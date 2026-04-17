import numpy as np

DATASETS = {
  "237": {
    "bp_speeds": [0, 11, 40, 83, 150, 250],
    "assist_maps": [{'x': [0, 13, 77, 136, 190, 272, 345, 408], 'y': [0, 57, 410, 934, 1587, 2671, 3652, 4506]}, {'x': [0, 14, 77, 136, 190, 272, 408, 525], 'y': [0, 30, 204, 497, 896, 1602, 2944, 4506]}, {'x': [0, 14, 77, 137, 190, 272, 407, 544], 'y': [0, 14, 102, 247, 437, 866, 1894, 3396]}, {'x': [0, 14, 77, 136, 191, 272, 408, 544], 'y': [0, 10, 67, 135, 239, 485, 1179, 2446]}, {'x': [0, 14, 77, 136, 190, 272, 408, 544], 'y': [0, 6, 31, 57, 92, 188, 518, 1365]}, {'x': [0, 13, 54, 109, 177, 272, 408, 544], 'y': [0, 8, 98, 290, 635, 1321, 2788, 4506]}],
    "hca_speed_gain": {'x': [0, 50, 120], 'y': [79, 129, 147]},
    "adas_scalar": 20,
    "hca_limit": {'x': [0, 12, 69, 192, 476, 1069, 2014, 4123, 7881, 13714], 'y': [0, 14, 100, 248, 424, 580, 720, 900, 1130, 1400]}
  },
  "239": {
    "bp_speeds": [0, 11, 40, 83, 150, 250],
    "assist_maps": [{'x': [0, 13, 77, 136, 190, 272, 345, 417], 'y': [0, 125, 819, 1459, 2048, 3004, 4002, 5120]}, {'x': [0, 14, 77, 136, 190, 272, 408, 540], 'y': [0, 49, 267, 543, 844, 1440, 2867, 4706]}, {'x': [0, 14, 77, 137, 190, 272, 407, 544], 'y': [0, 14, 101, 234, 407, 852, 1857, 3887]}, {'x': [0, 14, 77, 136, 191, 272, 408, 544], 'y': [0, 5, 62, 120, 226, 492, 1192, 3441]}, {'x': [0, 14, 77, 136, 190, 272, 408, 544], 'y': [0, 6, 33, 57, 88, 188, 533, 3025]}, {'x': [0, 13, 54, 109, 177, 272, 408, 544], 'y': [0, 8, 98, 290, 635, 1321, 2788, 4506]}],
    "hca_speed_gain": {'x': [0, 50, 120], 'y': [72, 128, 132]},
    "adas_scalar": 20,
    "hca_limit": {'x': [0, 12, 58, 192, 476, 1069, 2014, 4123, 7881, 13714], 'y': [0, 6, 70, 274, 450, 608, 736, 910, 1130, 1400]}
  },
  "241": {
    "bp_speeds": [0, 11, 40, 83, 150, 250],
    "assist_maps": [{'x': [0, 13, 77, 136, 190, 272, 345, 408], 'y': [0, 57, 410, 934, 1587, 2671, 3652, 4506]}, {'x': [0, 14, 77, 136, 190, 272, 408, 525], 'y': [0, 30, 204, 497, 896, 1602, 2944, 4506]}, {'x': [0, 14, 77, 137, 190, 272, 407, 544], 'y': [0, 14, 102, 247, 437, 866, 1894, 3396]}, {'x': [0, 14, 77, 136, 191, 272, 408, 544], 'y': [0, 10, 67, 135, 239, 485, 1179, 2446]}, {'x': [0, 14, 77, 136, 190, 272, 408, 544], 'y': [0, 6, 31, 57, 92, 188, 518, 1365]}, {'x': [0, 13, 54, 109, 177, 272, 408, 544], 'y': [0, 8, 98, 290, 635, 1321, 2788, 4506]}],
    "hca_speed_gain": {'x': [0, 50, 120], 'y': [79, 129, 147]},
    "adas_scalar": 20,
    "hca_limit": {'x': [0, 12, 69, 192, 476, 1069, 2014, 4123, 7881, 13714], 'y': [0, 14, 100, 248, 424, 580, 720, 900, 1130, 1400]}
  },
}


