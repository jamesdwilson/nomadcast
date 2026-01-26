from __future__ import annotations

import os
import platform
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


APP_NAME = "NomadCast"
APP_BUNDLE_NAME = f"{APP_NAME}.app"
APP_BUNDLE_ID = "com.nomadcast.ui"
APP_INSTALL_STAMP = Path.home() / ".nomadcast" / "app_install_prompted"


def maybe_prompt_install_app(root: object) -> None:
    """Prompt macOS users to install NomadCast into Applications on first run."""
    if platform.system() != "Darwin":
        return
    if APP_INSTALL_STAMP.exists():
        return
    if _running_from_app_bundle():
        return

    _record_prompt_stamp()
    install_dir = _preferred_applications_dir()

    from tkinter import messagebox

    answer = messagebox.askyesno(
        title="Install NomadCast",
        message=(
            "Install NomadCast into the Applications folder for easier launch?\n\n"
            f"Target: {install_dir}"
        ),
        parent=root,
    )
    if not answer:
        return

    try:
        bundle_path = _install_app_bundle(install_dir)
    except OSError as exc:
        messagebox.showerror(
            title="Install failed",
            message=f"Could not install NomadCast: {exc}",
            parent=root,
        )
        return

    _relaunch_from_app(bundle_path, root)


def _record_prompt_stamp() -> None:
    try:
        APP_INSTALL_STAMP.parent.mkdir(parents=True, exist_ok=True)
        APP_INSTALL_STAMP.write_text("prompted\n", encoding="utf-8")
    except OSError:
        pass


def _running_from_app_bundle() -> bool:
    for candidate in {Path(sys.argv[0]).resolve(), Path(sys.executable).resolve()}:
        for parent in candidate.parents:
            if parent.suffix == ".app":
                return True
    return False


def _preferred_applications_dir() -> Path:
    system_apps = Path("/Applications")
    if os.access(system_apps, os.W_OK):
        return system_apps
    return Path.home() / "Applications"


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


def _relaunch_from_app(bundle_path: Path, root: object) -> None:
    subprocess.run(["open", "-a", str(bundle_path)], check=False)
    try:
        root.destroy()
    finally:
        sys.exit(0)
