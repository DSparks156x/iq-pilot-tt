"""
Copyright © IQ.Lvbs, apart of Project Teal Lvbs, All Rights Reserved, licensed under https://konn3kt.com/tos

Cruise control settings for MICI (comma 4).
Placeholder — cruise settings are under active development.
"""
from collections.abc import Callable

import pyray as rl

from openpilot.system.ui.lib.application import FontWeight
from openpilot.system.ui.widgets import NavWidget
from openpilot.system.ui.widgets.label import UnifiedLabel


class CruiseLayoutMici(NavWidget):
  """Cruise control settings — coming soon placeholder."""

  def __init__(self, back_callback: Callable | None = None):
    super().__init__()

    self._label = UnifiedLabel(
      "coming soon",
      72,
      FontWeight.DISPLAY,
      rl.Color(255, 255, 255, int(255 * 0.35)),
      alignment=rl.GuiTextAlignment.TEXT_ALIGN_CENTER,
      alignment_vertical=rl.GuiTextAlignmentVertical.TEXT_ALIGN_MIDDLE,
    )

    if back_callback:
      self.set_back_callback(back_callback)

  def _render(self, rect: rl.Rectangle):
    self._label.render(rect)
