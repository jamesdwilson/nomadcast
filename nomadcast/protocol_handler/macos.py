"""macOS protocol handler registration."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

from nomadcast.protocol_handler.shared import SCHEME, LOGGER, shell_env_export


def register_protocol_handler() -> bool:
    """Register nomadcast:// by writing an app bundle in ~/Applications and updating LaunchServices.

    Side effects: creates the bundle directories, writes the handler script and Info.plist, and
    invokes lsregister to update the URL scheme registry.
    """
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
            {shell_env_export()}
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
