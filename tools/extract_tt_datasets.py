import os
import struct

def read_hca_mode1(data):
    offset = 0x5D4
    count = struct.unpack('<H', data[offset:offset+2])[0]
    speeds = list(data[offset+2:offset+2+count])
    # gains are also 1 byte each based on the data
    gains = list(data[offset+2+count:offset+2+count+count])
    return {"x": speeds, "y": gains}

def read_assist_maps(data):
    maps = []
    i = 0
    while i < len(data) - 34 and len(maps) < 6:
        count = struct.unpack('<H', data[i:i+2])[0]
        if count == 8:
            x = list(struct.unpack('<8H', data[i+2:i+18]))
            y = list(struct.unpack('<8H', data[i+18:i+34]))
            if x[0] == 0 and y[0] == 0 and x[-1] > 100 and y[-1] > 100:
                if all(x[j] <= x[j+1] for j in range(7)) and all(y[j] <= y[j+1] for j in range(7)):
                    maps.append({"x": x, "y": y})
                    i += 34
                    continue
        i += 2
    return maps

def extract_dataset(filepath):
    with open(filepath, 'rb') as f:
        data = f.read()

    assist_bp_speeds = list(data[0x7A8:0x7A8+5])
    hca_mode1 = read_hca_mode1(data)
    assist_maps = read_assist_maps(data)
    
    return {
        "assist_bp_speeds": assist_bp_speeds,
        "hca_mode1": hca_mode1,
        "assist_maps": assist_maps,
        "adas_scalar": 20
    }

if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    datasets_dir = os.path.join(base_dir, 'refs', 'datasets')
    
    datasets = {}
    for fw in ['237', '239', '241']:
        path = os.path.join(datasets_dir, f'tt_dataset_{fw}.bin')
        if os.path.exists(path):
            datasets[fw] = extract_dataset(path)
            
    # output nicely to datasets.py format instead of one line
    print("DATASETS = {")
    for k, v in datasets.items():
        print(f'  "{k}": {{')
        print(f'    "assist_bp_speeds": {v["assist_bp_speeds"]},')
        print(f'    "hca_mode1": {v["hca_mode1"]},')
        print(f'    "assist_maps": {v["assist_maps"]},')
        print(f'    "adas_scalar": 20')
        print("  },")
    print("}")
