import struct
import matplotlib.pyplot as plt
import numpy as np

# METADATA: Assist Map Resolution for TTS (237)
# Speed | Idx  | Offset | Pointer    | File Offset
# 0kmh  | 0x03 | 0x0C   | 0x0005E1DC | 0x1DC
# 15kmh | 0x06 | 0x18   | 0x0005E248 | 0x248
# 50kmh | 0x09 | 0x24   | 0x0005E2B4 | 0x2B4
# 100km | 0x0C | 0x30   | 0x0005E320 | 0x320
# 250km | 0x0F | 0x3C   | 0x0005E38C | 0x38C
# Fallbk| 0x12 | 0x48   | 0x0005E3F8 | 0x3F8

def interpolate(x_points, y_points, x_val):
    return np.interp(x_val, x_points, y_points)

def read_assist_curve(f, offset):
    f.seek(offset)
    count = struct.unpack('<H', f.read(2))[0]
    if count > 12: return None, None
    x_axis = struct.unpack(f'<{count}H', f.read(2 * count))
    # NO PADDING BETWEEN X AND Y
    y_axis = struct.unpack(f'<{count}H', f.read(2 * count))
    x_scaled = [x / 128.0 for x in x_axis]
    y_scaled = [y / 100.0 for y in y_axis]
    return x_scaled, y_scaled

# TTS 237 (tt_dataset_237.bin)
path = 'datasets/tt/tt_dataset_237.bin'
hca_cmd_nm = 3.0
scalar = 115.0 / 128.0  # From 0x63A (0x73 73)

# HCA Gain (Mode 1 - 0x5D4) - Pointer at 0xFC (Idx 63)
hca_gain_x = [0, 11, 40, 83, 150, 250]
hca_gain_y = [53/128, 84/128, 117/128, 135/128, 150/128, 166/128]

# Assist Speed Breakpoints
assist_speeds = [0, 15, 50, 100, 250]
assist_ptr_table_offsets = [0x0c, 0x18, 0x24, 0x30, 0x3c]

with open(path, 'rb') as f:
    print("--- TTS (237) RESOLVED OFFSETS ---")
    assist_curves = []
    for speed, tbl_off in zip(assist_speeds, assist_ptr_table_offsets):
        f.seek(tbl_off)
        ptr = struct.unpack('<I', f.read(4))[0]
        file_offset = ptr - 0x5e000
        print(f"Speed {speed:3} km/h: Ptr Index {tbl_off//4:02X}, Ptr {ptr:08X}, File Offset {file_offset:03X}")
        x, y = read_assist_curve(f, file_offset)
        assist_curves.append((x, y))
    print("-----------------------------------")

# Calculate authority for speed range 0-250
plot_speeds = np.linspace(0, 250, 251)
total_motor_torques = []

for speed in plot_speeds:
    # 1. Scaled HCA Gain
    gain = interpolate(hca_gain_x, hca_gain_y, speed)
    hca_virtual_input = hca_cmd_nm * gain * scalar
    
    # 2. Interpolate assist for this virtual input across the speed groups
    curve_assists = []
    for x_curve, y_curve in assist_curves:
        assist = interpolate(x_curve, y_curve, hca_virtual_input)
        curve_assists.append(assist)
        
    # 3. Interpolate between the resulting assists based on speed
    final_assist = interpolate(assist_speeds, curve_assists, speed)
    
    # 4. Total motor torque = Virtual HCA Torque + Resulting Assist
    total_motor_torques.append(hca_virtual_input + final_assist)

plt.figure(figsize=(10, 6))
plt.plot(plot_speeds, total_motor_torques, 'r-', linewidth=2, label='TTS (237) - 3Nm Command')
plt.title('Max Authority: TTS (237) - Total Motor Torque at 3Nm HCA Command')
plt.xlabel('Vehicle Speed (km/h)')
plt.ylabel('Resultant Motor Torque (Nm)')
plt.grid(True, which='both', linestyle='--', alpha=0.7)
plt.axhline(y=0, color='k', linestyle='-', alpha=0.3)
plt.ylim(0, max(total_motor_torques) * 1.2)
plt.legend()

plt.savefig('max_authority_tts_237_detailed.png')
print("Plot saved as max_authority_tts_237_detailed.png")
