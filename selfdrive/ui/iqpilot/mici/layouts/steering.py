"""
Copyright © IQ.Lvbs, apart of Project Teal Lvbs, All Rights Reserved, licensed under https://konn3kt.com/tos
"""
from collections.abc import Callable

import pyray as rl
from cereal import car

from openpilot.common.params import Params
from openpilot.iqpilot.selfdrive.controls.lib.helpers.lane_change import AutoLaneChangeMode
from openpilot.selfdrive.ui.mici.widgets.button import BigButton, BigMultiToggle, BigParamControl, NeonBigParamToggle
from openpilot.selfdrive.ui.mici.widgets.dialog import BigDialogBase
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import FontWeight, gui_app
from openpilot.system.ui.widgets import DialogResult, NavWidget
from openpilot.system.ui.widgets.label import UnifiedLabel
from openpilot.system.ui.widgets.scroller import Scroller


class MappedParamToggle(BigMultiToggle):
  def __init__(self, text: str, param: str, options: list[str], values: list[int]):
    super().__init__(text, options)
    assert len(options) == len(values)
    self._param = param
    self._values = values
    self._params = Params()
    self.refresh()

  def refresh(self) -> None:
    current = self._params.get(self._param, return_default=True)
    try:
      idx = self._values.index(int(current))
    except (TypeError, ValueError):
      idx = 0
    self.set_value(self._options[idx])

  def _handle_mouse_release(self, mouse_pos):
    super()._handle_mouse_release(mouse_pos)
    idx = self._options.index(self.value)
    self._params.put_nonblocking(self._param, self._values[idx])


class AolBrakeToggle(BigParamControl):
  def __init__(self):
    super().__init__("Disengage on Brake", "AolEnabled")

  def refresh(self):
    self.set_checked(int(self.params.get("AolSteeringMode", return_default=True)) == 2)

  def _handle_mouse_release(self, mouse_pos):
    super(BigParamControl, self)._handle_mouse_release(mouse_pos)
    enabled = not self._checked
    self._checked = enabled
    current_mode = int(self.params.get("AolSteeringMode", return_default=True))
    if enabled:
      self.params.put("AolSteeringMode", 2)
    elif current_mode == 2:
      self.params.put("AolSteeringMode", 1)


class AolSettingsModal(BigDialogBase):
  def __init__(self):
    super().__init__()
    self._ret = DialogResult.NO_ACTION

    self._back_btn = BigButton("back")
    self._back_btn.set_click_callback(lambda: setattr(self, "_ret", DialogResult.CANCEL))
    self._title_label = UnifiedLabel("aol settings", 44, FontWeight.DISPLAY,
                                     alignment=rl.GuiTextAlignment.TEXT_ALIGN_LEFT)

    self._main_cruise = BigParamControl("Toggle with Main Cruise", "AolMainCruiseAllowed")
    self._disengage_on_brake = AolBrakeToggle()
    self._steering_mode = MappedParamToggle(
      "Steering Mode",
      "AolSteeringMode",
      ["remain active", "pause", "disengage"],
      [0, 1, 2],
    )

    self._scroller = Scroller([
      self._main_cruise,
      self._disengage_on_brake,
      self._steering_mode,
    ], horizontal=False, snap_items=False)

  @staticmethod
  def _aol_limited_settings() -> bool:
    brand = ""
    if ui_state.is_offroad():
      bundle = ui_state.params.get("CarPlatformBundle")
      if bundle:
        brand = bundle.get("brand", "")
    if not brand:
      brand = ui_state.CP.brand if ui_state.CP else ""
    return brand == "rivian"

  def show_event(self):
    super().show_event()

    limited = self._aol_limited_settings()
    if limited:
      ui_state.params.remove("AolMainCruiseAllowed")
      ui_state.params.put_bool("AolUnifiedEngagementMode", True)
      ui_state.params.put("AolSteeringMode", 2)

    self._main_cruise.refresh()
    self._main_cruise.set_enabled(ui_state.is_offroad() and not limited)
    self._main_cruise.set_checked(False if limited else self._main_cruise._checked)

    self._disengage_on_brake.refresh()
    self._disengage_on_brake.set_enabled(ui_state.is_offroad() and not limited)

    self._steering_mode.refresh()
    self._steering_mode.set_enabled(ui_state.is_offroad() and not limited)

    self._scroller.show_event()

  def _render(self, _):
    rect = self._rect
    self._back_btn.render(rl.Rectangle(rect.x, rect.y, self._back_btn.rect.width, self._back_btn.rect.height))

    title_x = rect.x + self._back_btn.rect.width + 12
    self._title_label.render(rl.Rectangle(title_x, rect.y + 8, rect.width - title_x - 8, 50))

    content_rect = rl.Rectangle(rect.x, rect.y + 60, rect.width, rect.height - 60)
    self._scroller.render(content_rect)
    return self._ret


