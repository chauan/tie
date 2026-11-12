using System.Diagnostics.CodeAnalysis;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using Unreal.Core;
using Unreal.Core.Attributes;
using Unreal.Core.Contracts;
using Unreal.Core.Models;
using Unreal.Core.Models.Enums;
using UReader = Unreal.Core.BinaryReader;

[PlayerController("BP_ReplayPlayerController_C")]
public class ReplayController : INetFieldExportGroup { }

public class Entity
{
    public uint Id { get; set; }
    public string ClassPath { get; set; } = "";
    public string Species { get; set; } = "";
    public string Kind { get; set; } = "unknown";
    public string? SteamId { get; set; }
    public string? Name { get; set; }
    public uint? PlayerState { get; set; }
    public bool? IsAI { get; set; }
    public bool? Dead { get; set; }
    public double? Growth { get; set; }
    public double? X { get; set; }
    public double? Y { get; set; }
    public double? Z { get; set; }
    public double LastSeen { get; set; }
    public double FirstSeen { get; set; }
    public bool InScope { get; set; } = true;
    public string PositionSource { get; set; } = "spawn";
    public FVector? SpawnPosition { get; set; }
}

public class DiagnosticLog : ILogger
{
    public int WarningCount;
    public List<string> Samples = new();
    public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
    public bool IsEnabled(LogLevel level) => level >= LogLevel.Warning;
    public void Log<TState>(LogLevel level, EventId id, TState state, Exception? ex, Func<TState, Exception?, string> formatter)
    {
        if (!IsEnabled(level)) return;
        WarningCount++;
        if (Samples.Count < 8) Samples.Add(formatter(state, ex));
    }
}

public class IsleReader : ReplayReader<Replay>
{
    public readonly Dictionary<uint, Entity> Entities = new();
    public readonly Dictionary<uint, string> PlayerNames = new();
    // Compact sampled history: t, x, y, z, in_scope, dead(-1=unknown), growth, last_movement.
    public readonly Dictionary<uint, List<double?[]>> Tracks = new();
    public double HistorySampleSeconds = 1;
    private int historyPoints;
    public double Time;
    public int Frames, Movements, FailedMovements, Properties;
    public Replay Result => Replay;
    public IsleReader(ILogger logger) : base(logger, ParseMode.Full) { Replay = new Replay(); }

    static bool IsCreature(string path) => path.Contains("/Characters/Dinosaurs/") && !path.Contains("/Abilities/") && !path.Contains("Burrow")
        || path.Contains("/Characters/Animals/") || path.Contains("/Characters/Fishes/") || path.Contains("/AI/Characters/");

    Entity? GetEntity(uint channel)
    {
        var actor = Channels[channel]?.Actor;
        if (actor == null) return null;
        if (Entities.TryGetValue(actor.ActorNetGUID.Value, out var entity)) return entity;
        var path = _netGuidCache.GetNetFieldExportGroup(actor.Archetype?.Value)?.PathName;
        if (path == null || !IsCreature(path)) return null;
        var species = path.Split('/').Last().Replace("Default__BP_", "").Replace("BP_", "").Split('.')[0];
        if (species.EndsWith("_C")) species = species[..^2];
        entity = new Entity { Id = actor.ActorNetGUID.Value, ClassPath = path, Species = species, LastSeen = Time, FirstSeen = Time };
        if (path.Contains("/Animals/") || path.Contains("/Fishes/") || path.Contains("/AI/")) { entity.Kind = "ai"; entity.IsAI = true; }
        if (actor.Location is {} location) { entity.SpawnPosition = location; SetLocation(entity, location, "spawn"); }
        Entities[entity.Id] = entity;
        RecordState(entity, true);
        return entity;
    }

    void SetLocation(Entity e, FVector p, string source)
    {
        if (!double.IsFinite(p.X) || !double.IsFinite(p.Y) || !double.IsFinite(p.Z) || Math.Abs(p.X) > 5_000_000 || Math.Abs(p.Y) > 5_000_000) return;
        e.X = p.X; e.Y = p.Y; e.Z = p.Z; e.LastSeen = Time; e.PositionSource = source;
        if (Entities.ContainsKey(e.Id)) RecordState(e);
    }

    void RecordState(Entity e, bool force = false)
    {
        if (!Tracks.TryGetValue(e.Id, out var samples)) Tracks[e.Id] = samples = new();
        var sameTime = samples.Count > 0 && Math.Abs(samples[^1][0]!.Value - Time) < 0.0001;
        if (!force && samples.Count > 0 && !sameTime && Time - samples[^1][0]!.Value < HistorySampleSeconds) return;
        double?[] sample = [Math.Round(Time, 4), e.X, e.Y, e.Z, e.InScope ? 1 : 0,
            e.Dead.HasValue ? (e.Dead.Value ? 1 : 0) : -1, e.Growth.HasValue ? Math.Round(e.Growth.Value, 6) : null,
            Math.Round(e.LastSeen, 4)];
        if (sameTime) samples[^1] = sample;
        else { samples.Add(sample); historyPoints++; }
        if (historyPoints > 600_000) CompactHistory();
    }

