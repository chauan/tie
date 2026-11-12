using System.Buffers.Binary;

static void Check(bool passed, string contract) { if (!passed) throw new Exception(contract); }
const string group = "/Script/TheIsle.TIAttributeSetDinosaur";
Check(VitalsLayout.TryField(group,42,1,"CurrentValue",1941375516,out var field) && field==VitalField.Health,"Known current HP schema");
Check(VitalsLayout.TryField(group,42,3,"CurrentValue",388483262,out field) && field==VitalField.MaxHealth,"Known maximum HP schema");
Check(!VitalsLayout.TryField(group,43,1,"CurrentValue",1941375516,out _),"Reject a new engine layout until verified");
Check(!VitalsLayout.TryField(group,42,1,"CurrentValue",0,out _),"Do not trust a handle with a different property checksum");
Check(!VitalsLayout.TryField(group,42,1,"BaseValue",1941375516,out _),"Use current, not base, attributes");
Check(!VitalsLayout.TryField(group,42,19,"CurrentValue",1941375516,out _),"Other attributes are not health or body mass");
Check(!VitalsLayout.TryField("/Script/Other.AttributeSet",42,1,"CurrentValue",1941375516,out _),"Reject unrelated groups");
Check(VitalsLayout.AttributeGroupFor("/Game/TheIsle/Core/Characters/Dinosaurs/Example") == group,"Resolve a stably named dinosaur subobject");
Check(VitalsLayout.AttributeGroupFor("/Game/TheIsle/Core/Characters/Animals/Boar") == "/Script/TheIsle.TIAttributeSetAnimals","Animal attributes use their own group");
Check(VitalsLayout.AttributeGroupFor("/Game/TheIsle/Core/Characters/Fishes/Schools/Example") == null,"Do not infer a fish attribute layout");
foreach (var value in new[]{0f,125.5f,13500f}) {
    var bytes=new byte[4];BinaryPrimitives.WriteInt32LittleEndian(bytes,BitConverter.SingleToInt32Bits(value));
    Check(VitalsLayout.TryValue(bytes,32,out var decoded) && decoded==value,"Read exact little-endian HP values, including zero");
    Check(!VitalsLayout.TryValue(bytes,31,out _),"Reject mismatched payload lengths");
}
foreach (var value in new[]{-1f,float.NaN,float.PositiveInfinity,20_000_000f}) {
    var bytes=BitConverter.GetBytes(value);Check(!VitalsLayout.TryValue(bytes,32,out _),"Reject invalid or unbounded HP");
}
Check(!VitalsLayout.TryValue(new byte[8],32,out _),"Reject trailing payload bytes");
Console.WriteLine("PASS: replay vitals checksums, engine/class guards, attribute semantics, payload lengths and numeric boundaries");
