from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from nomadcast_sample.sample_installer import (
    PLACEHOLDER_IDENTITY,
    detect_nomadnet_identity,
    detect_nomadnet_node_name,
    install_sample,
    sanitize_show_name_for_path,
)
from nomadcastd.config import NomadCastConfig, set_starter_pack_state


@dataclass(frozen=True)
class StarterPackChoices:
    pages_path: Path
    show_name: str
    identity: str


def _prompt_yes_no(prompt: str, *, input_fn: Callable[[str], str]) -> bool:
    answer = input_fn(prompt).strip().lower()
    return answer in {"", "y", "yes"}


def _prompt_text(prompt: str, *, default: str, input_fn: Callable[[str], str]) -> str:
    answer = input_fn(f"{prompt} [{default}]: ").strip()
    return answer or default


def _resolve_choices(
    config: NomadCastConfig,
    *,
    pages_path: Path | None,
    input_fn: Callable[[str], str],
    logger: logging.Logger,
    is_interactive: bool,
) -> StarterPackChoices | None:
    detected_identity = detect_nomadnet_identity()
    identity_value = detected_identity.identity if detected_identity else ""
    if not identity_value:
        if not is_interactive:
            logger.info("NomadNet identity not found; using placeholder identity for starter pack.")
            identity_value = PLACEHOLDER_IDENTITY
        else:
            proceed = _prompt_yes_no(
                "No NomadNet identity found. Install starter pack with a placeholder? [y/N]: ",
                input_fn=input_fn,
            )
            if not proceed:
                return None
            identity_value = PLACEHOLDER_IDENTITY

    node_name = detect_nomadnet_node_name()
    default_show_name = node_name or "Nomad Node"
    show_name = (
        _prompt_text("Show name", default=default_show_name, input_fn=input_fn)
        if is_interactive
        else default_show_name
    )

    default_pages_path = pages_path or (config.nomadnet_root / "pages")
    selected_pages_path = (
        Path(_prompt_text("Pages destination", default=str(default_pages_path), input_fn=input_fn)).expanduser()
        if is_interactive and pages_path is None
        else default_pages_path
    )
    return StarterPackChoices(
        pages_path=selected_pages_path,
        show_name=show_name,
        identity=identity_value,
    )


def maybe_install_starter_pack(
    config: NomadCastConfig,
    *,
    is_interactive: bool,
    logger: logging.Logger,
    force: bool = False,
    pages_path: Path | None = None,
    input_fn: Callable[[str], str] = input,
) -> None:
    """Install the starter pack pages on first run or when forced."""
    if config.starter_pack_installed and not force:
        return
    if config.starter_pack_prompted and not force:
        return
    if not is_interactive and not force:
        logger.debug("Skipping starter pack prompt in non-interactive mode.")
        return

    if is_interactive and not force:
        should_install = _prompt_yes_no(
            "Install the starter pack pages now? [Y/n]: ",
            input_fn=input_fn,
        )
        if not should_install:
            set_starter_pack_state(config.config_path, prompted=True)
            return

    choices = _resolve_choices(
        config,
        pages_path=pages_path,
        input_fn=input_fn,
        logger=logger,
        is_interactive=is_interactive,
    )
    if choices is None:
        set_starter_pack_state(config.config_path, prompted=True)
        return

    show_slug = sanitize_show_name_for_path(choices.show_name)
    try:
        install_sample(
            storage_root=config.nomadnet_root,
            pages_path=choices.pages_path,
            identity=choices.identity,
            show_name=choices.show_name,
            show_name_slug=show_slug,
            replace_existing=False,
        )
    except FileExistsError as exc:
        logger.warning("Starter pack pages already exist: %s", exc)
        set_starter_pack_state(
            config.config_path,
            installed=True,
            prompted=True,
            pages_path=choices.pages_path,
        )
        return
    except OSError as exc:
        logger.error("Failed to install starter pack pages: %s", exc)
        set_starter_pack_state(config.config_path, prompted=True)
        return

    logger.info("Starter pack installed at %s", choices.pages_path)
    set_starter_pack_state(
        config.config_path,
        installed=True,
        prompted=True,
        pages_path=choices.pages_path,
    )
