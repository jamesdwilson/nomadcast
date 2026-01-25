from __future__ import annotations

import configparser
import logging
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATHS = [
    Path("/etc/nomadcast/config"),
    Path("~/.config/nomadcast/config").expanduser(),
    Path("~/.nomadcast/config").expanduser(),
]

DEFAULT_CONFIG = """[nomadcast]
# Default configuration aligned with README "Configuration (must implement)" and
# "Binding behavior requirement" sections. The daemon must create this file if
# no config exists (Reticulum-style search order in README).
listen_host = 127.0.0.1  # use 0.0.0.0 to bind publicly (eg to test from a phone on your LAN). this exposes your local feed server; do not use on untrusted networks.
listen_port = 5050
storage_path = ~/.nomadcast/storage
episodes_per_show = 5
strict_cached_enclosures = yes
rss_poll_seconds = 900
retry_backoff_seconds = 300
max_bytes_per_show = 0
public_host =

[subscriptions]
uri =

[reticulum]
config_dir =
"""


@dataclass(frozen=True)
class NomadCastConfig:
    listen_host: str
    listen_port: int
    storage_path: Path
    episodes_per_show: int
    strict_cached_enclosures: bool
    rss_poll_seconds: int
    retry_backoff_seconds: int
    max_bytes_per_show: int
    public_host: str | None
    reticulum_config_dir: str | None
    config_path: Path


def ensure_default_config(config_path: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if not config_path.exists():
        config_path.write_text(DEFAULT_CONFIG, encoding="utf-8")


def _parse_bool(value: str | None, default: bool) -> bool:
    """Parse a Reticulum-style boolean value used in the README config."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "yes", "true", "on"}


def _load_config_parser(config_path: Path) -> configparser.ConfigParser:
    """Load the INI config file from disk."""
    parser = configparser.ConfigParser()
    parser.read(config_path)
    return parser


def _load_subscription_uris(config_path: Path) -> list[str]:
    """Read multiple `uri = ...` lines from [subscriptions].

    README explicitly allows multiple `uri` lines, so we parse by hand to keep
    duplicates and ordering intact.
    """
    uris: list[str] = []
    current_section = None
    for line in config_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped[1:-1].strip().lower()
            continue
        if current_section == "subscriptions" and stripped.lower().startswith("uri"):
            if "=" in stripped:
                _, value = stripped.split("=", 1)
                uri = value.strip()
                if uri:
                    uris.append(uri)
    return uris


def load_config(config_path: Path | None = None) -> NomadCastConfig:
    """Load the NomadCast config using the README search order."""
    if config_path is None:
        config_path = next((path for path in DEFAULT_CONFIG_PATHS if path.exists()), None)
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATHS[-1]
    if not config_path.exists():
        ensure_default_config(config_path)
        logging.getLogger(__name__).info("Created default config at %s", config_path)

    parser = _load_config_parser(config_path)
    section = parser["nomadcast"] if parser.has_section("nomadcast") else {}

    # Defaults mirror README-required keys in [nomadcast].
    listen_host = section.get("listen_host", "127.0.0.1").strip()
    listen_port = int(section.get("listen_port", "5050"))
    storage_path = Path(os.path.expanduser(section.get("storage_path", "~/.nomadcast/storage")))
    episodes_per_show = int(section.get("episodes_per_show", "5"))
    strict_cached_enclosures = _parse_bool(section.get("strict_cached_enclosures", "yes"), True)
    rss_poll_seconds = int(section.get("rss_poll_seconds", "900"))
    retry_backoff_seconds = int(section.get("retry_backoff_seconds", "300"))
    max_bytes_per_show = int(section.get("max_bytes_per_show", "0"))
    public_host = section.get("public_host", "").strip() or None

    reticulum_config_dir = None
    if parser.has_section("reticulum"):
        reticulum_config_dir = parser.get("reticulum", "config_dir", fallback="").strip() or None

    return NomadCastConfig(
        listen_host=listen_host,
        listen_port=listen_port,
        storage_path=storage_path.expanduser(),
        episodes_per_show=episodes_per_show,
        strict_cached_enclosures=strict_cached_enclosures,
        rss_poll_seconds=rss_poll_seconds,
        retry_backoff_seconds=retry_backoff_seconds,
        max_bytes_per_show=max_bytes_per_show,
        public_host=public_host,
        reticulum_config_dir=reticulum_config_dir,
        config_path=config_path,
    )


def load_subscriptions(config_path: Path) -> list[str]:
    if not config_path.exists():
        ensure_default_config(config_path)
    return _load_subscription_uris(config_path)
