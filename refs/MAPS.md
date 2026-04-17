# MQB Steering Dataset & HCA 7 Torque Control Documentation

This document describes the binary structure of the steering rack datasets (4KB files) for the VW MQB platform and the mathematical pipeline used by the firmware to process Heading Control Assistant (HCA) commands.

---

## 1. Dataset Binary Structure

The dataset is a **4096-byte** binary blob. It consists of a pointer table at the beginning, followed by raw map data.

### 1.1 Pointer Table
*   **Offset:** `0x000` to `0x1CF`.
*   **Format:** Array of `uint32_t` absolute addresses (Little Endian).
*   **Addressing:** The firmware expects the dataset to be mapped at base address `0x5E000`.
*   **File Offset Calculation:** `FileOffset = PointerValue - 0x5E000`.

### 1.2 Map Header & Data Format (1D Lookup Table)
Every map in the dataset follows this standard structure:

| Offset | Field | Type | Description |
| :--- | :--- | :--- | :--- |
| `+0x00` | **Point Count** | `uint16_t` | Number of points in the map ($N$). |
| `+0x02` | **X-Axis** | `uint16_t[N]` | Input values (e.g., Torque, Speed). Must be strictly increasing. |
| `+0x02 + 2*N` | **Y-Axis** | `int16_t[N]` | Output values (e.g., Assist Torque, Gain). |

---

## 2. Scaling and Units

The firmware uses fixed-point arithmetic. Use these divisors to convert raw binary values to physical units:

| Parameter | Raw Unit | Physical Scaling | Example |
| :--- | :--- | :--- | :--- |
| **Torque** | 1/128 Nm | `Value / 128.0` | `256 = 2.0 Nm` |
| **Speed** | 1 km/h | `Value / 1.0` | `120 = 120 km/h` |
| **Gain** | 1/128 Ratio | `Value / 128.0` | `128 = 1.0x (Unity)` |

---

## 3. HCA 7 Torque Pipeline (Forward)

In HCA 7 mode, the command is treated as a **Virtual Driver Torque** and is added to the physical driver input *before* the assist curve lookup.

### Step 1: Pre-scaling the HCA Command
The raw HCA command from CAN ($HCA_{raw}$) is multiplied by two multipliers from the dataset:
1.  **HCA Speed Gain:** A 3-point map (PtrIdx `0x4B`) that scales authority based on speed.
2.  **Dataset Scalar:** A fixed global gain (typically `0.914`) found at PtrIdx `0x3A`.

$$T_{hca\_eff} = HCA_{raw} \cdot \left( \frac{Gain_{speed}(Speed)}{128} \right) \cdot \left( \frac{Gain_{dataset}}{128} \right)$$

### Step 2: Total Effective Torque
$$T_{input} = T_{driver\_physical} + T_{hca\_eff}$$

### Step 3: Assist Map Lookup
The motor assist is looked up using $T_{input}$ and vehicle speed. The firmware interpolates between the two nearest speed-dependent 8-point maps.

$$T_{assist} = Interpolate\_Speed(AssistMap[V_{low}], AssistMap[V_{high}], Speed, T_{input})$$

### Step 4: Final Rack Torque
The total torque applied to the tie rods is the sum of the input and the motor's assistance.
$$T_{final} = T_{input} + T_{assist}$$

---

## 4. Inverse Pipeline (Controller Strategy)

To achieve a target **Final Rack Torque** ($T_{target}$) using HCA (assuming hands-off, $T_{driver} = 0$):

1.  **Find Effective Torque ($X$):**
    Solve for $X$ in the equation: $X + AssistMap(X, Speed) = T_{target}$.
    *Implementation:* Create a "Total Torque" curve where $Y' = X + Assist(X)$. Perform a reverse interpolation on this $Y'$ curve to find $X$.

2.  **Calculate Required HCA Command:**
    $$HCA_{cmd} = \frac{X \cdot 128 \cdot 128}{Gain_{speed}(Speed) \cdot Gain_{dataset}}$$

## 5. Primary Map Locations (Audi TT Series)

These indices are standard for the `3501` firmware datasets:

### 5.1 Assist Curves (8-point, 16-bit)
There are 18 maps arranged in speed groups. Each group contains 3 maps (one per driving mode: Normal, Sport, Comfort). In TT datasets, all three maps in a group are typically identical.

| Vehicle Speed | Ptr Index (Mode 1) | Ptr Index (Mode 2) | Ptr Index (Mode 3) |
| :--- | :---: | :---: | :---: |
| **0 km/h** | `0x03` | `0x04` | `0x05` |
| **11 km/h** | `0x06` | `0x07` | `0x08` |
| **40 km/h** | `0x09` | `0x0A` | `0x0B` |
| **83 km/h** | `0x0C` | `0x0D` | `0x0E` |
| **150 km/h** | `0x0F` | `0x10` | `0x11` |
| **250 km/h** | `0x12` | `0x13` | `0x14` |

### 5.2 Control & Limit Maps
| Function | Ptr Index | File Offset | Type | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Assist Speed BP** | `0x3F` | `0x5D4` | 8-bit | X-axis for speed interpolation. |
| **HCA Speed Gain** | `0x4B` | `0x640` | 8-bit | X: [0, 50, 120] km/h. Scales HCA input. |
| **ADAS Scalar** | `0x3A` | `0x63A` | Scalar | Global multiplier (typically `117`). |
| **HCA Limit** | `0x2A` | `0x490` | 16-bit | 10-point saturation map for HCA torque. |

---

## 6. Extraction Reference (Python Snippet)
```python
# To find Ptr Index 0x03 (Assist 0kmh):
ptr_addr = struct.unpack('<I', data[0x03*4 : 0x03*4 + 4])[0]
offset = ptr_addr - 0x5E000
count = struct.unpack('<H', data[offset : offset+2])[0]
# X-axis follows at offset+2, Y-axis follows at offset+2+(2*count)
```
