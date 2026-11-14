using System.Buffers.Binary;

public enum VitalField { Health, MaxHealth, Stamina, MaxStamina, Weight, Blood, MaxBlood, FoodValue, MaxFoodValue, RottenValue }

// Flattened FGameplayAttributeData fields observed in EVRIMA's replay schema.
// Check the export checksum as well as the index: CurrentValue alone is ambiguous.
public static class VitalsLayout
{
    public const uint EngineVersion = 42;
    public const uint HealthChecksum = 1941375516;
    public const uint MaxHealthChecksum = 388483262;
    public const uint StaminaChecksum = 1106828627;
    public const uint MaxStaminaChecksum = 254763432;
    public const uint WeightChecksum = 82420820;
    public const uint BloodChecksum = 2248534704;
    public const uint MaxBloodChecksum = 2241345538;
    public const uint FoodValueChecksum = 3889355494;
    public const uint MaxFoodValueChecksum = 1258175889;
    public const uint RottenValueChecksum = 1173781508;

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
        if (handle == 5 && checksum == StaminaChecksum) { field = VitalField.Stamina; return true; }
        if (handle == 7 && checksum == MaxStaminaChecksum) { field = VitalField.MaxStamina; return true; }
        if (handle == 19 && checksum == WeightChecksum) { field = VitalField.Weight; return true; }
        if (handle == 35 && checksum == BloodChecksum) { field = VitalField.Blood; return true; }
        if (handle == 37 && checksum == MaxBloodChecksum) { field = VitalField.MaxBlood; return true; }
        if (handle == 21 && checksum == FoodValueChecksum) { field = VitalField.FoodValue; return true; }
        if (handle == 23 && checksum == MaxFoodValueChecksum) { field = VitalField.MaxFoodValue; return true; }
        if (handle == 25 && checksum == RottenValueChecksum) { field = VitalField.RottenValue; return true; }
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
