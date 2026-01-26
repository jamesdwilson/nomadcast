from __future__ import annotations

import logging
import sys
import textwrap
from pathlib import Path

from nomadcastd.config import NomadCastConfig, set_reticulum_config_dir

NOMADNET_CONFIG_PATH = Path.home() / ".nomadnetwork" / "config"
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
    if not NOMADNET_CONFIG_PATH.exists():
        logger.info(
            "NomadNet config not found at %s; skipping interface import prompt.",
            NOMADNET_CONFIG_PATH,
        )
        return False

    prompt = textwrap.dedent(
        f"""
        NomadCast can import Reticulum interface settings from Nomad Network.

        This will copy only the [interfaces] section from:
          {NOMADNET_CONFIG_PATH}
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
        imported = _import_nomadnet_interfaces(config.config_path, logger)
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


def ensure_nomadnet_interfaces(config: NomadCastConfig, logger: logging.Logger) -> tuple[bool, bool]:
    """Ensure NomadCast uses a dedicated Reticulum config with NomadNet interfaces.

    Returns:
        (ready, reload_config): ready indicates whether startup can proceed.
        reload_config is True if the NomadCast config file was modified and
        should be reloaded.
    """
    config_dir = Path(config.reticulum_config_dir).expanduser() if config.reticulum_config_dir else None
    reload_config = False

    if config_dir is None:
        logger.warning(
            "Reticulum config_dir is not set. NomadCast requires imported NomadNet interfaces to start."
        )
        if not sys.stdin.isatty():
            logger.error(
                "Cannot prompt to import NomadNet interfaces in a non-interactive session. "
                "Run nomadcastd interactively once or set reticulum.config_dir to %s.",
                NOMADCAST_RETICULUM_DIR,
            )
            return False, False
        if not maybe_prompt_nomadnet_interface_import(config, logger):
            logger.error(
                "NomadNet interface import was not completed. "
                "NomadCast will not start without imported interfaces."
            )
            return False, False
        reload_config = True
        config_dir = NOMADCAST_RETICULUM_DIR

    if config_dir != NOMADCAST_RETICULUM_DIR:
        logger.error(
            "NomadCast requires its own Reticulum config at %s. "
            "Other Reticulum config directories are not supported to avoid ambiguity.",
            NOMADCAST_RETICULUM_DIR,
        )
        return False, reload_config

    reticulum_config_path = config_dir / "config"
    if not reticulum_config_path.exists():
        logger.error(
            "NomadCast Reticulum config not found at %s. "
            "Run nomadcastd interactively to import NomadNet interfaces.",
            reticulum_config_path,
        )
        return False, reload_config

    interface_block = _extract_interfaces_block(
        reticulum_config_path.read_text(encoding="utf-8")
    )
    if not _has_interface_entries(interface_block):
        logger.error(
            "NomadCast Reticulum config at %s does not include any [interfaces] entries. "
            "Re-run the NomadNet interface import.",
            reticulum_config_path,
        )
        return False, reload_config

    logger.info(
        "NomadCast Reticulum config verified at %s with imported NomadNet interfaces.",
        reticulum_config_path,
    )
    return True, reload_config


def _import_nomadnet_interfaces(config_path: Path, logger: logging.Logger) -> bool:
    if NOMADCAST_RETICULUM_CONFIG.exists():
        logger.info(
            "NomadCast Reticulum config already exists at %s; leaving it unchanged.",
            NOMADCAST_RETICULUM_CONFIG,
        )
        set_reticulum_config_dir(config_path, NOMADCAST_RETICULUM_DIR)
        return True

    source_text = NOMADNET_CONFIG_PATH.read_text(encoding="utf-8")
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
        #   {NOMADNET_CONFIG_PATH}
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


def _has_interface_entries(block: list[str]) -> bool:
    """Return True when the [interfaces] block contains at least one entry."""
    if not block:
        return False
    for line in block[1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")):
            continue
        return True
    return False


def _record_prompt_stamp(logger: logging.Logger) -> None:
    try:
        PROMPT_STAMP.parent.mkdir(parents=True, exist_ok=True)
        PROMPT_STAMP.write_text("prompted\n", encoding="utf-8")
    except OSError as exc:
        logger.debug("Failed to record reticulum import prompt stamp: %s", exc)