    void CompactHistory()
    {
        HistorySampleSeconds *= 2;
        historyPoints = 0;
        foreach (var id in Tracks.Keys.ToArray())
        {
            var old = Tracks[id];
            if (old.Count < 3) { historyPoints += old.Count; continue; }
            var kept = new List<double?[]> { old[0] };
            for (int i = 1; i < old.Count - 1; i++)
            {
                var sample = old[i];
                bool transition = sample[4] != old[i - 1][4] || sample[5] != old[i - 1][5];
                if (transition || sample[0] - kept[^1][0] >= HistorySampleSeconds) kept.Add(sample);
            }
            kept.Add(old[^1]); Tracks[id] = kept; historyPoints += kept.Count;
        }
    }

    protected override void OnChannelOpened(uint ch, NetworkGUID? actor)
    {
        var e = GetEntity(ch); if (e == null) return;
        e.InScope = true;
        if (Channels[ch]?.Actor?.Location is {} p) SetLocation(e, p, "spawn");
        RecordState(e, true);
    }
    public override bool ReceivedSequencedBunch(DataBunch bunch)
    {
        var actor = Channels[bunch.ChIndex]?.Actor?.ActorNetGUID;
        var result = base.ReceivedSequencedBunch(bunch);
        if (bunch.bClose && actor != null && Entities.TryGetValue(actor.Value, out var e)) { e.InScope = false; RecordState(e, true); }
        return result;
    }
    protected override void OnChannelClosed(uint ch, NetworkGUID? actor)
    {
        if (actor != null && Entities.TryGetValue(actor.Value, out var e)) { e.InScope = false; RecordState(e, true); }
    }

    public override void ReadDemoFrameIntoPlaybackPackets(FArchive archive)
    {
        var position = archive.Position;
        if (archive.NetworkVersion >= NetworkVersionHistory.HISTORY_MULTIPLE_LEVELS) archive.ReadInt32();
        Time = archive.ReadSingle();
        archive.Seek(position);
        base.ReadDemoFrameIntoPlaybackPackets(archive);
        Frames++;
    }

    public override bool ReceivedReplicatorBunch(DataBunch bunch, FBitArchive archive, uint? repObject, bool layout)
    {
        var group = _netGuidCache.GetNetFieldExportGroup(repObject);
        if (layout && group != null) ReceiveProperties(archive, group, bunch.ChIndex, out _);
        archive.SkipBits(archive.GetBitsLeft());
        return !archive.IsError;
    }

    public override bool ReceiveProperties(FBitArchive archive, NetFieldExportGroup group, uint channel,
        [NotNullWhen(true)] out INetFieldExportGroup? export, bool enablePropertyChecksum = true, bool netDeltaUpdate = false)
    {
        export = new ReplayController();
        if (enablePropertyChecksum) archive.ReadBit();
        var entity = GetEntity(channel);
        while (!archive.AtEnd() && !archive.IsError)
        {
            var handle = archive.ReadIntPacked();
            if (handle == 0) return true;
            handle--;
            var count = archive.ReadIntPacked();
            if (count > archive.GetBitsLeft()) return false;
            if (!group.IsValidIndex(handle)) { archive.SkipBits(count); continue; }
            var field = group.NetFieldExports[handle]?.Name;
            if (count == 0) continue;
            var wanted = entity != null && field is "ReplicatedMovement" or "SteamId" or "PlayerState" or "bIsAIControlled" or "bIsDead" or "Growth";
            var playerName = field == "PlayerNamePrivate" && group.PathName.Contains("BP_PlayerState");
            if (!wanted && !playerName) { archive.SkipBits(count); continue; }
            var r = new NetBitReader(archive.ReadBits(count), (int)count) {
                EngineNetworkVersion = archive.EngineNetworkVersion, NetworkVersion = archive.NetworkVersion,
                ReplayHeaderFlags = archive.ReplayHeaderFlags, NetworkReplayVersion = archive.NetworkReplayVersion
            };
            try
            {
                if (playerName)
                {
                    var name = r.ReadFString();
                    if (!r.IsError && r.AtEnd() && Channels[channel]?.ActorId is uint id) PlayerNames[id] = name;
                    continue;
                }
                if (entity == null) continue;
                switch (field)
                {
                    case "ReplicatedMovement":
                        var move = r.SerializeRepMovement(VectorQuantization.RoundTwoDecimals, RotatorQuantization.ShortComponents);
                        if (r.IsError || !r.AtEnd())
                        {
                            r.Reset();
                            move = r.SerializeRepMovement(VectorQuantization.RoundTwoDecimals, RotatorQuantization.ByteComponents);
                        }
                        if (!r.IsError && r.AtEnd()) { SetLocation(entity, move.Location, "replicated_movement"); Movements++; }
                        else FailedMovements++;
                        break;
                    case "SteamId":
                        var steam = r.ReadFString();
                        if (!r.IsError && r.AtEnd() && steam.Length == 17 && steam.All(char.IsDigit)) { entity.SteamId = steam; entity.Kind = "player"; }
                        break;
                    case "PlayerState": entity.PlayerState = r.ReadIntPacked(); break;
                    case "bIsAIControlled": entity.IsAI = r.ReadBit(); if (entity.IsAI == true) entity.Kind = "ai"; break;
                    case "bIsDead": entity.Dead = r.ReadBit(); RecordState(entity, true); break;
                    case "Growth": if (count == 32) entity.Growth = r.ReadSingle(); break;
                }
                RecordState(entity);
                Properties++;
            }
            catch (Exception) { if (field == "ReplicatedMovement") FailedMovements++; }
        }
        return !archive.IsError;
    }

