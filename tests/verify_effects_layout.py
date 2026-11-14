"""Read-only verification of the native negative-effect layout in the inspected game build."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

EXPECTED_SHA256 = '440e5e9ede3a808d98a0c65f528c9da41eb6444040934f1f8ca03c37d38d4115'
MEMBERS = ['bSlovenly', 'bFluidDeficient', 'bHasCataracts', 'bGlassBones', 'bIsSickState',
           'bIsHeadFractured', 'bIsBodyFractured', 'bIsLegsFractured']


def verify(binary):
    data = binary.read_bytes()
    assert hashlib.sha256(data).hexdigest() == EXPECTED_SHA256, 'Unverified game build; do not reuse hardcoded addresses'
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    assert data[pe:pe + 4] == b'PE\0\0'
    optional = pe + 24
    image_base = struct.unpack_from('<Q', data, optional + 24)[0]
    count = struct.unpack_from('<H', data, pe + 6)[0]
    table = optional + struct.unpack_from('<H', data, pe + 20)[0]
    sections = [struct.unpack_from('<IIII', data, table + 40 * i + 8) for i in range(count)]

    def raw(rva):
        return next(offset + rva - start for _, start, size, offset in sections if start <= rva < start + size)

    def pointer(rva):
        return struct.unpack_from('<Q', data, raw(rva))[0] - image_base

    def string(rva):
        return data[raw(rva):].split(b'\0', 1)[0].decode('ascii')

    params = 0x0B6BDC50
    assert string(pointer(params + 24)) == 'NegativeEffects'
    properties = pointer(params + 32)
    packed = struct.unpack_from('<HHHH', data, raw(params + 40))
    assert packed == (8, 8, 1, 0), packed  # property count, native size, alignment
    members = []
    for index, expected in enumerate(MEMBERS):
        prop = pointer(properties + 8 * index)
        name = string(pointer(prop))
        assert name == expected
        setter = pointer(prop + 56)
        expected_store = bytes([0xc6, 0x01, 1, 0xc3]) if index == 0 else bytes([0xc6, 0x41, index, 1, 0xc3])
        assert data[raw(setter):raw(setter) + len(expected_store)] == expected_store
        members.append(dict(slot=index + 1, mask=1 << index, native_name=name, storage_offset=index))

    serializer = data[raw(0x05493300):raw(0x054936bf)]
    positions = [serializer.index(b'\x88\x07')]
    positions += [serializer.index(bytes([0x88, 0x47, i])) for i in range(1, 8)]
    assert positions == sorted(positions), 'Serializer order differs from native property offsets'
    assert serializer.count(b'\x48\x83\x00\x04') == 8, 'Expected eight four-byte read advances'
    return dict(binary_sha256=EXPECTED_SHA256, binary_bytes=len(data), struct_name='FNegativeEffects',
                serializer_rva='0x05493300', serialized_boolean_bits=32, members=members)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = verify(args.binary)
    rendered = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding='utf-8')
    print(rendered)
