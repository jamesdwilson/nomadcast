from __future__ import annotations

import os
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path


APP_NAME = "NomadCast"
APP_BUNDLE_NAME = f"{APP_NAME}.app"
APP_BUNDLE_ID = "com.nomadcast.ui"
APP_INSTALL_STAMP = Path.home() / ".nomadcast" / "app_install_prompted"


@dataclass(frozen=True)
class InstallTarget:
    platform: str
    install_dir: Path
    display_target: str
    launcher_path: Path | None = None
    desktop_entry_path: Path | None = None


def maybe_prompt_install_app(root: object) -> None:
    """Prompt users to install NomadCast into a standard applications location."""
    target = _install_target()
    if target is None:
        return
    if APP_INSTALL_STAMP.exists():
        return
    if _running_from_app_bundle() and target.platform == "Darwin":
        return

    _record_prompt_stamp()

    from tkinter import messagebox

    answer = messagebox.askyesno(
        title="Install NomadCast",
        message=(
            "Install NomadCast into your system Applications location for easier launch?\n\n"
            f"Target: {target.display_target}"
        ),
        parent=root,
    )
    if not answer:
        return

    try:
        install_result = _install_app(target)
    except OSError as exc:
        messagebox.showerror(
            title="Install failed",
            message=f"Could not install NomadCast: {exc}",
            parent=root,
        )
        return

    _relaunch_from_app(install_result, root)


def _record_prompt_stamp() -> None:
    try:
        APP_INSTALL_STAMP.parent.mkdir(parents=True, exist_ok=True)
        APP_INSTALL_STAMP.write_text("prompted\n", encoding="utf-8")
    except OSError:
        pass


def _source_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _shell_env_export() -> str:
    root = shlex.quote(str(_source_root()))
    return f'export PYTHONPATH="{root}:$PYTHONPATH"'


def _windows_env_set() -> str:
    root = str(_source_root())
    return f'set "PYTHONPATH={root};%PYTHONPATH%"'


def _running_from_app_bundle() -> bool:
    for candidate in {Path(sys.argv[0]).resolve(), Path(sys.executable).resolve()}:
        for parent in candidate.parents:
            if parent.suffix == ".app":
                return True
    return False


def _install_target() -> InstallTarget | None:
    system = platform.system()
    if system == "Darwin":
        install_dir = _preferred_macos_applications_dir()
        display_target = str(install_dir / APP_BUNDLE_NAME)
        return InstallTarget(platform=system, install_dir=install_dir, display_target=display_target)
    if system == "Windows":
        install_dir = _preferred_windows_applications_dir()
        display_target = str(install_dir)
        launcher_path = install_dir / "NomadCast.cmd"
        return InstallTarget(
            platform=system,
            install_dir=install_dir,
            display_target=display_target,
            launcher_path=launcher_path,
        )
    if system == "Linux":
        applications_dir = _preferred_linux_applications_dir()
        launcher_path = _preferred_linux_bin_dir() / "nomadcast"
        desktop_entry_path = applications_dir / "nomadcast.desktop"
        display_target = f"{desktop_entry_path} (+ {launcher_path})"
        return InstallTarget(
            platform=system,
            install_dir=applications_dir,
            display_target=display_target,
            launcher_path=launcher_path,
            desktop_entry_path=desktop_entry_path,
        )
    return None


def _preferred_macos_applications_dir() -> Path:
    system_apps = Path("/Applications")
    if os.access(system_apps, os.W_OK):
        return system_apps
    return Path.home() / "Applications"


def _preferred_windows_applications_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidate = Path(local_app_data) / "Programs" / APP_NAME
    else:
        candidate = Path.home() / "AppData" / "Local" / "Programs" / APP_NAME
    if os.access(candidate.parent, os.W_OK):
        return candidate
    fallback = Path.home() / APP_NAME
    return fallback


def _preferred_linux_applications_dir() -> Path:
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg_data_home) if xdg_data_home else Path.home() / ".local" / "share"
    return base / "applications"


def _preferred_linux_bin_dir() -> Path:
    xdg_bin_home = os.environ.get("XDG_BIN_HOME")
    return Path(xdg_bin_home) if xdg_bin_home else Path.home() / ".local" / "bin"


def _install_app(target: InstallTarget) -> Path:
    if target.platform == "Darwin":
        return _install_app_bundle(target.install_dir)
    if target.platform == "Windows":
        return _install_windows_app(target)
    if target.platform == "Linux":
        return _install_linux_app(target)
    raise OSError(f"Unsupported platform: {target.platform}")


