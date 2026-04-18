# MQB/PQ Steering Dataset & HCA 7 Torque Pipeline

This document defines the binary layout and mathematical logic for steering rack datasets. Use this as the ground truth for building map-based torque controllers.

---

## 1. Binary Structure & Addressing
*   **Format:** 4096-byte blob.
*   **Header:** Pointer Table from `0x000` to `0x1CF` (32-bit Little Endian pointers).
*   **Base Address:** `0x5E000`.
*   **File Offset:** `PointerValue - 0x5E000`.

---

## 2. Mathematical Scaling
| Parameter | Bits | Raw Scaling | Physical Unit |
| :--- | :---: | :--- | :--- |
| **Vehicle Speed** | 8 | 1 count = 1 km/h | `km/h` |
| **Input Torque (X)** | 16 | 128 counts = 1.0 Nm | `Nm (Pinion)` |
| **Motor Assist (Y)** | 16 | 100 counts = 1.0 Nm | `Nm (Motor help)` |
| **HCA/Global Gains** | 8/16 | 128 counts = 1.0x | `Multiplier` |

---

## 3. Primary Data Mappings (Standard 3501/3001)

### 3.1 HCA Pre-scaling
Before your HCA command enters the assist logic, it is scaled by these two parameters:
1.  **Global ADAS Scalar (16-bit):** Pointer `0x3A` (Word at `0x63A`). Usually ~30,000 (effectively 1.0x - 1.2x).
2.  **HCA Speed Gain (8-bit, 6 Points):** Pointer `0x3F`. 
    *   **X (Speed km/h):** `[0, 11, 40, 83, 150, 250]`
    *   **Y (Multiplier):** Scaling 128 = 1.0x.

$$T_{virtual\_input} = HCA_{cmd} \cdot \left( \frac{Scalar}{128} \right) \cdot \left( \frac{Gain_{speed}(Speed)}{128} \right)$$

### 3.2 Assist Map Bundle (16-bit, 8 Points)
There are 6 groups of assist curves. Each group contains 3 identical maps (one per driving mode). 
The rack **linearly interpolates** between these 6 speeds based on vehicle speed.

| Speed (km/h) | Ptr Index (Mode 1) | Ptr Index (Mode 2) | Ptr Index (Mode 3) |
| :--- | :---: | :---: | :---: |
| **0** | `0x03` | `0x04` | `0x05` |
| **11** | `0x06` | `0x07` | `0x08` |
| **40** | `0x09` | `0x0A` | `0x0B` |
| **83** | `0x0C` | `0x0D` | `0x0E` |
| **150** | `0x0F` | `0x10` | `0x11` |
| **250** | `0x12` | `0x13` | `0x14` |

---

## 4. Final Torque Calculation (HCA 7)

To calculate the total force applied to the wheels ($T_{total}$):

1.  **Calculate Virtual Input:** (See Step 3.1).
2.  **Interpolate Assist Maps:** 
    Find the two nearest speed curves $M_{low}$ and $M_{high}$ and interpolate based on current speed to get the active 8-point Assist Curve $M_{current}$.
3.  **Lookup Motor Torque:**
    $$T_{assist} = Lookup(M_{current}, T_{virtual\_input})$$
4.  **Final Sum:**
    $$T_{final} = T_{virtual\_input} + T_{assist}$$

---

## 5. Controller Implementation (Inverse)
To target a specific $T_{target}$ (total Nm at wheels):
1.  Solve for $X$ such that: $X + Assist(X, Speed) = T_{target}$.
2.  Calculate the required HCA command to produce $X$:
    $$HCA_{cmd} = \frac{X \cdot 128 \cdot 128}{Scalar \cdot Gain_{speed}(Speed)}$$
3.  **Safety Saturation:** Ensure your output doesn't exceed the saturation map at Ptr `0x2A`.