    public void Parse(string file)
    {
        using var input = File.OpenRead(file);
        using var header = new UReader(input.ReadPrefix(16_384));
        ReadReplayInfo(header);
        HistorySampleSeconds = Math.Max(1, Math.Ceiling(Replay.Info.LengthInMs / 3_600_000.0));
        if (Replay.Info.IsCompressed || Replay.Info.IsEncrypted) throw new NotSupportedException("Replay compression/encryption is not supported by this Isle decoder.");
        input.Position = header.Position;
        using var raw = new System.IO.BinaryReader(input);
        while (input.Position + 8 <= input.Length)
        {
            uint type = raw.ReadUInt32(); int length = raw.ReadInt32();
            if (length < 0 || input.Position + length > input.Length) break;
            if (type is not 0 and not 1) { input.Seek(length, SeekOrigin.Current); continue; }
            if (length > 256 * 1024 * 1024) throw new InvalidDataException("Replay chunk exceeds 256 MB.");
            using var chunk = new UReader(raw.ReadBytes(length).AsMemory()) {
                ReplayVersion = header.ReplayVersion, NetworkVersion = header.NetworkVersion,
                EngineNetworkVersion = header.EngineNetworkVersion, ReplayHeaderFlags = header.ReplayHeaderFlags,
                NetworkReplayVersion = header.NetworkReplayVersion
            };
            if (type == 0)
            {
                ReadReplayHeader(chunk);
                header.NetworkVersion = chunk.NetworkVersion; header.EngineNetworkVersion = chunk.EngineNetworkVersion;
                header.ReplayHeaderFlags = chunk.ReplayHeaderFlags; header.NetworkReplayVersion = chunk.NetworkReplayVersion;
            }
            else ReadReplayData(chunk, length);
        }
        foreach (var e in Entities.Values)
        {
            if (e.PlayerState is uint state && PlayerNames.TryGetValue(state, out var name)) e.Name = name;
            if (e.Kind == "unknown" && e.PlayerState is > 0 && e.IsAI != true) e.Kind = "player";
            RecordState(e, true);
        }
    }

    protected override void OnExportRead(uint ch, INetFieldExportGroup? e) { }
    protected override void OnExternalDataRead(uint ch, IExternalData? e) { }
    protected override void OnNetDeltaRead(uint ch, NetDeltaUpdate e) { }
}

static class Extensions
{
    public static ReadOnlyMemory<byte> ReadPrefix(this Stream s, int max)
    {
        var b = new byte[Math.Min(s.Length, max)]; s.ReadExactly(b); return b;
    }
}

public class Program
{
    public static int Main(string[] args)
    {
        if (args.Length != 1) { Console.Error.WriteLine("Usage: IsleDecoder <file.replay>"); return 2; }
        var log = new DiagnosticLog(); var reader = new IsleReader(log);
        try
        {
            reader.Parse(args[0]);
            Console.WriteLine(JsonSerializer.Serialize(new {
                entities = reader.Entities.Values, time_seconds = reader.Time, tracks = reader.Tracks,
                history_sample_seconds = reader.HistorySampleSeconds, history_schema = 1,
                diagnostics = new { frames = reader.Frames, movements = reader.Movements, failed_movements = reader.FailedMovements,
                    properties = reader.Properties, warnings = log.WarningCount, samples = log.Samples }
            }, new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower }));
            return 0;
        }
        catch (Exception ex) { Console.Error.WriteLine(ex.ToString()); return 1; }
    }
}
