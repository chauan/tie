using System.Buffers.Binary;

static void Check(bool passed, string contract) { if (!passed) throw new Exception(contract); }
const string group = "/Script/TheIsle.TIAttributeSetDinosaur";
Check(VitalsLayout.TryField(group,42,1,"CurrentValue",1941375516,out var field) && field==VitalField.Health,"Known current HP schema");
Check(VitalsLayout.TryField(group,42,3,"CurrentValue",388483262,out field) && field==VitalField.MaxHealth,"Known maximum HP schema");
Check(VitalsLayout.TryField(group,42,5,"CurrentValue",1106828627,out field) && field==VitalField.Stamina,"Known current stamina schema");
Check(VitalsLayout.TryField(group,42,7,"CurrentValue",254763432,out field) && field==VitalField.MaxStamina,"Known maximum stamina schema");
Check(!VitalsLayout.TryField(group,42,5,"CurrentValue",254763432,out _),"Do not confuse current and maximum stamina");
Check(!VitalsLayout.TryField(group,43,5,"CurrentValue",1106828627,out _),"Reject unverified stamina engine versions");
Check(!VitalsLayout.TryField(group,42,5,"BaseValue",1106828627,out _),"Base stamina is not observed current stamina");
Check(VitalsLayout.TryField("/Script/TheIsle.TIAttributeSetAnimals",42,7,"CurrentValue",254763432,out field) && field==VitalField.MaxStamina,"Animal stamina requires the same verified property signature");
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

// Reproduce Unreal's compatible property checksum independently of the decoder.
// This ties the flattened CurrentValue slots to their parent attribute names.
static uint AttributeChecksum(string attribute) {
    uint crc=0xffffffff;
    void Bytes(byte[] bytes) { foreach(var b in bytes) { crc^=b; for(int i=0;i<8;i++)crc=(crc>>1)^((crc&1)!=0?0xedb88320u:0u); } }
    void Text(string value) => Bytes(System.Text.Encoding.UTF32.GetBytes(value.ToLowerInvariant()));
    Text(attribute);Text("FGameplayAttributeData");Bytes(new byte[4]);
    Text("CurrentValue");Text("float");Bytes(new byte[4]);
    return ~crc;
}
Check(AttributeChecksum("Health")==VitalsLayout.HealthChecksum,"Health checksum identifies the parent attribute");
Check(AttributeChecksum("MaxHealth")==VitalsLayout.MaxHealthChecksum,"Maximum health checksum identifies the parent attribute");
Check(AttributeChecksum("Stamina")==VitalsLayout.StaminaChecksum,"Stamina checksum identifies the parent attribute");
Check(AttributeChecksum("MaxStamina")==VitalsLayout.MaxStaminaChecksum,"Maximum stamina checksum identifies the parent attribute");
Console.WriteLine("PASS: attribute names reproduce the observed Health, MaxHealth, Stamina and MaxStamina checksums");
foreach(var item in new[]{
    ("Weight",19u,VitalsLayout.WeightChecksum,VitalField.Weight),
    ("Blood",35u,VitalsLayout.BloodChecksum,VitalField.Blood),
    ("MaxBlood",37u,VitalsLayout.MaxBloodChecksum,VitalField.MaxBlood),
    ("FoodValue",21u,VitalsLayout.FoodValueChecksum,VitalField.FoodValue),
    ("MaxFoodValue",23u,VitalsLayout.MaxFoodValueChecksum,VitalField.MaxFoodValue),
    ("RottenValue",25u,VitalsLayout.RottenValueChecksum,VitalField.RottenValue)}) {
    Check(AttributeChecksum(item.Item1)==item.Item3,"Extended parent attribute checksum");
    Check(VitalsLayout.TryField(group,42,item.Item2,"CurrentValue",item.Item3,out field)&&field==item.Item4,"Read verified extended attribute");
    Check(!VitalsLayout.TryField(group,43,item.Item2,"CurrentValue",item.Item3,out _),"Reject extended attributes on unverified engine");
    Check(!VitalsLayout.TryField(group,42,item.Item2,"CurrentValue",item.Item3^1u,out _),"Reject changed extended property signature");
}
Check(CreatureLayout.Matches(42,"GroupId",3232821953,32),"Observed signed int32 group key");
Check(!CreatureLayout.Matches(42,"GroupId",3232821953,8),"Reject truncated group key");
Check(CreatureLayout.Matches(42,"bIsGroupLeader",2318999206,1),"Observed leader bit");
Check(CreatureLayout.Matches(42,"AbilityState",4238146573,7),"Observed ability code payload");
Check(!CreatureLayout.Matches(43,"AbilityState",4238146573,7),"Don't reuse state layouts on a new engine");
var effects=new byte[32];effects[28]=1;
Check(CreatureLayout.TryEffects(effects,out var mask)&&mask==128,"Preserve the eighth effect slot without naming it");
effects[4]=1;Check(CreatureLayout.TryEffects(effects,out mask)&&mask==130,"Preserve multiple active effect slots");
effects[4]=2;Check(!CreatureLayout.TryEffects(effects,out _),"Reject unsupported effect encodings");
Check(CreatureLayout.TryEffects(new byte[32],out mask)&&mask==0,"Observed clear effects differ from missing data");
Check(!CreatureLayout.TryEffects(new byte[31],out _),"Reject partial effect structure");
foreach(var name in new[]{"BP_Coalecanth","BP_Fish_Coalacanth","BP_Coelacanth","bp_coalecanth"}) Check(CreatureLayout.Excluded(name),"Exclude requested fish spelling variants");
Check(!CreatureLayout.Excluded("BP_Fish_RainbowFish"),"Keep unrelated animals");
Console.WriteLine("PASS: Weight/Blood/food signatures, group/action/effect guards and Coelacanth exclusions");
