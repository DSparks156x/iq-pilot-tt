import pyray as rl
from collections.abc import Callable

from openpilot.common.time_helpers import system_time_valid
from openpilot.system.ui.widgets.scroller import Scroller
from openpilot.selfdrive.ui.mici.widgets.button import BigButton, BigToggle, BigParamControl, BigCircleParamControl
from openpilot.selfdrive.ui.mici.widgets.dialog import BigDialog, BigInputDialog
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.widgets import NavWidget
from openpilot.selfdrive.ui.layouts.settings.common import restart_needed_callback
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.selfdrive.ui.widgets.ssh_key import SshKeyAction


class DeveloperLayoutMici(NavWidget):
  def __init__(self, back_callback: Callable):
    super().__init__()
    self.set_back_callback(back_callback)

    def github_username_callback(username: str):
      if username:
        ssh_keys = SshKeyAction()
        ssh_keys._fetch_ssh_key(username)
        if not ssh_keys._error_message:
          self._ssh_keys_btn.set_value(username)
        else:
          dlg = BigDialog("", ssh_keys._error_message)
          gui_app.set_modal_overlay(dlg)

    def ssh_keys_callback():
      github_username = ui_state.params.get("GithubUsername") or ""
      dlg = BigInputDialog("enter GitHub username", github_username, confirm_callback=github_username_callback)
      if not system_time_valid():
        dlg = BigDialog("Please connect to Wi-Fi to fetch your key", "")
        gui_app.set_modal_overlay(dlg)
        return
      gui_app.set_modal_overlay(dlg)

    txt_ssh = gui_app.texture("icons_mici/settings/developer/ssh.png", 56, 64)
    github_username = ui_state.params.get("GithubUsername") or ""
    self._ssh_keys_btn = BigButton("SSH keys", "Not set" if not github_username else github_username, icon=txt_ssh)
    self._ssh_keys_btn.set_click_callback(ssh_keys_callback)

    # adb, ssh, ssh keys
    # ******** Main Scroller ********
    self._adb_toggle = BigCircleParamControl("icons_mici/adb_short.png", "AdbEnabled", icon_size=(82, 82), icon_offset=(0, 12))
    self._ssh_toggle = BigCircleParamControl("icons_mici/ssh_short.png", "SshEnabled", icon_size=(82, 82), icon_offset=(0, 12))

    self._scroller = Scroller([
      self._adb_toggle,
      self._ssh_toggle,
      self._ssh_keys_btn,
    ], snap_items=False)

    # Toggle lists
    self._refresh_toggles = (
      ("AdbEnabled", self._adb_toggle),
      ("SshEnabled", self._ssh_toggle),
    )
    onroad_blocked_toggles = (self._adb_toggle,)

    # Disable toggles that require offroad
    for item in onroad_blocked_toggles:
      item.set_enabled(lambda: ui_state.is_offroad())

    # Set initial state
    if ui_state.params.get_bool("ShowDebugInfo"):
      gui_app.set_show_touches(True)
      gui_app.set_show_fps(True)

    ui_state.add_offroad_transition_callback(self._update_toggles)

  def show_event(self):
    super().show_event()
    self._scroller.show_event()
    self._update_toggles()

  def _render(self, rect: rl.Rectangle):
    self._scroller.render(rect)

  def _update_toggles(self):
    ui_state.update_params()

    # Refresh toggles from params to mirror external changes
    for key, item in self._refresh_toggles:
      item.set_checked(ui_state.params.get_bool(key))
