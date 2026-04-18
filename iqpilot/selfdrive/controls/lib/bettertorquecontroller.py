import numpy as np

try:
  from opendbc.car.volkswagen.datasets import DATASETS
except ImportError:
  DATASETS = {}

def compute_smart_hca_target_torque(dataset_name: str, target_fractional_torque: float, v_ego_kph: float, hca_baseline_torque: float = 160.0) -> float:
  """
  Inverse Feedforward Lateral Torque Controller based on HCA 7 pipeline.
  Takes openpilot's desired fractional torque and models the required HCA CAN request
  to produce equivalent rack torque using the PQ/MQB dataset assist maps.
  """
  if dataset_name not in DATASETS:
    return target_fractional_torque
    
  ds = DATASETS[dataset_name]
  assist_bp_speeds = np.array(ds["assist_bp_speeds"], dtype=float)
  assist_maps = ds["assist_maps"]
  gain_speed_x = np.array(ds["hca_mode1"]["x"], dtype=float)
  gain_speed_y = np.array(ds["hca_mode1"]["y"], dtype=float)
  adas_scalar = float(ds.get("adas_scalar", 20.0))
  
  # Ensure constraints
  v_ego_kph_assist = float(np.clip(v_ego_kph, assist_bp_speeds[0], assist_bp_speeds[-1]))
  v_ego_kph_gain = float(np.clip(v_ego_kph, gain_speed_x[0], gain_speed_x[-1]))
  
  # 1. Evaluate Mode 1 Gain based on 6-point speed axis
  mode1_gain = float(np.interp(v_ego_kph_gain, gain_speed_x, gain_speed_y))
  
  # 2. Evaluate Assist Map based on 5-point assist speed axis
  idx = np.searchsorted(assist_bp_speeds, v_ego_kph_assist, side='right') - 1
  idx = int(np.clip(idx, 0, len(assist_bp_speeds) - 2))
  v_low, v_high = assist_bp_speeds[idx], assist_bp_speeds[idx + 1]
  map_low, map_high = assist_maps[idx], assist_maps[idx + 1]
  
  frac = (v_ego_kph_assist - v_low) / (v_high - v_low) if v_high > v_low else 0.0
  
  def evaluate_assist(x_in):
      x_in = float(abs(x_in))
      if x_in >= max(map_low["x"]):
          y_low = map_low["y"][-1]
      else:
          y_low = np.interp(x_in, map_low["x"], map_low["y"])
          
      if x_in >= max(map_high["x"]):
          y_high = map_high["y"][-1]
      else:
          y_high = np.interp(x_in, map_high["x"], map_high["y"])
      return float(y_low + frac * (y_high - y_low))
      
  # 3. Model Assist Motor Torque Reverse Pipeline:
  # The Lateral Toruqe Controller output fundamentally expects a perfectly linear correlation frame.
  # If we scale our mapping bounds to the fluctuating live speed max_motor_torque, a 0.20 fractional
  # request yields highly variable true physical torque.
  # Thus, we anchor our 100% boundary mathematically against the absolute maximum global force
  # available (at 0 Kph) and saturate safely using the live variables downstream.
  
  hca_cmd_max = 300.0
  live_multiplier = (mode1_gain / 128.0) * (adas_scalar / 128.0)
  
  if live_multiplier <= 0.0:
      return 0.0
      
  live_max_hca_postgain = hca_cmd_max * live_multiplier
  
  # Calculate GLOBAL EQUALIZED MAX MOTOR TORQUE
  # Openpilot relies on a static base parameter to tie fractional torque (0.5) to physical
  # expected Nm outputs so the online learner (torqued) doesn't over-saturate.
  # We expose this baseline here. 
  # Motor Torque (Y-Axis in dataset): 100 counts = 1.0 Physical Nm
  # Desired physical motor torque is statically governed against this tuned anchor!
  desired_motor_torque = hca_baseline_torque * abs(target_fractional_torque)
  
  # Create monotonic search space restricting to the LIVE speed's physical assist limits!
  seq_x = np.linspace(0, live_max_hca_postgain * 1.5, 100)
  seq_y = np.zeros_like(seq_x)
  for i, sx in enumerate(seq_x):
      seq_y[i] = evaluate_assist(sx)
      
  # Reverse interpolate required HCA Postgain (X) to achieve Desired Motor Torque (Y)
  required_hca_postgain = np.interp(desired_motor_torque, seq_y, seq_x)
  
  # Math it back to HCA CAN request pre-gain
  required_hca_cmd = required_hca_postgain / live_multiplier
  
  # Normalize output back to [-1.0, 1.0] relative to max HCA command for Openpilot
  normalized_output = float(required_hca_cmd / hca_cmd_max)
  normalized_output = min(1.0, max(0.0, normalized_output))
  
  return float(-normalized_output if target_fractional_torque < 0 else normalized_output)

