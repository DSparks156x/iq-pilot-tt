#!/usr/bin/env python3
"""
Extract TT steering rack dataset binaries into Python dict format for datasets.py.

Binary layout (from newmaps.md):
  - Assist map pointer table starts at offset 0x00, 4-byte LE pointers
    Ptr indices: 0x03 (0kph), 0x06 (15kph), 0x09 (50kph), 0x0C (100kph), 0x0F (250kph), 0x12 (fallback)
  - Each pointer value has base address 0x5E000 subtracted to get file offset
  - Assist curve: ushort count + count*ushort X + count*ushort Y (no padding)
  - Assist breakpoint speeds at offset 0x7A8 (5 bytes, 1 byte each)
  - HCA Mode 1 gain curve at offset 0x5D4: ushort count + count*ushort X + count*ushort Y
  - ADAS scalar at offset 0x63A: ushort (high byte, 128 = 1.0x)
"""

import os
import struct


# Pointer table indices (multiply by 4 for byte offset)
# Maps 6 assist groups: 0kph, 15kph, 50kph, 100kph, 250kph, fallback
ASSIST_PTR_INDICES = [0x03, 0x06, 0x09, 0x0C, 0x0F, 0x12]
ASSIST_PTR_BASE = 0x5E000

# Fixed offsets
ASSIST_BP_SPEEDS_OFFSET = 0x7A8
ASSIST_BP_SPEEDS_COUNT = 5
HCA_MODE1_OFFSET = 0x5D4
ADAS_SCALAR_OFFSET = 0x63A


def read_assist_curve(data, file_offset):
    """Read a single assist curve at the given file offset.
    Format: ushort count, count*ushort X, count*ushort Y (no padding between axes)."""
    count = struct.unpack_from('<H', data, file_offset)[0]
    if count > 12 or count == 0:
        return None
    off = file_offset + 2
    x = list(struct.unpack_from(f'<{count}H', data, off))
    off += 2 * count
    y = list(struct.unpack_from(f'<{count}H', data, off))
    return {"x": x, "y": y}


def read_gain_curve(data, offset):
    """Read a gain curve (HCA Mode 1/2). Format:
    ushort count, count*byte X (speeds in kph), count*byte Y (gains, 128=1.0x)."""
    count = struct.unpack_from('<H', data, offset)[0]
    if count > 12 or count == 0:
        return None
    off = offset + 2
    x = list(data[off:off + count])
    off += count
    y = list(data[off:off + count])
    return {"x": x, "y": y}


def read_adas_scalar(data):
    """Read the ADAS scalar from offset 0x63A. Stored as ushort, 128 = 1.0x."""
    raw = struct.unpack_from('<H', data, ADAS_SCALAR_OFFSET)[0]
    # The scalar is in the low byte (e.g. 0x73 = 115)
    return raw & 0xFF


def extract_dataset(filepath):
    with open(filepath, 'rb') as f:
        data = f.read()

    # 1. Assist breakpoint speeds (5 single-byte values)
    assist_bp_speeds = list(data[ASSIST_BP_SPEEDS_OFFSET:ASSIST_BP_SPEEDS_OFFSET + ASSIST_BP_SPEEDS_COUNT])

    # 2. HCA Mode 1 gain curve
    hca_mode1 = read_gain_curve(data, HCA_MODE1_OFFSET)

    # 3. Assist maps via pointer table
    assist_maps = []
    for ptr_idx in ASSIST_PTR_INDICES:
        ptr_offset = ptr_idx * 4  # each pointer is 4 bytes
        ptr_value = struct.unpack_from('<I', data, ptr_offset)[0]
        file_offset = ptr_value - ASSIST_PTR_BASE
        curve = read_assist_curve(data, file_offset)
        if curve is not None:
            assist_maps.append(curve)

    # 4. ADAS scalar
    adas_scalar = read_adas_scalar(data)

    return {
        "assist_bp_speeds": assist_bp_speeds,
        "hca_mode1": hca_mode1,
        "assist_maps": assist_maps,
        "adas_scalar": adas_scalar,
    }


def format_map(m):
    return f"{{'x': {m['x']}, 'y': {m['y']}}}"


if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    datasets_dir = os.path.join(base_dir, 'refs', 'datasets')

    datasets = {}
    for fw in ['237', '239', '241']:
        path = os.path.join(datasets_dir, f'tt_dataset_{fw}.bin')
        if os.path.exists(path):
            ds = extract_dataset(path)
            datasets[fw] = ds
            print(f"--- Dataset {fw} ---")
            print(f"  Speeds: {ds['assist_bp_speeds']}")
            print(f"  HCA Mode1: {ds['hca_mode1']}")
            print(f"  ADAS Scalar: {ds['adas_scalar']}")
            print(f"  Assist Maps: {len(ds['assist_maps'])} curves")
            for i, m in enumerate(ds['assist_maps']):
                print(f"    [{i}] X={m['x']}")
                print(f"        Y={m['y']}")
            print()

    # Output datasets.py format
    print("=" * 60)
    print("# Paste into opendbc/car/volkswagen/datasets.py")
    print("=" * 60)
    print("DATASETS = {")
    for k, v in datasets.items():
        print(f'  "{k}": {{')
        print(f'    "assist_bp_speeds": {v["assist_bp_speeds"]},')
        print(f'    "hca_mode1": {format_map(v["hca_mode1"])},')
        maps_str = ", ".join(format_map(m) for m in v["assist_maps"])
        print(f'    "assist_maps": [{maps_str}],')
        print(f'    "adas_scalar": {v["adas_scalar"]}')
        print("  },")
    print("}")