def _install_app_bundle(applications_dir: Path) -> Path:
    bundle_dir = applications_dir / APP_BUNDLE_NAME
    contents_dir = bundle_dir / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"
    executable_path = macos_dir / "nomadcast"
    info_plist = contents_dir / "Info.plist"

    macos_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)
    icon_name = _write_app_icon(resources_dir)

    executable_path.write_text(
        textwrap.dedent(
            f"""\
            #!/bin/bash
            {_shell_env_export()}
            exec "{sys.executable}" -m nomadcast
            """
        ),
        encoding="utf-8",
    )
    executable_path.chmod(0o755)

    icon_entry = (
        f"                <key>CFBundleIconFile</key>\n"
        f"                <string>{icon_name}</string>\n"
        if icon_name
        else ""
    )

    info_plist.write_text(
        textwrap.dedent(
            f"""\
            <?xml version="1.0" encoding="UTF-8"?>
            <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
            <plist version="1.0">
              <dict>
                <key>CFBundleName</key>
                <string>{APP_NAME}</string>
                <key>CFBundleDisplayName</key>
                <string>{APP_NAME}</string>
                <key>CFBundleIdentifier</key>
                <string>{APP_BUNDLE_ID}</string>
                <key>CFBundleExecutable</key>
                <string>{executable_path.name}</string>
{icon_entry}                <key>CFBundlePackageType</key>
                <string>APPL</string>
                <key>CFBundleVersion</key>
                <string>1.0</string>
                <key>CFBundleShortVersionString</key>
                <string>1.0</string>
              </dict>
            </plist>
            """
        ),
        encoding="utf-8",
    )

    return bundle_dir


def _install_windows_app(target: InstallTarget) -> Path:
    target.install_dir.mkdir(parents=True, exist_ok=True)
    launcher_path = target.launcher_path or (target.install_dir / "NomadCast.cmd")
    launcher_path.write_text(
        textwrap.dedent(
            f"""\
            @echo off
            {_windows_env_set()}
            "{sys.executable}" -m nomadcast %*
            """
        ),
        encoding="utf-8",
    )
    return launcher_path


def _install_linux_app(target: InstallTarget) -> Path:
    applications_dir = target.install_dir
    bin_dir = target.launcher_path.parent if target.launcher_path else _preferred_linux_bin_dir()
    applications_dir.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)

    launcher_path = target.launcher_path or (bin_dir / "nomadcast")
    launcher_path.write_text(
        textwrap.dedent(
            f"""\
            #!/bin/sh
            {_shell_env_export()}
            exec "{sys.executable}" -m nomadcast "$@"
            """
        ),
        encoding="utf-8",
    )
    launcher_path.chmod(0o755)

    icon_path = _install_linux_icon()
    desktop_entry_path = target.desktop_entry_path or (applications_dir / "nomadcast.desktop")
    icon_entry = f"Icon={icon_path}\n" if icon_path else ""
    desktop_entry_path.write_text(
        textwrap.dedent(
            f"""\
            [Desktop Entry]
            Type=Application
            Name={APP_NAME}
            Exec={launcher_path}
            {icon_entry}Terminal=false
            Categories=Utility;
            """
        ),
        encoding="utf-8",
    )
    return launcher_path


def _install_linux_icon() -> str | None:
    source_icon = Path(__file__).resolve().parent.parent / "assets" / "nomadcast-logo.png"
    if not source_icon.exists():
        return None
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg_data_home) if xdg_data_home else Path.home() / ".local" / "share"
    icon_dir = base / "icons" / "hicolor" / "256x256" / "apps"
    icon_dir.mkdir(parents=True, exist_ok=True)
    icon_path = icon_dir / "nomadcast.png"
    shutil.copy(source_icon, icon_path)
    return str(icon_path)


def _write_app_icon(resources_dir: Path) -> str | None:
    source_icon = Path(__file__).resolve().parent.parent / "assets" / "nomadcast-logo.png"
    if not source_icon.exists():
        return None

    icns_name = "NomadCast.icns"
    icns_path = resources_dir / icns_name
    try:
        _convert_png_to_icns(source_icon, icns_path)
    except OSError:
        return None
    return icns_name if icns_path.exists() else None


def _convert_png_to_icns(source_icon: Path, icns_path: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        iconset_dir = Path(tmp_dir) / "NomadCast.iconset"
        iconset_dir.mkdir(parents=True, exist_ok=True)
        sizes = [16, 32, 64, 128, 256, 512, 1024]
        for size in sizes:
            output_path = iconset_dir / f"icon_{size}x{size}.png"
            subprocess.run(
                ["sips", "-z", str(size), str(size), str(source_icon), "--out", str(output_path)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if size <= 512:
                retina_size = size * 2
                retina_path = iconset_dir / f"icon_{size}x{size}@2x.png"
                subprocess.run(
                    ["sips", "-z", str(retina_size), str(retina_size), str(source_icon), "--out", str(retina_path)],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(icns_path)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    if not icns_path.exists():
        raise OSError("Failed to generate icns icon.")


def _relaunch_from_app(launch_path: Path, root: object) -> None:
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["open", "-a", str(launch_path)], check=False)
    elif system == "Windows":
        subprocess.run(["cmd", "/c", "start", "", str(launch_path)], check=False)
    else:
        subprocess.Popen([str(launch_path)])
    try:
        root.destroy()
    finally:
        sys.exit(0)
