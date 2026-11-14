# Dinosaur negative effects

The eight names were verified on 2026-11-14 by reading the installed game's executable **on disk**. No game process was opened and no game files were changed. Public SDK searches did not establish the slot order, so this mapping uses the native reflection metadata and serializer together.

Binary: `TheIsleClient-Win64-Shipping.exe`, 204,050,944 bytes; SHA-256 `440e5e9ede3a808d98a0c65f528c9da41eb6444040934f1f8ca03c37d38d4115`.

## Verified layout

The `FNegativeEffects` struct registration describes eight properties and an eight-byte native struct. Each property's native setter writes a distinct byte at offsets 0 through 7. The native `NetSerialize` method serializes those offsets in ascending order, using a 32-bit boolean for each. This matches the observed 256-bit replay payload accepted by `CreatureLayout.TryEffects`.

| Replay slot | Mask bit | Native property | Display name |
| --- | --- | --- | --- |
| E1 | 1 | bSlovenly | Vệ sinh kém (Slovenly) |
| E2 | 2 | bFluidDeficient | Thiếu dịch cơ thể (Fluid Deficient) |
| E3 | 4 | bHasCataracts | Đục thủy tinh thể (Cataracts) |
| E4 | 8 | bGlassBones | Xương giòn (Glass Bones) |
| E5 | 16 | bIsSickState | Đang bị bệnh (Sick) |
| E6 | 32 | bIsHeadFractured | Gãy xương đầu (Head Fracture) |
| E7 | 64 | bIsBodyFractured | Gãy xương thân (Body Fracture) |
| E8 | 128 | bIsLegsFractured | Gãy chân (Leg Fracture) |

These labels describe the replicated flags. They do not infer bleed, venom, remaining duration, disease cause, damage modifiers or recovery time. In particular, Glass Bones is distinct from an observed fracture. `VenomStatus` is a separate property and is not one of these eight bits.

## Reproduction

`tests/verify_effects_layout.py --binary <path-to-TheIsleClient-Win64-Shipping.exe>` validates this exact binary hash, reads the PE sections, checks the reflection property's setter for each native byte, and verifies serializer store order and four-byte reads. It uses only the Python standard library. The reviewed metadata is saved in `tests/negative-effects-layout.json`; no executable or disassembly is distributed with the application.

Addresses below are relative to the executable image base, for this exact binary only:

- Struct parameters: `0x0B6BDC50`.
- Property pointer array: `0x09EA4480`.
- Native serializer: `0x05493300` through `0x054936BF`.

The replay decoder continues to require engine network version 42, export checksum `4019245960`, exactly 256 bits, and eight valid 0/1 values. The existing history schema 4 stores the effect mask/time at indices 40/41. No schema migration is required. Older histories cannot borrow final actor effect values.

The inspector shows individual names, observation time and age relative to the selected replay point. Missing data is explicitly unknown; an observed zero mask is clear. Dead/out-of-scope dinosaurs show last recorded effects. The owner overview and target list expose the same timeline-relative state. CSV appends `negative_effects_status` and `negative_effects_names` while retaining the existing mask/time columns.

Evidence is limited to the recorded protocol and the inspected game binary. A future effect layout needs independent verification before reusing these names.
