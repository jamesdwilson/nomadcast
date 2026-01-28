"""Linux protocol handler registration."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

from nomadcast.protocol_handler.shared import LOGGER, SCHEME, source_root


def register_protocol_handler() -> bool:
    """Register nomadcast:// by writing a .desktop file and calling xdg-mime.

    Side effects: creates ~/.local/share/applications/nomadcast.desktop (or XDG_DATA_HOME) and
    updates the MIME association via xdg-mime.
    """
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
            Exec=sh -c 'PYTHONPATH="{shlex.quote(str(source_root()))}:$PYTHONPATH" exec "{sys.executable}" -m nomadcast %u'
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
