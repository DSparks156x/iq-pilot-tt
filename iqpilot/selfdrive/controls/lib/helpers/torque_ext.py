"""
Copyright © IQ.Lvbs, apart of Project Teal Lvbs, All Rights Reserved, licensed under https://konn3kt.com/tos
"""

from openpilot.iqpilot.selfdrive.controls.lib.neural_network_feed_forward.nnff import NeuralNetworkFeedForward
from openpilot.iqpilot.selfdrive.controls.lib.helpers.torque_override import LatControlTorqueExtOverride
from openpilot.common.params import Params
from opendbc.car.common.conversions import Conversions as CV

try:
  from openpilot.iqpilot.selfdrive.controls.lib.bettertorquecontroller import compute_smart_hca_target_torque, compute_max_motor_torque
  from opendbc.car.volkswagen.values import VolkswagenFlags
except ImportError:
  compute_smart_hca_target_torque = None
  compute_max_motor_torque = None


class LatControlTorqueExt(NeuralNetworkFeedForward, LatControlTorqueExtOverride):
  def __init__(self, lac_torque, CP, CP_IQ, CI):
    NeuralNetworkFeedForward.__init__(self, lac_torque, CP, CP_IQ, CI)
    LatControlTorqueExtOverride.__init__(self, lac_torque, CP)
    self._params = Params()
    self._smart_hca_enabled = self._params.get_bool("HcaMapTorqueController")
    self._frame = 0
    self._hca_baseline_torque = 1113.0

    if compute_smart_hca_target_torque and hasattr(self, 'CP') and self.CP is not None:
      try:
        from opendbc.car.volkswagen.values import CAR
        for c in CAR:
          if c.value == self.CP.carFingerprint:
            if hasattr(c.config.specs, 'hcaBaselineTorque'):
              self._hca_baseline_torque = c.config.specs.hcaBaselineTorque
            break
      except Exception:
        pass

    if compute_smart_hca_target_torque is None:
      print("HCA_DEBUG: compute_smart_hca_target_torque is NONE (Import Error)")
    else:
      print("HCA_DEBUG: bettertorquecontroller imported successfully")

  def _is_smart_hca_active(self):
    """Check if smart HCA remapping should be active for this vehicle."""
    if not self._smart_hca_enabled or compute_smart_hca_target_torque is None:
      return False
    tt_flag = getattr(VolkswagenFlags, 'TT_DATASET_237', None)
    active = tt_flag is not None and bool(self.CP.flags & tt_flag)
    if self._frame % 100 == 0:
      print(f"HCA_DEBUG: smart_hca_enabled={self._smart_hca_enabled}, tt_flag_exists={tt_flag is not None}, has_flag={bool(self.CP.flags & tt_flag) if tt_flag else 'N/A'}")
    return active

  def update_steer_max(self, v_ego):
    """
    Pre-PID hook: update the controller's steer_max based on the maximum achievable
    motor torque at the current speed. This tells the PID how much authority it
    actually has — steer_max varies because max motor torque from HCA=300 varies by speed.

    steer_max = max_motor_torque(speed) / baseline

    Returns True if steer_max was updated (caller should call update_limits).
    """
    if not self._is_smart_hca_active() or compute_max_motor_torque is None:
      return False

    kph = v_ego * CV.MS_TO_KPH
    max_motor = compute_max_motor_torque("237", kph)
    if max_motor > 0 and self._hca_baseline_torque > 0:
      new_steer_max = float(max_motor / self._hca_baseline_torque)
      new_steer_max = max(0.1, new_steer_max)  # safety floor
      self._controller.steer_max = new_steer_max
      return True
    return False

  def _snapshot_cycle(self,
                      feedforward_seed,
                      pid_core,
                      pid_trace,
                      torque_goal,
                      torque_actual,
                      roll_bias,
                      deadzone,
                      lat_accel_goal,
                      lat_accel_actual,
                      curvature_goal,
                      curvature_actual,
                      gravity_lat_accel,
                      safety_limited,
                      torque_output) -> None:
    self._ff = feedforward_seed
    self._pid = pid_core
    self._pid_log = pid_trace
    self._setpoint = torque_goal
    self._measurement = torque_actual
    self._roll_compensation = roll_bias
    self._lateral_accel_deadzone = deadzone
    self._desired_lateral_accel = lat_accel_goal
    self._actual_lateral_accel = lat_accel_actual
    self._desired_curvature = curvature_goal
    self._actual_curvature = curvature_actual
    self._gravity_adjusted_lateral_accel = gravity_lat_accel
    self._steer_limited_by_safety = safety_limited
    self._output_torque = torque_output

  def update(self,
             car_state,
             vehicle_model,
             pid_core,
             calibrator,
             feedforward_seed,
             pid_trace,
             torque_goal,
             torque_actual,
             calibrated_pose,
             roll_bias,
             lat_accel_goal,
             lat_accel_actual,
             deadzone,
             gravity_lat_accel,
             curvature_goal,
             curvature_actual,
             safety_limited,
             torque_output):
    self._snapshot_cycle(
      feedforward_seed,
      pid_core,
      pid_trace,
      torque_goal,
      torque_actual,
      roll_bias,
      deadzone,
      lat_accel_goal,
      lat_accel_actual,
      curvature_goal,
      curvature_actual,
      gravity_lat_accel,
      safety_limited,
      torque_output,
    )
    self.update_calculations(car_state, vehicle_model, lat_accel_goal)
    self.update_neural_network_feedforward(car_state, calibrator, calibrated_pose)
    self._output_torque = self.update_nav_torque_nudge(True, car_state, self._output_torque)

    # Periodic toggle re-read
    if self._frame % 100 == 0:
      self._smart_hca_enabled = self._params.get_bool("HcaMapTorqueController")
    self._frame += 1

    # Smart HCA remap: convert fractional torque through the inverse HCA pipeline
    # so that equal fractional authority produces equal physical motor torque at all speeds
    if self._is_smart_hca_active():
      pre_remap = self._output_torque
      kph = car_state.vEgo * CV.MS_TO_KPH
      self._output_torque = compute_smart_hca_target_torque(
        "237", self._output_torque, kph, self._hca_baseline_torque)
      if self._frame % 100 == 0:
        print(f"HCA_DEBUG: REMAP ACTIVE | v_ego={kph:.1f}kph | pre={pre_remap:.4f} | post={self._output_torque:.4f} | baseline={self._hca_baseline_torque}")

    return self._pid_log, self._output_torque
