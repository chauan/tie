using System.Buffers.Binary;

public enum VitalField { Health, MaxHealth }

// Flattened FGameplayAttributeData fields observed in EVRIMA's replay schema.
// Check the export checksum as well as the index: CurrentValue alone is ambiguous.
public static class VitalsLayout
{
    public const uint EngineVersion = 42;
    public const uint HealthChecksum = 1941375516;
    public const uint MaxHealthChecksum = 388483262;

    public static bool IsAttributeGroup(string path) => path is
        "/Script/TheIsle.TIAttributeSetDinosaur" or "/Script/TheIsle.TIAttributeSetAnimals";

    public static string? AttributeGroupFor(string classPath) =>
        classPath.Contains("/Characters/Dinosaurs/") ? "/Script/TheIsle.TIAttributeSetDinosaur" :
        classPath.Contains("/Characters/Animals/") ? "/Script/TheIsle.TIAttributeSetAnimals" : null;

    public static bool TryField(string group, uint engineVersion, uint handle, string? name, uint checksum, out VitalField field)
    {
        field = VitalField.Health;
        if (!IsAttributeGroup(group) || engineVersion != EngineVersion || name != "CurrentValue") return false;
        if (handle == 1 && checksum == HealthChecksum) return true;
        if (handle == 3 && checksum == MaxHealthChecksum) { field = VitalField.MaxHealth; return true; }
        return false;
    }

    public static bool TryValue(ReadOnlySpan<byte> bytes, uint bitCount, out double value)
    {
        value = 0;
        if (bitCount != 32 || bytes.Length != 4) return false;
        var decoded = BitConverter.Int32BitsToSingle(BinaryPrimitives.ReadInt32LittleEndian(bytes));
        if (!float.IsFinite(decoded) || decoded < 0 || decoded > 10_000_000) return false;
        value = decoded;
        return true;
    }
}