def compute_smart_hca_target_torque(dataset_name: str, target_fractional_torque: float, v_ego_kph: float) -> float:
  """
  Leverages standard HCA gain/steer maps to compute improved output torque.
  Uses reverse-interpolation:
  T_target = normalized_pid * T_target_MAX
  Wait, the input is `target_fractional_torque` ranging from [-1.0, 1.0].
  We want to figure out what maximum Rack Torque we can create with HCA_cmd = +/- 300,
  then scale the fractional torque to the target Rack Torque. Then reverse interpolate
  into the necessary HCA_cmd to produce this Rack Torque.
  Then output HCA_cmd / 300 to rescale to normalized controller output [-1.0, 1.0].
  """
  if dataset_name not in DATASETS:
    return target_fractional_torque
    
  ds = DATASETS[dataset_name]
  bp_speeds = ds["bp_speeds"]
  assist_maps = ds["assist_maps"]
  gain_speed_x = np.array(ds["hca_speed_gain"]["x"])
  gain_speed_y = np.array(ds["hca_speed_gain"]["y"])
  adas_scalar = ds["adas_scalar"]
  
  # Math precision / type conversion sanity
  v_ego_kph_clipped = float(np.clip(v_ego_kph, bp_speeds[0], bp_speeds[-1]))
  
  # Map lookup
  idx = np.searchsorted(bp_speeds, v_ego_kph_clipped, side='right') - 1
  idx = int(np.clip(idx, 0, len(bp_speeds) - 2))
  v_low, v_high = bp_speeds[idx], bp_speeds[idx + 1]
  map_low, map_high = assist_maps[idx], assist_maps[idx + 1]
  
  frac = (v_ego_kph_clipped - v_low) / (v_high - v_low) if v_high > v_low else 0.0
  
  def evaluate_assist(x_in):
      # Helper to interpolate assist torque at current speed for a given raw Input Torque
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
      
  # 1. Determine Gain_speed and Total Input Multiplier
  gain_speed = float(np.interp(v_ego_kph_clipped, gain_speed_x, gain_speed_y))
  
  # Equation: X = HCA_cmd * (gain_speed / 128) * (adas_scalar / 128)
  # X is effective input torque (raw 1/128 Nm)
  # T_target = X + Assist(X)
  # Let's find MAX possible Rack Torque using HCA_cmd = 300
  hca_cmd_max = 300.0
  x_max = hca_cmd_max * (gain_speed / 128.0) * (adas_scalar / 128.0)
  t_rack_max = x_max + evaluate_assist(x_max)
  
  # Scale openpilot pid fractional request by maximum available rack torque
  # So that at 1.0, we request t_rack_max
  t_rack_target = t_rack_max * abs(target_fractional_torque)
  
  # Reverse interpolation: Find X corresponding to t_rack_target
  # Create a monotonic sequence of (X + Assist(X)) over a reasonable domain
  seq_x = np.linspace(0, x_max * 1.5, 100)
  seq_total = np.zeros_like(seq_x)
  for i, sx in enumerate(seq_x):
      seq_total[i] = sx + evaluate_assist(sx)
      
  # Reverse interp to find required X
  required_x = np.interp(t_rack_target, seq_total, seq_x)
  
  # Solve back for needed HCA_cmd
  multiplier = (gain_speed / 128.0) * (adas_scalar / 128.0)
  required_hca = required_x / multiplier if multiplier > 0 else 0.0
  
  # Output the new normalized output torque (which represents desired HCA_cmd scaled)
  normalized_output = required_hca / hca_cmd_max
  
  return float(-normalized_output if target_fractional_torque < 0 else normalized_output)
