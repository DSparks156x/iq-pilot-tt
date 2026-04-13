"""
Copyright © IQ.Lvbs, apart of Project Teal Lvbs, All Rights Reserved, licensed under https://konn3kt.com/tos
"""
from collections.abc import Callable

import pyray as rl

from openpilot.common.params import Params
from openpilot.selfdrive.ui.mici.widgets.button import BigMultiParamToggle, BigMultiToggle
from openpilot.system.ui.widgets import NavWidget
from openpilot.system.ui.widgets.scroller import Scroller
# Onroad brightness options map directly to the existing param values.
ONROAD_BRIGHTNESS_OPTIONS = [
  "auto",
  "auto dark",
  "5%",
  "10%",
  "15%",
  "20%",
  "25%",
  "30%",
  "35%",
  "40%",
  "45%",
  "50%",
  "55%",
  "60%",
  "65%",
  "70%",
  "75%",
  "80%",
  "85%",
  "90%",
  "95%",
  "100%",
]

BRIGHTNESS_DELAY_OPTIONS = ["15s", "30s", "1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m", "10m"]
INTERACTIVITY_OPTIONS = ["default", "10s", "20s", "30s", "40s", "50s", "1m", "70s", "80s", "90s", "100s", "110s", "2m"]


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


class DisplayLayoutMici(NavWidget):
  """
  Display and brightness controls for MICI.
  Matches BIG DisplayLayout feature set, compact for 536×240.

  - Onroad brightness mode
  - Onroad brightness delay
  - Interactivity timeout
  """

  def __init__(self, back_callback: Callable | None = None):
    super().__init__()
    self._params = Params()

    self._brightness_mode = BigMultiParamToggle(
      "Onroad Brightness", "OnroadScreenOffBrightness", ONROAD_BRIGHTNESS_OPTIONS,
    )
    self._brightness_delay = MappedParamToggle(
      "Brightness Delay", "OnroadScreenOffTimer", BRIGHTNESS_DELAY_OPTIONS,
      [15, 30, 60, 120, 180, 240, 300, 360, 420, 480, 540, 600],
    )
    self._interactivity_timeout = MappedParamToggle(
      "Interactivity", "InteractivityTimeout", INTERACTIVITY_OPTIONS,
      [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120],
    )

    self._items = [
      self._brightness_mode,
      self._brightness_delay,
      self._interactivity_timeout,
    ]

    self._scroller = Scroller(
      list(self._items),
      horizontal=False, snap_items=False,
    )

    if back_callback:
      self.set_back_callback(back_callback)

  def show_event(self):
    super().show_event()
    self._brightness_mode._load_value()
    self._brightness_delay.refresh()
    self._interactivity_timeout.refresh()
    brightness_val = int(self._params.get("OnroadScreenOffBrightness", return_default=True))
    self._brightness_delay.set_enabled(brightness_val not in (0, 1))
    self._scroller.show_event()

  def _update_state(self):
    super()._update_state()
    brightness_val = int(self._params.get("OnroadScreenOffBrightness", return_default=True))
    self._brightness_delay.set_enabled(brightness_val not in (0, 1))

  def _render(self, rect: rl.Rectangle):
    self._scroller.render(rect)
