# Verified MQB/PQ Steering Dataset & HCA Maps (V3 - Final)

This document defines the verified binary layout and control logic for steering rack datasets, specifically addressing the differences between HCA 5 (PQ) and HCA 7 (MQB) torque pipelines.

---

## 1. Speed Breakpoint Axes

### 1.1 Assist Map Speed Axis (5-Point)
*   **Offset:** `0x7A8` in the binary.
*   **Points:** `[0, 15, 50, 100, 250]` km/h.
*   **Architecture:** Interpolates between 5 primary map groups. 

### 1.2 HCA Mode 1 (Primary) Speed Axis (6-Point)
*   **Pointer Index:** `0x3F` (Points to Offset `0x5D4`).
*   **Points (Typical):** `[0, 15, 50, 100, 150, 250]` km/h.
*   **Role:** Primary scaling for external HCA CAN torque commands (HCA 7).

### 1.3 HCA Mode 2 (HCA 5) Speed Axis (6-Point)
*   **Pointer Index:** `0x42` (Points to Offset `0x604`).
*   **Points (Typical Golf):** `[0, 7, 21, 51, 101, 250]` km/h.
*   **Points (Typical TTS):** `[0, 2, 20, 70, 125, 250]` km/h.
*   **Role:** Dedicated gain for HCA 5 (PQ-style) internal recentering/damping.

---

## 2. Map Group Architecture

### 2.1 Steering Assist Maps (8-Point Curves)
The rack uses 6 distinct map groups. Group 6 is the fallback for when the speed signal is lost.

| Group | Ptr Index | Speed | Description |
| :---: | :---: | :---: | :--- |
| **1** | `0x03` | 0 km/h | Parking Assist |
| **2** | `0x06` | 15 km/h | Low Speed |
| **3** | `0x09` | 50 km/h | Urban Speed |
| **4** | `0x0C` | 100 km/h | Highway Speed |
| **5** | `0x0F` | 250 km/h | High Speed |
| **6** | `0x12` | **Fallback** | **Speed-Lost Fallback Map** |

**Curve Structure (34 Bytes):**
*   `ushort count` (Always 8)
*   `ushort x_axis[8]` (Pinion Torque, 128 = 1 Nm)
*   `ushort y_axis[8]` (Motor Assist Torque, 100 = 1 Nm)
*   *(No internal padding between axes)*

---

## 3. Mathematical Scaling & Pipeline

| Parameter | Raw Scaling | Physical Unit |
| :--- | :---: | :--- |
| **Input Torque (X)** | 128 counts = 1.0 Nm | `Nm (Pinion Input)` |
| **Motor Assist (Y)** | 100 counts = 1.0 Nm | `Nm (Motor Assistance)` |
| **Vehicle Speed** | 1 count = 1 km/h | `km/h` |
| **HCA/Global Gains** | 128 counts = 1.0x | `Multiplier (Fixed Point)` |

---

## 4. Torque Summation Logic (HCA 5 vs HCA 7)

The final torque demand is the sum of the scaled HCA request and the speed-interpolated assist.

### 4.1 HCA 7 (External Control Mode)
In HCA 7, the rack bypasses the internal Mode 2 recentering logic.
$$T_{hca\_final} = HCA_{can\_cmd} \cdot \left( \frac{Gain_{Mode1}(Speed)}{128} \right) \cdot \left( \frac{Scalar_{ADAS}}{128} \right)$$

### 4.2 HCA 5 (Internal Recentering Mode)
In HCA 5, the rack calculates an internal recentering torque using the Mode 2 Gain.
$$T_{hca\_final} = T_{hca\_external} + \left( T_{internal\_recenter} \cdot \frac{Gain_{Mode2}(Speed)}{128} \right)$$

### 4.3 Final Assist Pipeline
The assist is calculated based on the sum of the driver's physical torque and the HCA active torque.
$$T_{total\_input} = T_{driver} + T_{hca\_final}$$
$$T_{final\_motor\_torque} = Interpolate\_5\_Speed(AssistMaps, Speed, T_{total\_input})$$

---

## 5. Key Findings
*   **HCA 7 Implementation:** If building an inverse controller for HCA 7, **ignore Mode 2 (0x604)**. It is explicitly zeroed in the HCA 7 code path.
*   **TTS Dataset (237):** Features extremely high Mode 2 gains at very low speeds (e.g., 0.86x at 2 km/h), confirming its origin as an HCA 5 performance calibration.
*   **Breakpoint Logic:** The 150 km/h breakpoint is exclusive to the HCA pipelines and does not exist in the primary assist maps.
