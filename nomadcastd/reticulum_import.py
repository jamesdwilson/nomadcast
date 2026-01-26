from __future__ import annotations

import logging
import sys
import textwrap
from pathlib import Path

from nomadcastd.config import NomadCastConfig, set_reticulum_config_dir

NOMADNET_CONFIG_PATH = Path.home() / ".nomadnetwork" / "config"
NOMADNET_RETICULUM_CONFIG_PATH = Path.home() / ".nomadnetwork" / "reticulum" / "config"
NOMADNET_RETICULUM_CONF_PATH = Path.home() / ".nomadnetwork" / "reticulum" / "reticulum.conf"
NOMADCAST_RETICULUM_DIR = Path.home() / ".nomadcast" / "reticulum"
NOMADCAST_RETICULUM_CONFIG = NOMADCAST_RETICULUM_DIR / "config"
PROMPT_STAMP = Path.home() / ".nomadcast" / "reticulum_import_prompted"


def maybe_prompt_nomadnet_interface_import(
    config: NomadCastConfig,
    logger: logging.Logger,
) -> bool:
    """Offer a one-time Nomad Network interface import for Reticulum config."""
    if config.reticulum_config_dir is not None:
        return False
    if PROMPT_STAMP.exists():
        return False
    if not sys.stdin.isatty():
        logger.info("NomadNet interface import prompt skipped (non-interactive).")
        return False
    interface_source = _find_nomadnet_interface_source(logger)
    if interface_source is None:
        return False

    prompt = textwrap.dedent(
        f"""
        NomadCast can import Reticulum interface settings from Nomad Network.

        This will copy only the [interfaces] section from:
          {interface_source}
        into a new NomadCast-only Reticulum config at:
          {NOMADCAST_RETICULUM_CONFIG}

        Your Nomad Network identity and settings stay untouched. NomadCast will
        use the new Reticulum config directory for its own network state.

        Import Nomad Network interfaces now? [y/N]:
        """
    )
    answer = input(prompt).strip().lower()
    _record_prompt_stamp(logger)
    if answer not in {"y", "yes"}:
        logger.info("Skipping NomadNet interface import.")
        return False

    try:
        imported = _import_nomadnet_interfaces(config.config_path, interface_source, logger)
    except OSError as exc:
        logger.error("NomadNet interface import failed: %s", exc)
        return False

    if not imported:
        return False

    logger.info(
        "NomadNet interfaces imported. NomadCast will use Reticulum config_dir=%s",
        NOMADCAST_RETICULUM_DIR,
    )
    return True


def _import_nomadnet_interfaces(
    config_path: Path,
    interface_source: Path,
    logger: logging.Logger,
) -> bool:
    if NOMADCAST_RETICULUM_CONFIG.exists():
        logger.info(
            "NomadCast Reticulum config already exists at %s; leaving it unchanged.",
            NOMADCAST_RETICULUM_CONFIG,
        )
        set_reticulum_config_dir(config_path, NOMADCAST_RETICULUM_DIR)
        return True

    source_text = interface_source.read_text(encoding="utf-8")
    interface_block = _extract_interfaces_block(source_text)
    if not interface_block:
        logger.warning(
            "NomadNet config did not contain a [interfaces] section. Nothing to import."
        )
        return False

    NOMADCAST_RETICULUM_DIR.mkdir(parents=True, exist_ok=True)
    header = textwrap.dedent(
        f"""\
        # NomadCast Reticulum config
        # Interfaces imported from Nomad Network:
        #   {interface_source}
        #
        # Only the [interfaces] section is copied to avoid altering or sharing
        # Nomad Network's identity and state.
        """
    ).strip()
    content_lines = [header, "", *interface_block, ""]
    NOMADCAST_RETICULUM_CONFIG.write_text("\n".join(content_lines), encoding="utf-8")
    set_reticulum_config_dir(config_path, NOMADCAST_RETICULUM_DIR)
    return True


def _extract_interfaces_block(source_text: str) -> list[str]:
    lines = source_text.splitlines()
    start_index = None
    for index, line in enumerate(lines):
        if line.strip().lower() == "[interfaces]":
            start_index = index
            break
    if start_index is None:
        return []
    block = [lines[start_index]]
    for line in lines[start_index + 1 :]:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            break
        block.append(line)
    while block and not block[-1].strip():
        block.pop()
    return block


def _find_nomadnet_interface_source(logger: logging.Logger) -> Path | None:
    candidates = [
        NOMADNET_CONFIG_PATH,
        NOMADNET_RETICULUM_CONFIG_PATH,
        NOMADNET_RETICULUM_CONF_PATH,
    ]
    for path in candidates:
        if not path.exists():
            continue
        source_text = path.read_text(encoding="utf-8")
        if _extract_interfaces_block(source_text):
            return path
    logger.info(
        "NomadNet Reticulum interfaces were not found in %s.",
        ", ".join(str(path) for path in candidates),
    )
    return None


def _record_prompt_stamp(logger: logging.Logger) -> None:
    try:
        PROMPT_STAMP.parent.mkdir(parents=True, exist_ok=True)
        PROMPT_STAMP.write_text("prompted\n", encoding="utf-8")
    except OSError as exc:
        logger.debug("Failed to record reticulum import prompt stamp: %s", exc)
