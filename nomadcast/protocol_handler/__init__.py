"""Register the nomadcast:// protocol handler for the current platform."""

from __future__ import annotations

import platform

from nomadcast.protocol_handler.linux import register_protocol_handler as _register_linux
from nomadcast.protocol_handler.macos import register_protocol_handler as _register_macos
from nomadcast.protocol_handler.shared import LOGGER, STAMP_PATH
from nomadcast.protocol_handler.windows import register_protocol_handler as _register_windows


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