class LaneChangeSettingsModal(BigDialogBase):
  def __init__(self):
    super().__init__()
    self._ret = DialogResult.NO_ACTION

    self._back_btn = BigButton("back")
    self._back_btn.set_click_callback(lambda: setattr(self, "_ret", DialogResult.CANCEL))
    self._title_label = UnifiedLabel("lane change", 44, FontWeight.DISPLAY,
                                     alignment=rl.GuiTextAlignment.TEXT_ALIGN_LEFT)

    self._timer = MappedParamToggle(
      "Auto Lane Change",
      "AutoLaneChangeTimer",
      ["off", "nudge", "nudgeless", "0.5 s", "1 s", "2 s", "3 s"],
      [-1, 0, 1, 2, 3, 4, 5],
    )
    self._bsm_delay = BigParamControl("Delay with Blind Spot", "AutoLaneChangeBsmDelay")

    self._scroller = Scroller([
      self._timer,
      self._bsm_delay,
    ], horizontal=False, snap_items=False)

  def show_event(self):
    super().show_event()
    self._timer.refresh()

    enable_bsm = bool(ui_state.CP and ui_state.CP.enableBsm)
    if not enable_bsm and ui_state.params.get_bool("AutoLaneChangeBsmDelay"):
      ui_state.params.remove("AutoLaneChangeBsmDelay")

    self._bsm_delay.refresh()
    self._bsm_delay.set_enabled(enable_bsm and int(ui_state.params.get("AutoLaneChangeTimer", return_default=True)) > AutoLaneChangeMode.NUDGE)
    self._scroller.show_event()

  def _render(self, _):
    rect = self._rect
    self._back_btn.render(rl.Rectangle(rect.x, rect.y, self._back_btn.rect.width, self._back_btn.rect.height))

    title_x = rect.x + self._back_btn.rect.width + 12
    self._title_label.render(rl.Rectangle(title_x, rect.y + 8, rect.width - title_x - 8, 50))

    content_rect = rl.Rectangle(rect.x, rect.y + 60, rect.width, rect.height - 60)
    self._scroller.render(content_rect)
    return self._ret


class TorqueSettingsModal(BigDialogBase):
  def __init__(self):
    super().__init__()
    self._ret = DialogResult.NO_ACTION

    self._back_btn = BigButton("back")
    self._back_btn.set_click_callback(lambda: setattr(self, "_ret", DialogResult.CANCEL))
    self._title_label = UnifiedLabel("torque settings", 44, FontWeight.DISPLAY,
                                     alignment=rl.GuiTextAlignment.TEXT_ALIGN_LEFT)

    self._self_tune = BigParamControl("Self Tune", "LiveTorqueParamsToggle")
    self._relaxed_tune = BigParamControl("Relaxed Self Tune", "LiveTorqueParamsRelaxedToggle")
    self._custom_tune = BigParamControl("Enable Custom Tuning", "CustomTorqueParams")
    self._manual_rt = BigParamControl("Manual Real-Time Tuning", "TorqueParamsOverrideEnabled")

    self._scroller = Scroller([
      self._self_tune,
      self._relaxed_tune,
      self._custom_tune,
      self._manual_rt,
    ], horizontal=False, snap_items=False)

  def show_event(self):
    super().show_event()
    if not ui_state.params.get_bool("LiveTorqueParamsToggle"):
      ui_state.params.remove("LiveTorqueParamsRelaxedToggle")

    custom_tune_enabled = ui_state.params.get_bool("CustomTorqueParams")

    self._self_tune.refresh()
    self._self_tune.set_enabled(ui_state.is_offroad())

    self._relaxed_tune.refresh()
    self._relaxed_tune.set_enabled(ui_state.is_offroad() and self._self_tune._checked)

    self._custom_tune.refresh()
    self._custom_tune.set_enabled(ui_state.is_offroad())

    self._manual_rt.refresh()
    self._manual_rt.set_visible(custom_tune_enabled)
    self._manual_rt.set_enabled(ui_state.is_offroad())

    self._scroller.show_event()

  def _render(self, _):
    rect = self._rect
    self._back_btn.render(rl.Rectangle(rect.x, rect.y, self._back_btn.rect.width, self._back_btn.rect.height))

    title_x = rect.x + self._back_btn.rect.width + 12
    self._title_label.render(rl.Rectangle(title_x, rect.y + 8, rect.width - title_x - 8, 50))

    content_rect = rl.Rectangle(rect.x, rect.y + 60, rect.width, rect.height - 60)
    self._scroller.render(content_rect)
    return self._ret


