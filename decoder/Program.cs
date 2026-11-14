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
    public double? Health { get; set; }
    public double? MaxHealth { get; set; }
    public double? HealthSeen { get; set; }
    public double? MaxHealthSeen { get; set; }
    public double? Stamina { get; set; }
    public double? MaxStamina { get; set; }
    public double? StaminaSeen { get; set; }
    public double? MaxStaminaSeen { get; set; }
    public double? Weight { get; set; }
    public double? WeightSeen { get; set; }
    public double? Blood { get; set; }
    public double? MaxBlood { get; set; }
    public double? BloodSeen { get; set; }
    public double? MaxBloodSeen { get; set; }
    public double? FoodValue { get; set; }
    public double? MaxFoodValue { get; set; }
    public double? FoodSeen { get; set; }
    public double? MaxFoodSeen { get; set; }
    public double? RottenValue { get; set; }
    public double? RottenSeen { get; set; }
    public double? Yaw { get; set; }
    public double? Pitch { get; set; }
    public double? Roll { get; set; }
    public double? VelocityX { get; set; }
    public double? VelocityY { get; set; }
    public double? VelocityZ { get; set; }
    public double? MovementSeen { get; set; }
    public int? GroupId { get; set; }
    public bool? IsGroupLeader { get; set; }
    public double? GroupSeen { get; set; }
    public byte? AbilityState { get; set; }
    public double? AbilitySeen { get; set; }
    public byte? NegativeEffectsMask { get; set; }
    public double? EffectsSeen { get; set; }
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
    // t, x, y, z, scope, dead(-1=unknown), growth, last_movement,
    // hp, max_hp, hp_seen, max_hp_seen, stamina, max_stamina, stamina_seen, max_stamina_seen.
    public readonly Dictionary<uint, List<double?[]>> Tracks = new();
    public double HistorySampleSeconds = 1;
    private int historyPoints;
    public double Time;
    public int Frames, Movements, FailedMovements, Properties;
    public int VitalUpdates, UnsupportedVitalFields;
    public int StaminaUpdates, UnsupportedStaminaFields;
    public int ExtendedVitalUpdates, UnsupportedExtendedFields, ExcludedActors;
    private readonly HashSet<uint> excludedActors = new();
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
        if (CreatureLayout.Excluded(path)) { if (excludedActors.Add(actor.ActorNetGUID.Value)) ExcludedActors++; return null; }
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
            Math.Round(e.LastSeen, 4), e.Health, e.MaxHealth, e.HealthSeen, e.MaxHealthSeen,
            e.Stamina, e.MaxStamina, e.StaminaSeen, e.MaxStaminaSeen,
            e.Weight, e.WeightSeen, e.Blood, e.MaxBlood, e.BloodSeen, e.MaxBloodSeen,
            e.FoodValue, e.MaxFoodValue, e.FoodSeen, e.MaxFoodSeen, e.RottenValue, e.RottenSeen,
            e.Yaw, e.Pitch, e.Roll, e.VelocityX, e.VelocityY, e.VelocityZ, e.MovementSeen,
            e.GroupId, e.IsGroupLeader.HasValue ? (e.IsGroupLeader.Value ? 1 : 0) : -1, e.GroupSeen,
            e.AbilityState, e.AbilitySeen, e.NegativeEffectsMask, e.EffectsSeen];
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
                var previous = old[i - 1];
                bool transition = sample[4] != previous[4] || sample[5] != previous[5]
                    || sample[8].HasValue != previous[8].HasValue || sample[9].HasValue != previous[9].HasValue
                    || sample[8] == 0 && previous[8] > 0
                    || sample[12].HasValue != previous[12].HasValue || sample[13].HasValue != previous[13].HasValue
                    || sample[12] == 0 && previous[12] > 0
                    || ExtendedTransition(sample, previous)
                    || sample[18] == 0 && previous[18] > 0 || sample[22] == 0 && previous[22] > 0
                    || sample[35] != previous[35] || sample[36] != previous[36]
                    || sample[38] != previous[38] || sample[40] != previous[40];
                if (transition || sample[0] - kept[^1][0] >= HistorySampleSeconds) kept.Add(sample);
            }
            kept.Add(old[^1]); Tracks[id] = kept; historyPoints += kept.Count;
        }
    }

    static bool ExtendedTransition(double?[] sample, double?[] previous)
    {
        for (int i = 16; i < sample.Length; i++) if (sample[i].HasValue != previous[i].HasValue) return true;
        return false;
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
        // Stably named subobjects export the instance name, not their native class.
        if (group == null && repObject.HasValue && _netGuidCache.TryGetPathName(repObject.Value, out var path)
            && path == "AttributeSetBase" && GetEntity(bunch.ChIndex) is {} creature
            && VitalsLayout.AttributeGroupFor(creature.ClassPath) is {} attributePath)
            _netGuidCache.NetFieldExportGroupMap.TryGetValue(attributePath, out group);
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
            var fieldExport = group.NetFieldExports[handle];
            var field = fieldExport?.Name;
            if (count == 0) continue;
            if (entity != null && VitalsLayout.IsAttributeGroup(group.PathName) && field == "CurrentValue" && handle is 1 or 3 or 5 or 7 or 19 or 21 or 23 or 25 or 35 or 37)
            {
                var bytes = archive.ReadBits(count);
                if (VitalsLayout.TryField(group.PathName, (uint)archive.EngineNetworkVersion, handle, field, fieldExport!.CompatibleChecksum, out var vital)
                    && VitalsLayout.TryValue(bytes, count, out var value))
                {
                    bool transition = false;
                    if (vital == VitalField.Health) { transition = !entity.Health.HasValue || value == 0 && entity.Health > 0; entity.Health = value; entity.HealthSeen = Math.Round(Time, 4); }
                    else if (vital == VitalField.MaxHealth) { transition = !entity.MaxHealth.HasValue; entity.MaxHealth = value; entity.MaxHealthSeen = Math.Round(Time, 4); }
                    else if (vital == VitalField.Stamina) { transition = !entity.Stamina.HasValue || value == 0 && entity.Stamina > 0; entity.Stamina = value; entity.StaminaSeen = Math.Round(Time, 4); }
                    else if (vital == VitalField.MaxStamina) { transition = !entity.MaxStamina.HasValue; entity.MaxStamina = value; entity.MaxStaminaSeen = Math.Round(Time, 4); }
                    else if (vital == VitalField.Weight) { transition = !entity.Weight.HasValue; entity.Weight = value; entity.WeightSeen = Math.Round(Time, 4); }
                    else if (vital == VitalField.Blood) { transition = !entity.Blood.HasValue || value == 0 && entity.Blood > 0; entity.Blood = value; entity.BloodSeen = Math.Round(Time, 4); }
                    else if (vital == VitalField.MaxBlood) { transition = !entity.MaxBlood.HasValue; entity.MaxBlood = value; entity.MaxBloodSeen = Math.Round(Time, 4); }
                    else if (vital == VitalField.FoodValue) { transition = !entity.FoodValue.HasValue || value == 0 && entity.FoodValue > 0; entity.FoodValue = value; entity.FoodSeen = Math.Round(Time, 4); }
                    else if (vital == VitalField.MaxFoodValue) { transition = !entity.MaxFoodValue.HasValue; entity.MaxFoodValue = value; entity.MaxFoodSeen = Math.Round(Time, 4); }
                    else { transition = !entity.RottenValue.HasValue; entity.RottenValue = value; entity.RottenSeen = Math.Round(Time, 4); }
                    RecordState(entity, transition);
                    if (vital is VitalField.Stamina or VitalField.MaxStamina) StaminaUpdates++;
                    else if (vital is VitalField.Health or VitalField.MaxHealth) VitalUpdates++;
                    else ExtendedVitalUpdates++;
                }
                else if (handle is 5 or 7) UnsupportedStaminaFields++;
                else if (handle is 1 or 3) UnsupportedVitalFields++;
                else UnsupportedExtendedFields++;
                continue;
            }
            if (entity != null && field is "GroupId" or "bIsGroupLeader" or "AbilityState" or "ReplicatedNegativeEffects")
            {
                var bytes = archive.ReadBits(count);
                if (!CreatureLayout.Matches((uint)archive.EngineNetworkVersion, field, fieldExport!.CompatibleChecksum, count)) { UnsupportedExtendedFields++; continue; }
                var seen = Math.Round(Time, 4);
                if (field == "GroupId") { entity.GroupId = System.Buffers.Binary.BinaryPrimitives.ReadInt32LittleEndian(bytes); entity.GroupSeen = seen; }
                else if (field == "bIsGroupLeader") { entity.IsGroupLeader = (bytes[0] & 1) != 0; entity.GroupSeen = seen; }
                else if (field == "AbilityState") { entity.AbilityState = (byte)(bytes[0] & 127); entity.AbilitySeen = seen; }
                else if (CreatureLayout.TryEffects(bytes, out var mask)) { entity.NegativeEffectsMask = mask; entity.EffectsSeen = seen; }
                else { UnsupportedExtendedFields++; continue; }
                RecordState(entity, true);
                continue;
            }
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
                        if (!r.IsError && r.AtEnd()) {
                            if (double.IsFinite(move.Rotation.Yaw) && double.IsFinite(move.Rotation.Pitch) && double.IsFinite(move.Rotation.Roll)
                                && double.IsFinite(move.LinearVelocity.X) && double.IsFinite(move.LinearVelocity.Y) && double.IsFinite(move.LinearVelocity.Z)) {
                                entity.Yaw = move.Rotation.Yaw; entity.Pitch = move.Rotation.Pitch; entity.Roll = move.Rotation.Roll;
                                entity.VelocityX = move.LinearVelocity.X; entity.VelocityY = move.LinearVelocity.Y; entity.VelocityZ = move.LinearVelocity.Z;
                                entity.MovementSeen = Math.Round(Time, 4);
                            }
                            SetLocation(entity, move.Location, "replicated_movement"); Movements++;
                        }
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
                history_sample_seconds = reader.HistorySampleSeconds, history_schema = 4,
                diagnostics = new { frames = reader.Frames, movements = reader.Movements, failed_movements = reader.FailedMovements,
                    properties = reader.Properties, health_updates = reader.VitalUpdates, unsupported_health_fields = reader.UnsupportedVitalFields,
                    stamina_updates = reader.StaminaUpdates, unsupported_stamina_fields = reader.UnsupportedStaminaFields,
                    extended_vital_updates = reader.ExtendedVitalUpdates, unsupported_extended_fields = reader.UnsupportedExtendedFields, excluded_coelacanth = reader.ExcludedActors,
                    warnings = log.WarningCount, samples = log.Samples }
            }, new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower }));
            return 0;
        }
        catch (Exception ex) { Console.Error.WriteLine(ex.ToString()); return 1; }
    }
}
