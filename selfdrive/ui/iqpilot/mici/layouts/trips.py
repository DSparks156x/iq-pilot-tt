"""
Copyright © IQ.Lvbs, apart of Project Teal Lvbs, All Rights Reserved, licensed under https://konn3kt.com/tos

Trips / drive statistics for MICI (comma 4).
Ported from selfdrive/ui/iqpilot/layouts/settings/trips.py.
Shows all-time stats: drives, distance, hours driven.
"""
import threading
from collections.abc import Callable

import pyray as rl

from openpilot.common.params import Params
from openpilot.selfdrive.ui.mici.widgets.button import BigButton
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.system.ui.widgets import NavWidget
from openpilot.system.ui.widgets.label import UnifiedLabel

try:
  from openpilot.selfdrive.ui.iqpilot.layouts.settings.trips import fetch_drive_stats
except ImportError:
  fetch_drive_stats = None


class TripsLayoutMici(NavWidget):
  """
  All-time drive statistics panel for MICI.
  Fetches stats from the API in a background thread (same as BIG version).
  Displays: drives / distance / hours in a clean compact layout.
  """

  STAT_FONT_SIZE = 52
  LABEL_FONT_SIZE = 24
  STAT_COLOR = rl.Color(255, 255, 255, int(255 * 0.92))
  LABEL_COLOR = rl.Color(180, 180, 180, 200)
  PAD = 20

  def __init__(self, back_callback: Callable | None = None):
    super().__init__()
    self._params = Params()

    self._loading = False
    self._stats: dict | None = None  # {"routes": N, "distance_mi": X, "distance_km": X, "hours": H}

    # Display labels — updated when stats arrive
    self._drives_stat = UnifiedLabel("—", self.STAT_FONT_SIZE, FontWeight.DISPLAY,
                                     self.STAT_COLOR, alignment=rl.GuiTextAlignment.TEXT_ALIGN_LEFT)
    self._drives_lbl = UnifiedLabel("drives", self.LABEL_FONT_SIZE, FontWeight.ROMAN,
                                    self.LABEL_COLOR, alignment=rl.GuiTextAlignment.TEXT_ALIGN_LEFT)

    self._distance_stat = UnifiedLabel("—", self.STAT_FONT_SIZE, FontWeight.DISPLAY,
                                       self.STAT_COLOR, alignment=rl.GuiTextAlignment.TEXT_ALIGN_LEFT)
    self._distance_lbl = UnifiedLabel("distance", self.LABEL_FONT_SIZE, FontWeight.ROMAN,
                                      self.LABEL_COLOR, alignment=rl.GuiTextAlignment.TEXT_ALIGN_LEFT)

    self._hours_stat = UnifiedLabel("—", self.STAT_FONT_SIZE, FontWeight.DISPLAY,
                                    self.STAT_COLOR, alignment=rl.GuiTextAlignment.TEXT_ALIGN_LEFT)
    self._hours_lbl = UnifiedLabel("hours", self.LABEL_FONT_SIZE, FontWeight.ROMAN,
                                   self.LABEL_COLOR, alignment=rl.GuiTextAlignment.TEXT_ALIGN_LEFT)

    # Loading / empty state label
    self._status_label = UnifiedLabel("loading...", 36, FontWeight.ROMAN,
                                      rl.Color(255, 255, 255, int(255 * 0.35)),
                                      alignment=rl.GuiTextAlignment.TEXT_ALIGN_CENTER,
                                      alignment_vertical=rl.GuiTextAlignmentVertical.TEXT_ALIGN_MIDDLE)

    self._refresh_btn = BigButton("refresh")
    self._refresh_btn.set_click_callback(self._start_fetch)

    if back_callback:
      self.set_back_callback(back_callback)

  def _start_fetch(self):
    if self._loading or fetch_drive_stats is None:
      return
    self._loading = True
    self._stats = None
    self._status_label.set_text("loading...")

    def _fetch():
      try:
        data = fetch_drive_stats()
        self._stats = data
      except Exception:
        self._stats = {}
      finally:
        self._loading = False
        self._update_display()

    threading.Thread(target=_fetch, daemon=True).start()

  def _is_metric(self) -> bool:
    return self._params.get_bool("IsMetric", False)

  def _update_display(self):
    if not self._stats:
      self._status_label.set_text("no data")
      return

    drives = self._stats.get("routes", 0)
    if self._is_metric():
      dist = self._stats.get("distance_km", 0.0)
      dist_str = f"{dist:,.0f} km"
    else:
      dist = self._stats.get("distance_mi", 0.0)
      dist_str = f"{dist:,.0f} mi"
    hours = self._stats.get("hours", 0.0)

    self._drives_stat.set_text(f"{drives:,}")
    self._distance_stat.set_text(dist_str)
    self._hours_stat.set_text(f"{hours:.1f}h")
    self._status_label.set_text("")

  def show_event(self):
    super().show_event()
    self._start_fetch()

  def _render(self, rect: rl.Rectangle):
    px = rect.x + self.PAD
    w = rect.width - self.PAD * 2

    if self._loading or not self._stats:
      self._status_label.render(rect)
      # Refresh button bottom center
      btn_w = self._refresh_btn._rect.width
      self._refresh_btn.render(rl.Rectangle(
        rect.x + (rect.width - btn_w) / 2,
        rect.y + rect.height - self._refresh_btn._rect.height - self.PAD,
        btn_w, self._refresh_btn._rect.height,
      ))
      return

    # Three stats stacked: drives / distance / hours
    # Each stat: large number + small label underneath
    stat_block_h = self.STAT_FONT_SIZE + self.LABEL_FONT_SIZE + 4
    total_h = stat_block_h * 3 + 16 * 2  # 3 blocks + 2 gaps
    start_y = rect.y + (rect.height - total_h) / 2

    for stat_label, desc_label in [
      (self._drives_stat, self._drives_lbl),
      (self._distance_stat, self._distance_lbl),
      (self._hours_stat, self._hours_lbl),
    ]:
      stat_label.render(rl.Rectangle(px, start_y, w, self.STAT_FONT_SIZE))
      start_y += self.STAT_FONT_SIZE + 2
      desc_label.render(rl.Rectangle(px, start_y, w, self.LABEL_FONT_SIZE))
      start_y += self.LABEL_FONT_SIZE + 16

    # Refresh button bottom-right
    btn_w = self._refresh_btn._rect.width
    self._refresh_btn.render(rl.Rectangle(
      rect.x + rect.width - btn_w - self.PAD,
      rect.y + rect.height - self._refresh_btn._rect.height - self.PAD,
      btn_w, self._refresh_btn._rect.height,
    ))