class SteeringLayoutMici(NavWidget):
  def __init__(self, back_callback: Callable | None = None):
    super().__init__()
    self._params = Params()

    self._aol_btn = NeonBigParamToggle(
      "AOL",
      "AolEnabled",
      sub_chips=self._get_aol_sub_chips(),
      toggle_callback=self._on_aol_toggled,
    )
    self._aol_settings_btn = BigButton("aol settings")
    self._aol_settings_btn.set_click_callback(self._open_aol_settings)

    self._lane_change_btn = BigButton("lane change")
    self._lane_change_btn.set_click_callback(self._open_lane_change)

    self._torque_ctrl = BigParamControl("Torque Auto Tune", "EnforceTorqueControl", toggle_callback=self._on_torque_toggled)
    self._torque_settings_btn = BigButton("torque settings")
    self._torque_settings_btn.set_click_callback(self._open_torque_settings)

    self._nnff_ctrl = BigParamControl("Neural Net FF", "NeuralNetworkFeedForward", toggle_callback=self._on_nnff_toggled)

    self._scroller = Scroller([
      self._aol_btn,
      self._aol_settings_btn,
      self._lane_change_btn,
      self._torque_ctrl,
      self._torque_settings_btn,
      self._nnff_ctrl,
    ], horizontal=False, snap_items=False)

    if back_callback:
      self.set_back_callback(back_callback)

    self._aol_modal = AolSettingsModal()
    self._lane_change_modal = LaneChangeSettingsModal()
    self._torque_modal = TorqueSettingsModal()

  def _get_aol_sub_chips(self) -> list[str]:
    modes = ["remain active", "pause", "disengage"]
    try:
      mode = int(self._params.get("AolSteeringMode", return_default=True))
      return [modes[mode]]
    except (TypeError, ValueError, IndexError):
      return [modes[0]]

  def _on_aol_toggled(self, checked: bool):
    if checked:
      ui_state.params.put_bool("AolUnifiedEngagementMode", True)
    self._aol_btn.set_sub_chips(self._get_aol_sub_chips())

  def _on_torque_toggled(self, checked: bool):
    if checked:
      ui_state.params.put_bool("NeuralNetworkFeedForward", False)
    self._refresh_main_controls()

  def _on_nnff_toggled(self, checked: bool):
    if checked:
      ui_state.params.put_bool("EnforceTorqueControl", False)
    self._refresh_main_controls()

  def _refresh_main_controls(self):
    self._aol_btn.refresh()
    self._aol_btn.set_sub_chips(self._get_aol_sub_chips())

    self._torque_ctrl.refresh()
    self._nnff_ctrl.refresh()

    torque_allowed = ui_state.CP is not None and ui_state.CP.steerControlType != car.CarParams.SteerControlType.angle
    if not torque_allowed:
      ui_state.params.remove("EnforceTorqueControl")
      ui_state.params.remove("NeuralNetworkFeedForward")
      self._torque_ctrl.refresh()
      self._nnff_ctrl.refresh()

    self._aol_btn.set_enabled(ui_state.is_offroad())
    self._aol_settings_btn.set_enabled(ui_state.is_offroad() and self._aol_btn._checked)

    self._torque_ctrl.set_enabled(ui_state.is_offroad() and torque_allowed and not self._nnff_ctrl._checked)
    self._nnff_ctrl.set_enabled(ui_state.is_offroad() and torque_allowed and not self._torque_ctrl._checked)
    self._torque_settings_btn.set_enabled(self._torque_ctrl._checked)

  def _update_state(self):
    super()._update_state()
    self._refresh_main_controls()

  def _open_aol_settings(self):
    self._aol_modal.show_event()
    gui_app.set_modal_overlay(self._aol_modal)

  def _open_lane_change(self):
    self._lane_change_modal.show_event()
    gui_app.set_modal_overlay(self._lane_change_modal)

  def _open_torque_settings(self):
    self._torque_modal.show_event()
    gui_app.set_modal_overlay(self._torque_modal)

  def show_event(self):
    super().show_event()
    self._refresh_main_controls()
    self._scroller.show_event()

  def _render(self, rect: rl.Rectangle):
    self._scroller.render(rect)
