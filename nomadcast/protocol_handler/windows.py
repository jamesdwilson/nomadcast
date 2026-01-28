"""Windows protocol handler registration."""

from __future__ import annotations

import sys
import winreg

from nomadcast.protocol_handler.shared import SCHEME, windows_env_set


def register_protocol_handler() -> bool:
    """Register nomadcast:// by writing HKCU\\Software\\Classes registry keys.

    Side effects: creates or updates the per-user registry keys for the URL protocol handler.
    """
    command = f'cmd /c {windows_env_set()} && "{sys.executable}" -m nomadcast "%1"'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\\Classes\\{SCHEME}") as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:NomadCast Protocol")
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(key, r"shell\\open\\command") as command_key:
            winreg.SetValueEx(command_key, "", 0, winreg.REG_SZ, command)
    return True
