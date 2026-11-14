# Replay vitals, movement, groups and creature state

Health values are decoded from replicated `FGameplayAttributeData` on the creature's `AttributeSetBase` subobject. The instance name is resolved to `/Script/TheIsle.TIAttributeSetDinosaur` or `/Script/TheIsle.TIAttributeSetAnimals` according to the owning creature class. Fish and unknown classes are not assigned an attribute layout.

For engine network version 42, the verified flattened export fields are:

| Value | Handle (zero-based) | Export name | Compatible checksum |
| --- | --- | --- | --- |
| Current health | 1 | CurrentValue | 1941375516 |
| Maximum health | 3 | CurrentValue | 388483262 |
| Current stamina | 5 | CurrentValue | 1106828627 |
| Maximum stamina | 7 | CurrentValue | 254763432 |
| Direct Weight | 19 | CurrentValue | 82420820 |
| Blood | 35 | CurrentValue | 2248534704 |
| Maximum Blood | 37 | CurrentValue | 2241345538 |
| FoodValue | 21 | CurrentValue | 3889355494 |
| Maximum FoodValue | 23 | CurrentValue | 1258175889 |
| RottenValue | 25 | CurrentValue | 1173781508 |

All checks must match; a different engine, class, property checksum or payload width produces no HP value. Values are little-endian 32-bit floats. Unknown data remains null. BaseValue, LowHealth, food weight and other unnamed attribute slots are not treated as current HP or dinosaur mass.

The layout was inspected on copied replay data. Zero current health was observed on dead animal actors; healthy and injured actors expose distinct current and maximum health values. The UI displays the last observation at or before the chosen replay time. History schema 2 appends `health`, `max_health`, `health_seen`, `max_health_seen` to the original eight movement-sample columns. Schema 1 timelines display unavailable vitals instead of borrowing an entity's final values.

Stamina slots were identified by reconstructing Unreal's compatible property checksum from the parent attribute names `Stamina` and `MaxStamina`, the struct type `FGameplayAttributeData`, child `CurrentValue`, type `float`, and zero static array indices. The same reconstruction matches both existing HP signatures. See the engine's [replication layout implementation](https://github.com/folgerwang/UnrealEngine/blob/release/Engine/Source/Runtime/Engine/Private/RepLayout.cpp) and [CRC implementation](https://github.com/chendi-YU/UnrealEngine/blob/master/Engine/Source/Runtime/Core/Public/Misc/Crc.h). The checks reproduce these signatures independently in `tests/VitalsDecoderChecks`.

History schema 3 appends `stamina`, `max_stamina`, `stamina_seen`, `max_stamina_seen` at indices 12–15. Old schema 1 and 2 histories show unavailable stamina. Percent is current stamina divided by an observed positive maximum; no species default, growth-based value, or assumed 1000-point maximum is used. Current-only and maximum-only observations remain visible without inventing a percentage. Missing replication stays null, including animals and fish without these fields. Stamina is a replay observation with its own timestamp, not a live server query. Initial observations and exhaustion transitions survive history compaction.

**Direct Weight is now decoded; its kg unit has not been independently verified.** Both the BaseValue and CurrentValue checksums reproduce the parent attribute name `Weight`. The primary inspector displays the observed value as **Weight ghi nhận**, without claiming kg. The old maximum-HP-to-kg proxy remains explicitly labeled as an estimate inside expanded metadata and in the existing Telegram size comparison. It is not substituted for a missing direct Weight value. Growth percentage is not used to fabricate weight.

Blood is separate from HP. FoodValue is a separate observed food attribute, not an inferred hunger/thirst or diet percentage. Percentages require a positive observed maximum, and missing values remain null.

History schema 4 preserves the first 16 columns of schema 3 and appends:

| Indices | Values |
| --- | --- |
| 16–17 | Weight, observed time |
| 18–21 | Blood, maximum Blood, their observation times |
| 22–25 | FoodValue, maximum FoodValue, their observation times |
| 26–27 | RottenValue, observed time |
| 28–34 | Unreal yaw/pitch/roll, X/Y/Z velocity in cm/s, movement observation time |
| 35–37 | signed GroupId, leader bit (-1 unknown), group observation time |
| 38–39 | ability-state code, observation time |
| 40–41 | negative-effects mask, observation time |

Old timelines never borrow final values for these added fields. Velocity magnitude is divided by 100 to display m/s. World yaw is converted to a north-clockwise bearing by `(yaw + 90) mod 360`; it is the dinosaur's facing direction, separate from the direction from you to a target.

Named creature properties are guarded by engine version, checksum and width: GroupId `3232821953` / 32 bits (int32), bIsGroupLeader `2318999206` / 1 bit, AbilityState `4238146573` / 7 bits, ReplicatedNegativeEffects `4019245960` / 256 bits. The observed FNegativeEffects payload contains eight 32-bit booleans; any non-boolean value or unsupported length is rejected. The eight slot names and serializer order have now been verified from the installed game binary; see [EFFECTS-SOURCES.md](EFFECTS-SOURCES.md) for the mapping and read-only reproduction check. Only the ability names supported by the [documented native state observations](https://github.com/diplomatic-tendencies/evrima-dev-knowledge/blob/main/EVRIMA_PteranodonGrab_Architecture.md) are labeled; unknown ability codes stay explicitly unnamed.

GroupId is a signed group key, not a group-size field or proof that a player has other members. Two observed equal nonzero keys identify the same group. See the [grouping observations](https://github.com/diplomatic-tendencies/evrima-dev-knowledge/blob/main/EVRIMA_Grouping_Mechanism.md). Known matching groups are marked as teammates and excluded from Telegram target alerts. Missing keys do not imply friendship.

Coelacanth/Coalecanth/Coalacanth spelling variants are excluded before creating decoder entities. The viewer also filters these variants from legacy histories and exports. Unrelated species are retained.

Engine references: [GameplayAttributeData](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/GameplayAbilities/FGameplayAttributeData) and [Gameplay Attributes and Attribute Sets](https://dev.epicgames.com/documentation/unreal-engine/gameplay-attributes-and-attribute-sets-for-the-gameplay-ability-system-in-unreal-engine?lang=en-US). These explain base/current attribute values; they do not establish The Isle's mass conversion.

Validation: `tests/VitalsDecoderChecks` covers property checksums, widths, numeric guards, effect payloads and species exclusion. `tests/test_extended_vitals.cjs` covers added metrics, motion units, groups, state labels, legacy isolation and exclusions; `tests/browser_extended.py` covers the inspector, map priority and 390/320 px rendering. A frozen 353 MB replay comparison preserved existing fields on all 227 retained entities, excluded 1,641 Coelacanth actors, and reported zero movement errors or unsupported extended fields.
