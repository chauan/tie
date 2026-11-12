# Replay health and estimated weight

Health values are decoded from replicated `FGameplayAttributeData` on the creature's `AttributeSetBase` subobject. The instance name is resolved to `/Script/TheIsle.TIAttributeSetDinosaur` or `/Script/TheIsle.TIAttributeSetAnimals` according to the owning creature class. Fish and unknown classes are not assigned an attribute layout.

For engine network version 42, the verified flattened export fields are:

| Value | Handle (zero-based) | Export name | Compatible checksum |
| --- | --- | --- | --- |
| Current health | 1 | CurrentValue | 1941375516 |
| Maximum health | 3 | CurrentValue | 388483262 |

All checks must match; a different engine, class, property checksum or payload width produces no HP value. Values are little-endian 32-bit floats. Unknown data remains null. BaseValue, LowHealth, food weight and other unnamed attribute slots are not treated as current HP or dinosaur mass.

The layout was inspected on copied replay data. Zero current health was observed on dead animal actors; healthy and injured actors expose distinct current and maximum health values. The UI displays the last observation at or before the chosen replay time. History schema 2 appends `health`, `max_health`, `health_seen`, `max_health_seen` to the original eight movement-sample columns. Schema 1 timelines display unavailable vitals instead of borrowing an entity's final values.

**Weight is an estimate, not a separately decoded kg field.** For dinosaur classes only, the viewer uses maximum HP as a numeric proxy for kilograms and labels it `ước tính từ máu tối đa`. This conversion has not been independently verified for every species, mutation or custom server. Animals and fish receive no such estimate. Exact mass requires a separately verified source or mapping. Missing maximum HP means no weight estimate; growth percentage is not used to fabricate it.

Engine references: [GameplayAttributeData](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/GameplayAbilities/FGameplayAttributeData) and [Gameplay Attributes and Attribute Sets](https://dev.epicgames.com/documentation/unreal-engine/gameplay-attributes-and-attribute-sets-for-the-gameplay-ability-system-in-unreal-engine?lang=en-US). These explain base/current attribute values; they do not establish The Isle's mass conversion.

Validation: `tests/VitalsDecoderChecks` covers the property and numeric guards; `tests/test_vitals.cjs` covers timeline isolation, partial/missing data and estimate labeling; browser checks exercise the rendered HP meter, details and CSV.
