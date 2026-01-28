"""Shared helpers for registering the nomadcast:// protocol handler."""

from __future__ import annotations

import logging
import shlex
from pathlib import Path

SCHEME = "nomadcast"
STAMP_PATH = Path.home() / ".nomadcast" / "protocol_handler_registered"
LOGGER = logging.getLogger(__name__)


def source_root() -> Path:
    return Path(__file__).resolve().parent.parent


def shell_env_export() -> str:
    root = shlex.quote(str(source_root()))
    return f'export PYTHONPATH="{root}:$PYTHONPATH"'


def windows_env_set() -> str:
    root = str(source_root())
    return f'set "PYTHONPATH={root};%PYTHONPATH%"'
