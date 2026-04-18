import numpy as np

try:
  from opendbc.car.volkswagen.datasets import DATASETS
except ImportError:
  DATASETS = {}

HCA_CMD_MAX = 300.0  # CAN counts, 100 counts = 1.0 Nm → 3.0 Nm max


def _get_dataset_context(dataset_name: str, v_ego_kph: float):
  """
  Shared evaluation context for the HCA pipeline.
  Returns (hca_virtual_input, evaluate_assist_fn) or None if dataset missing.

  The HCA virtual input is the scaled HCA torque in assist-map X units (128 counts/Nm).
  Pipeline: HCA_CAN_cmd → Nm → gain scaling → ADAS scalar → assist-map input.

  Total motor torque = hca_virtual_input + assist(hca_virtual_input)
  (The HCA virtual torque itself contributes to the motor output, plus the assist maps
  provide additional speed-interpolated assist on top.)
  """
  if dataset_name not in DATASETS:
    return None

  ds = DATASETS[dataset_name]
  assist_bp_speeds = np.array(ds["assist_bp_speeds"], dtype=float)
  assist_maps = ds["assist_maps"]
  gain_speed_x = np.array(ds["hca_mode1"]["x"], dtype=float)
  gain_speed_y = np.array(ds["hca_mode1"]["y"], dtype=float)
  adas_scalar = float(ds.get("adas_scalar", 115.0))

  # Ensure constraints
  v_ego_kph_assist = float(np.clip(v_ego_kph, assist_bp_speeds[0], assist_bp_speeds[-1]))
  v_ego_kph_gain = float(np.clip(v_ego_kph, gain_speed_x[0], gain_speed_x[-1]))

  # 1. Evaluate Mode 1 Gain based on 6-point speed axis (raw fixed-point, 128 = 1.0x)
  mode1_gain = float(np.interp(v_ego_kph_gain, gain_speed_x, gain_speed_y))

  # 2. Evaluate Assist Map based on 5-point assist speed axis
  idx = np.searchsorted(assist_bp_speeds, v_ego_kph_assist, side='right') - 1
  idx = int(np.clip(idx, 0, len(assist_bp_speeds) - 2))
  v_low, v_high = assist_bp_speeds[idx], assist_bp_speeds[idx + 1]
  map_low, map_high = assist_maps[idx], assist_maps[idx + 1]

  frac = (v_ego_kph_assist - v_low) / (v_high - v_low) if v_high > v_low else 0.0

  def evaluate_assist(x_in):
      """Evaluate speed-interpolated assist map. X in 128 counts/Nm, Y in 100 counts/Nm."""
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

  # HCA virtual input in assist-map X units (128 counts/Nm):
  #   HCA_cmd_nm = HCA_CAN / 100  (CAN uses 100 counts/Nm)
  #   hca_virtual_nm = HCA_cmd_nm * (gain / 128) * (adas_scalar / 128)
  #   hca_virtual_counts = hca_virtual_nm * 128 = HCA_CAN * gain * adas_scalar / (100 * 128)
  #
  # We compute a per-CAN-count multiplier so callers can scale by any HCA command:
  hca_per_can_count = mode1_gain * adas_scalar / (100.0 * 128.0)

  return hca_per_can_count, evaluate_assist


def _forward_total_motor_torque(hca_can_cmd: float, hca_per_can_count: float, evaluate_assist) -> float:
  """
  Forward pipeline: compute total motor torque (in 100 counts/Nm) from an HCA CAN command.

  Total Motor Torque = HCA virtual input + Assist(HCA virtual input)

  The HCA virtual input is the scaled HCA command that feeds into the assist maps.
  The assist maps produce additional motor assistance on top of the HCA input.
  Both contribute to the total motor output.

  Returns total motor torque in assist-map Y units (100 counts/Nm).
  """
  # HCA virtual input in assist-map X units (128 counts/Nm)
  hca_virtual_counts = hca_can_cmd * hca_per_can_count

  # Assist map output (100 counts/Nm)
  assist_motor = evaluate_assist(hca_virtual_counts)

  # Convert HCA virtual input from 128 counts/Nm to 100 counts/Nm for summation
  hca_virtual_motor = hca_virtual_counts * (100.0 / 128.0)

  # Total motor torque = HCA component + assist component (both in 100 counts/Nm)
  return hca_virtual_motor + assist_motor


def compute_max_motor_torque(dataset_name: str, v_ego_kph: float) -> float:
  """
  Compute the maximum motor torque (in 100 counts/Nm) achievable
  at a given speed when commanding HCA_CMD_MAX (300 CAN = 3.0 Nm).

  Total Motor Torque = HCA virtual input + Assist(HCA virtual input)

  Returns the total motor torque in counts (100 = 1.0 Nm), or 0.0 if unavailable.
  """
  ctx = _get_dataset_context(dataset_name, v_ego_kph)
  if ctx is None:
    return 0.0

  hca_per_can_count, evaluate_assist = ctx
  return _forward_total_motor_torque(HCA_CMD_MAX, hca_per_can_count, evaluate_assist)


def compute_smart_hca_target_torque(dataset_name: str, target_fractional_torque: float, v_ego_kph: float, hca_baseline_torque: float = 160.0) -> float:
  """
  Inverse Feedforward Lateral Torque Controller based on HCA 7 pipeline.
  Takes openpilot's desired fractional torque and models the required HCA CAN request
  to produce equivalent rack torque using the PQ/MQB dataset assist maps.

  The hca_baseline_torque anchors equalization: a fractional request of X always
  targets X * hca_baseline_torque total motor counts (100/Nm), regardless of speed.
  The HCA CAN command is whatever the inverse pipeline requires to achieve that
  total motor torque at the current speed.

  Total motor torque = HCA_virtual + Assist(HCA_virtual), and we invert this
  to find the HCA CAN command for our desired total.
  """
  ctx = _get_dataset_context(dataset_name, v_ego_kph)
  if ctx is None:
    return target_fractional_torque

  hca_per_can_count, evaluate_assist = ctx

  if hca_per_can_count <= 0.0:
    return 0.0

  # Desired total motor torque (100 counts/Nm) anchored to equalization baseline
  desired_total_motor = hca_baseline_torque * abs(target_fractional_torque)

  # Build forward mapping: HCA CAN command → total motor torque
  # Sweep HCA CAN commands from 0 to beyond max to create monotonic search space
  hca_sweep = np.linspace(0, HCA_CMD_MAX * 1.5, 100)
  total_sweep = np.array([_forward_total_motor_torque(h, hca_per_can_count, evaluate_assist) for h in hca_sweep])

  # Reverse interpolate: find HCA CAN command that produces desired total motor torque
  required_hca_cmd = float(np.interp(desired_total_motor, total_sweep, hca_sweep))

  # Normalize output back to [-1.0, 1.0] relative to max HCA CAN command
  normalized_output = float(required_hca_cmd / HCA_CMD_MAX)
  normalized_output = min(1.0, max(0.0, normalized_output))

  return float(-normalized_output if target_fractional_torque < 0 else normalized_output)
