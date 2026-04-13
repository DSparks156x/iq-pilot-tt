"""
Copyright © IQ.Lvbs, apart of Project Teal Lvbs, All Rights Reserved, licensed under https://konn3kt.com/tos
"""
from collections.abc import Callable

import pyray as rl

from openpilot.common.params import Params
from openpilot.selfdrive.ui.mici.widgets.button import BigParamControl, BigMultiParamToggle
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.widgets import NavWidget
from openpilot.system.ui.widgets.scroller import Scroller


class VisualsLayoutMici(NavWidget):
  """
  Visual display settings for MICI.
  Matches the BIG VisualsLayout feature set, adapted for the 536×240 display
  using BigParamControl and BigMultiParamToggle widgets in a vertical scroller.
  """

  def __init__(self, back_callback: Callable | None = None):
    super().__init__()
    self._params = Params()

    # --- Simple on/off toggles ---
    self._blind_spot = BigParamControl("Blind Spot Warnings", "BlindSpot")
    self._steering_arc = BigParamControl("Steering Arc", "TorqueBar")
    self._road_name = BigParamControl("Road Name", "RoadNameToggle")
    self._turn_signals = BigParamControl("Turn Signals", "ShowTurnSignals")
    self._accel_bar = BigParamControl("Acceleration Bar", "RocketFuel")

    # --- Multi-option selectors ---
    # Chevron metrics: what info to show below the lead chevron
    CHEVRON_OPTIONS = ["off", "distance", "speed", "time", "all"]
    self._chevron_info = BigMultiParamToggle(
      "Chevron Info", "ChevronInfo", CHEVRON_OPTIONS
    )

    # Developer UI overlay position
    DEV_UI_OPTIONS = ["off", "bottom", "right", "right & bottom"]
    self._dev_ui = BigMultiParamToggle(
      "Dev UI", "DevUIInfo", DEV_UI_OPTIONS
    )

    self._scroller = Scroller([
      self._blind_spot,
      self._steering_arc,
      self._road_name,
      self._turn_signals,
      self._accel_bar,
      self._chevron_info,
      self._dev_ui,
    ], horizontal=False, snap_items=False)

    if back_callback:
      self.set_back_callback(back_callback)

  def show_event(self):
    super().show_event()
    self._blind_spot.refresh()
    self._steering_arc.refresh()
    self._road_name.refresh()
    self._turn_signals.refresh()
    self._accel_bar.refresh()
    self._chevron_info._load_value()
    self._dev_ui._load_value()

    if ui_state.has_longitudinal_control:
      self._chevron_info.set_enabled(True)
    else:
      self._chevron_info.set_enabled(False)
      self._params.put("ChevronInfo", 0)
      self._chevron_info._load_value()

    self._scroller.show_event()

  def _render(self, rect: rl.Rectangle):
    self._scroller.render(rect)
