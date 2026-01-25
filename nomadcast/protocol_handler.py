from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

SCHEME = "nomadcast"
STAMP_PATH = Path.home() / ".nomadcast" / "protocol_handler_registered"
LOGGER = logging.getLogger(__name__)


def ensure_protocol_handler_registered() -> bool:
    """Register the nomadcast:// protocol handler once per user."""
    if STAMP_PATH.exists():
        return True

    if register_protocol_handler():
        STAMP_PATH.parent.mkdir(parents=True, exist_ok=True)
        STAMP_PATH.write_text("registered\n", encoding="utf-8")
        return True
    return False


def register_protocol_handler() -> bool:
    """Register the URL scheme handler for the current platform."""
    system = platform.system()
    if system == "Windows":
        return _register_windows()
    if system == "Darwin":
        return _register_macos()
    if system == "Linux":
        return _register_linux()

    LOGGER.info("Protocol handler registration is not supported on %s.", system)
    return False


def _register_windows() -> bool:
    import winreg

    command = f'"{sys.executable}" -m nomadcast "%1"'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\\Classes\\{SCHEME}") as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:NomadCast Protocol")
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(key, r"shell\\open\\command") as command_key:
            winreg.SetValueEx(command_key, "", 0, winreg.REG_SZ, command)
    return True


def _register_macos() -> bool:
    bundle_dir = Path.home() / "Applications" / "NomadCast Protocol Handler.app"
    contents_dir = bundle_dir / "Contents"
    macos_dir = contents_dir / "MacOS"
    executable_path = macos_dir / "nomadcast-handler"
    info_plist = contents_dir / "Info.plist"

    macos_dir.mkdir(parents=True, exist_ok=True)

    executable_path.write_text(
        textwrap.dedent(
            f"""\
            #!/bin/bash
            exec "{sys.executable}" -m nomadcast "$@"
            """
        ),
        encoding="utf-8",
    )
    executable_path.chmod(0o755)

    info_plist.write_text(
        textwrap.dedent(
            f"""\
            <?xml version="1.0" encoding="UTF-8"?>
            <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
            <plist version="1.0">
              <dict>
                <key>CFBundleName</key>
                <string>NomadCast Protocol Handler</string>
                <key>CFBundleIdentifier</key>
                <string>com.nomadcast.protocol-handler</string>
                <key>CFBundleExecutable</key>
                <string>{executable_path.name}</string>
                <key>CFBundlePackageType</key>
                <string>APPL</string>
                <key>CFBundleVersion</key>
                <string>1.0</string>
                <key>CFBundleShortVersionString</key>
                <string>1.0</string>
                <key>LSUIElement</key>
                <true/>
                <key>CFBundleURLTypes</key>
                <array>
                  <dict>
                    <key>CFBundleURLName</key>
                    <string>NomadCast Locator</string>
                    <key>CFBundleURLSchemes</key>
                    <array>
                      <string>{SCHEME}</string>
                    </array>
                  </dict>
                </array>
              </dict>
            </plist>
            """
        ),
        encoding="utf-8",
    )

    lsregister = Path(
        "/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
    )
    if not lsregister.exists():
        LOGGER.info("LaunchServices registry tool not found for protocol handler registration.")
        return False

    result = subprocess.run([str(lsregister), "-f", str(bundle_dir)], check=False)
    return result.returncode == 0


def _register_linux() -> bool:
    xdg_data_home = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local/share"))
    applications_dir = xdg_data_home / "applications"
    applications_dir.mkdir(parents=True, exist_ok=True)

    desktop_file = applications_dir / "nomadcast.desktop"
    desktop_file.write_text(
        textwrap.dedent(
            f"""\
            [Desktop Entry]
            Name=NomadCast
            Comment=NomadCast protocol handler
            Exec="{sys.executable}" -m nomadcast %u
            Terminal=false
            Type=Application
            NoDisplay=true
            MimeType=x-scheme-handler/{SCHEME};
            """
        ),
        encoding="utf-8",
    )

    xdg_mime = shutil.which("xdg-mime")
    if not xdg_mime:
        LOGGER.info("xdg-mime not found; protocol handler registration skipped.")
        return False

    result = subprocess.run(
        [xdg_mime, "default", desktop_file.name, f"x-scheme-handler/{SCHEME}"],
        check=False,
    )
    return result.returncode == 0
