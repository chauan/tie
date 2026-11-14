using System.Buffers.Binary;

public static class CreatureLayout
{
    public const uint GroupChecksum = 3232821953;
    public const uint LeaderChecksum = 2318999206;
    public const uint AbilityChecksum = 4238146573;
    public const uint EffectsChecksum = 4019245960;

    public static bool Excluded(string path) => new[] { "Coalecanth", "Coalacanth", "Coelacanth" }
        .Any(name => path.Contains(name, StringComparison.OrdinalIgnoreCase));

    public static bool Matches(uint engine, string? field, uint checksum, uint bits) => engine == VitalsLayout.EngineVersion && (field switch
    {
        "GroupId" => checksum == GroupChecksum && bits == 32,
        "bIsGroupLeader" => checksum == LeaderChecksum && bits == 1,
        "AbilityState" => checksum == AbilityChecksum && bits == 7,
        "ReplicatedNegativeEffects" => checksum == EffectsChecksum && bits == 256,
        _ => false
    });

    // FNegativeEffects in the observed v42 layout is eight serialized 32-bit booleans.
    // Native member names and serialization order are verified in EFFECTS-SOURCES.md.
    public static bool TryEffects(ReadOnlySpan<byte> bytes, out byte mask)
    {
        mask = 0;
        if (bytes.Length != 32) return false;
        for (int i = 0; i < 8; i++)
        {
            var value = BinaryPrimitives.ReadUInt32LittleEndian(bytes.Slice(i * 4, 4));
            if (value > 1) { mask = 0; return false; }
            if (value == 1) mask |= (byte)(1 << i);
        }
        return true;
    }
}
