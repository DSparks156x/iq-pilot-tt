"""
Copyright © IQ.Lvbs, apart of Project Teal Lvbs, All Rights Reserved, licensed under https://konn3kt.com/tos

Software / update settings for MICI (comma 4).
Ported from selfdrive/ui/iqpilot/layouts/settings/software.py.
"""
from collections.abc import Callable

import pyray as rl

from openpilot.common.params import Params
from openpilot.selfdrive.ui.mici.widgets.button import BigButton, BigParamControl
from openpilot.selfdrive.ui.mici.widgets.dialog import BigConfirmationDialogV2, BigMultiOptionDialog
from openpilot.system.hardware import HARDWARE
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.system.ui.widgets import DialogResult, NavWidget
from openpilot.system.ui.widgets.label import UnifiedLabel
from openpilot.system.ui.widgets.scroller import Scroller


# Branches available for selection
RELEASE_BRANCHES = [
  "release3-staging",
  "release3",
  "nightly",
  "nightly-dev",
]

MICI_BRANCHES = [
  "master-mici",
  "master-mici-staging",
]


class SoftwareLayoutMici(NavWidget):
  """
  Software update settings for MICI.
  - Shows current branch and version
  - Allow disabling automatic updates
  - Branch selection via BigMultiOptionDialog
  """

  def __init__(self, back_callback: Callable | None = None):
    super().__init__()
    self._params = Params()

    # Current branch / version info labels
    self._branch_label = UnifiedLabel(
      self._get_branch_text(), 30, FontWeight.ROMAN,
      alignment=rl.GuiTextAlignment.TEXT_ALIGN_LEFT,
    )
    self._version_label = UnifiedLabel(
      self._get_version_text(), 26, FontWeight.ROMAN,
      rl.Color(180, 180, 180, 200),
      alignment=rl.GuiTextAlignment.TEXT_ALIGN_LEFT,
    )

    # Disable updates toggle
    self._disable_updates = BigParamControl(
      "Disable Updates", "DisableUpdates",
      toggle_callback=self._on_disable_updates_toggled,
    )

    # Branch change button
    self._change_branch_btn = BigButton("change branch →")
    self._change_branch_btn.set_click_callback(self._open_branch_dialog)

    self._scroller = Scroller([
      self._disable_updates,
      self._change_branch_btn,
    ], horizontal=False, snap_items=False)

    if back_callback:
      self.set_back_callback(back_callback)

  def _get_branch_text(self) -> str:
    branch = self._params.get("GitBranch") or "unknown"
    return f"branch: {branch}"

  def _get_version_text(self) -> str:
    version = self._params.get("UpdaterCurrentDescription") or ""
    if not version:
      version = self._params.get("Version") or "unknown"
    # Trim to first 40 chars so it fits on MICI width
    return version[:40]

  def _get_branches(self) -> list[str]:
    """Build list of available branches filtered for device type."""
    device = HARDWARE.get_device_type()
    branches = list(RELEASE_BRANCHES)
    if device == "mici":
      branches = MICI_BRANCHES + branches
    return branches

  def _on_disable_updates_toggled(self, checked: bool):
    if checked:
      # Confirm before disabling — show a slider-confirm dialog
      def confirm():
        # Already toggled in BigParamControl, nothing extra needed
        pass
      dlg = BigConfirmationDialogV2(
        "Disable updates?",
        "icons_mici/settings/device/update.png",
        red=True,
        confirm_callback=confirm,
      )
      gui_app.set_modal_overlay(dlg)

  def _open_branch_dialog(self):
    branches = self._get_branches()
    current_branch = self._params.get("GitBranch") or ""

    def on_confirm():
      selected = dlg.get_selected_option()
      if selected and selected != current_branch:
        self._params.put_nonblocking("SwitchToBranch", selected)
        self._branch_label.set_text(f"branch: {selected} (pending reboot)")

    dlg = BigMultiOptionDialog(
      options=branches,
      default=current_branch if current_branch in branches else None,
      right_btn="check",
      right_btn_callback=on_confirm,
    )
    gui_app.set_modal_overlay(dlg)

  def show_event(self):
    super().show_event()
    self._disable_updates.refresh()
    self._branch_label.set_text(self._get_branch_text())
    self._version_label.set_text(self._get_version_text())
    self._scroller.show_event()

  def _render(self, rect: rl.Rectangle):
    # Info labels at top
    info_h = 70
    self._branch_label.render(rl.Rectangle(rect.x + 16, rect.y + 8, rect.width - 32, 32))
    self._version_label.render(rl.Rectangle(rect.x + 16, rect.y + 40, rect.width - 32, 28))

    # Buttons below info
    content_rect = rl.Rectangle(rect.x, rect.y + info_h, rect.width, rect.height - info_h)
    self._scroller.render(content_rect)
