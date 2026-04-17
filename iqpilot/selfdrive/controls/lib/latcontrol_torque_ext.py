"""
Copyright © IQ.Lvbs, apart of Project Teal Lvbs, All Rights Reserved, licensed under https://konn3kt.com/tos
"""

from openpilot.iqpilot.selfdrive.controls.lib.nnlc.nnlc import NeuralNetworkLateralControl
from openpilot.iqpilot.selfdrive.controls.lib.latcontrol_torque_ext_override import LatControlTorqueExtOverride
from openpilot.common.params import Params
from openpilot.common.conversions import Conversions as CV

try:
  from opendbc.car.volkswagen.datasets import compute_smart_hca_target_torque
  from opendbc.car.volkswagen.values import VolkswagenFlags
except ImportError:
  compute_smart_hca_target_torque = None


class LatControlTorqueExt(NeuralNetworkLateralControl, LatControlTorqueExtOverride):
  def __init__(self, lac_torque, CP, CP_IQ, CI):
    NeuralNetworkLateralControl.__init__(self, lac_torque, CP, CP_IQ, CI)
    LatControlTorqueExtOverride.__init__(self, CP)
    self._params = Params()
    self._smart_hca_enabled = self._params.get_bool("HcaMapTorqueController")
    self._frame = 0

  def update(self, CS, VM, pid, params, ff, pid_log, setpoint, measurement, calibrated_pose, roll_compensation,
             desired_lateral_accel, actual_lateral_accel, lateral_accel_deadzone, gravity_adjusted_lateral_accel,
             desired_curvature, actual_curvature, steer_limited_by_safety, output_torque):
    self._ff = ff
    self._pid = pid
    self._pid_log = pid_log
    self._setpoint = setpoint
    self._measurement = measurement
    self._roll_compensation = roll_compensation
    self._lateral_accel_deadzone = lateral_accel_deadzone
    self._desired_lateral_accel = desired_lateral_accel
    self._actual_lateral_accel = actual_lateral_accel
    self._desired_curvature = desired_curvature
    self._actual_curvature = actual_curvature
    self._gravity_adjusted_lateral_accel = gravity_adjusted_lateral_accel
    self._steer_limited_by_safety = steer_limited_by_safety
    self._output_torque = output_torque

    self.update_calculations(CS, VM, desired_lateral_accel)
    self.update_neural_network_feedforward(CS, params, calibrated_pose)

    if self._frame % 100 == 0:
        self._smart_hca_enabled = self._params.get_bool("HcaMapTorqueController")
    self._frame += 1

    if self._smart_hca_enabled and compute_smart_hca_target_torque and getattr(self, 'CP', None):
        tt_flag = getattr(VolkswagenFlags, 'TT_DATASET_237', None)
        if tt_flag and (self.CP.flags & tt_flag):
            kph = CS.vEgo * CV.MS_TO_KPH
            self._output_torque = compute_smart_hca_target_torque("237", self._output_torque, kph)

    return self._pid_log, self._output_torque
