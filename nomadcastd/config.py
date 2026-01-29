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
starter_pack_installed = no
starter_pack_prompted = no
starter_pack_pages_path =

[subscriptions]
uri =

[mirroring]
nomadnet_root = ~/.nomadnetwork/storage

[reticulum]
config_dir = ~/.reticulum
destination_app = nomadnetwork
destination_aspects = node
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
    starter_pack_installed: bool
    starter_pack_prompted: bool
    starter_pack_pages_path: Path | None
    nomadnet_root: Path
    mirror_enabled: bool | None
    no_mirror_uris: set[str]
    reticulum_config_dir: str | None
    reticulum_destination_app: str
    reticulum_destination_aspects: tuple[str, ...]
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


def _parse_optional_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    stripped = value.strip().lower()
    if not stripped:
        return None
    return stripped in {"1", "yes", "true", "on"}


def _load_config_parser(config_path: Path) -> configparser.ConfigParser:
    """Load the INI config file from disk."""
    parser = configparser.ConfigParser(strict=False, inline_comment_prefixes=("#", ";"))
    parser.read(config_path)
    return parser


def _get_string_value(
    section: configparser.SectionProxy | dict,
    key: str,
    default: str,
    config_path: Path,
    *,
    warn_if_blank: bool = False,
) -> str:
    if key in section:
        value = str(section.get(key, "")).strip()
        if not value:
            if warn_if_blank:
                logging.getLogger(__name__).warning(
                    "Config value for %s is blank in %s; using default %s.",
                    key,
                    config_path,
                    default,
                )
            return default
        return value
    return default


def _get_int_value(
    section: configparser.SectionProxy | dict,
    key: str,
    default: int,
    config_path: Path,
    *,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    if key not in section:
        return default
    raw_value = str(section.get(key, "")).strip()
    if not raw_value:
        logging.getLogger(__name__).warning(
            "Config value for %s is blank in %s; using default %s.",
            key,
            config_path,
            default,
        )
        return default
    try:
        parsed = int(raw_value)
    except ValueError:
        logging.getLogger(__name__).warning(
            "Config value for %s (%s) in %s is invalid; using default %s.",
            key,
            raw_value,
            config_path,
            default,
        )
        return default
    if min_value is not None and parsed < min_value:
        logging.getLogger(__name__).warning(
            "Config value for %s (%s) in %s is below %s; using default %s.",
            key,
            parsed,
            config_path,
            min_value,
            default,
        )
        return default
    if max_value is not None and parsed > max_value:
        logging.getLogger(__name__).warning(
            "Config value for %s (%s) in %s exceeds %s; using default %s.",
            key,
            parsed,
            config_path,
            max_value,
            default,
        )
        return default
    return parsed


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


def _load_no_mirror_uris(config_path: Path) -> set[str]:
    """Read multiple `no_mirror_uri = ...` lines from [mirroring]."""
    uris: set[str] = set()
    current_section = None
    for line in config_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped[1:-1].strip().lower()
            continue
        if current_section == "mirroring" and stripped.lower().startswith("no_mirror_uri"):
            if "=" in stripped:
                _, value = stripped.split("=", 1)
                uri = value.strip()
                if uri:
                    uris.add(uri)
    return uris


def load_config(config_path: Path | None = None) -> NomadCastConfig:
    """Load the NomadCast config using the README search order."""
    if config_path is None:
        env_override = os.getenv("NOMADCAST_CONFIG", "").strip()
        if env_override:
            config_path = Path(env_override).expanduser()
        else:
            config_path = next((path for path in DEFAULT_CONFIG_PATHS if path.exists()), None)
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATHS[-1]
    if not config_path.exists():
        ensure_default_config(config_path)
        logging.getLogger(__name__).info("Created default config at %s", config_path)

    parser = _load_config_parser(config_path)
    section = parser["nomadcast"] if parser.has_section("nomadcast") else {}

    # Defaults mirror README-required keys in [nomadcast].
    listen_host = _get_string_value(
        section,
        "listen_host",
        "127.0.0.1",
        config_path,
        warn_if_blank=True,
    )
    listen_port = _get_int_value(
        section,
        "listen_port",
        5050,
        config_path,
        min_value=1,
        max_value=65535,
    )
    storage_path = Path(
        os.path.expanduser(
            _get_string_value(
                section,
                "storage_path",
                "~/.nomadcast/storage",
                config_path,
                warn_if_blank=True,
            )
        )
    )
    episodes_per_show = _get_int_value(section, "episodes_per_show", 5, config_path, min_value=1)
    strict_cached_enclosures = _parse_bool(section.get("strict_cached_enclosures", "yes"), True)
    rss_poll_seconds = _get_int_value(section, "rss_poll_seconds", 900, config_path, min_value=1)
    retry_backoff_seconds = _get_int_value(
        section,
        "retry_backoff_seconds",
        300,
        config_path,
        min_value=1,
    )
    max_bytes_per_show = _get_int_value(section, "max_bytes_per_show", 0, config_path, min_value=0)
    public_host = section.get("public_host", "").strip() or None
    starter_pack_installed = _parse_bool(section.get("starter_pack_installed"), False)
    starter_pack_prompted = _parse_bool(section.get("starter_pack_prompted"), False)
    starter_pack_pages_value = _get_string_value(
        section,
        "starter_pack_pages_path",
        "",
        config_path,
    )
    starter_pack_pages_path = (
        Path(starter_pack_pages_value).expanduser() if starter_pack_pages_value else None
    )

    mirror_section = parser["mirroring"] if parser.has_section("mirroring") else {}
    nomadnet_root = Path(
        os.path.expanduser(
            _get_string_value(
                mirror_section,
                "nomadnet_root",
                "~/.nomadnetwork/storage",
                config_path,
                warn_if_blank=True,
            )
        )
    )
    mirror_enabled = _parse_optional_bool(mirror_section.get("enabled"))
    no_mirror_uris = _load_no_mirror_uris(config_path)

    reticulum_config_dir = None
    if parser.has_section("reticulum"):
        reticulum_config_dir = parser.get("reticulum", "config_dir", fallback="").strip() or None
        reticulum_destination_app = parser.get("reticulum", "destination_app", fallback="").strip()
        reticulum_destination_aspects = parser.get("reticulum", "destination_aspects", fallback="").strip()
    else:
        reticulum_destination_app = ""
        reticulum_destination_aspects = ""

    if not reticulum_destination_app:
        reticulum_destination_app = "nomadnetwork"
    aspects = tuple(
        aspect.strip()
        for aspect in reticulum_destination_aspects.split(",")
        if aspect.strip()
    )
    if not aspects:
        aspects = ("node",)

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
        starter_pack_installed=starter_pack_installed,
        starter_pack_prompted=starter_pack_prompted,
        starter_pack_pages_path=starter_pack_pages_path,
        nomadnet_root=nomadnet_root.expanduser(),
        mirror_enabled=mirror_enabled,
        no_mirror_uris=no_mirror_uris,
        reticulum_config_dir=reticulum_config_dir,
        reticulum_destination_app=reticulum_destination_app,
        reticulum_destination_aspects=aspects,
        config_path=config_path,
    )


def load_subscriptions(config_path: Path) -> list[str]:
    if not config_path.exists():
        ensure_default_config(config_path)
    return _load_subscription_uris(config_path)


def add_subscription_uri(config_path: Path, uri: str) -> bool:
    """Add a subscription URI to the NomadCast config.

    Returns True if the URI was added, False if it already existed.
    """
    ensure_default_config(config_path)
    existing = load_subscriptions(config_path)
    if uri in existing:
        return False

    lines = config_path.read_text(encoding="utf-8").splitlines()
    subscription_section_start: int | None = None
    subscription_section_end: int | None = None

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if subscription_section_start is not None and subscription_section_end is None:
                subscription_section_end = index
            section_name = stripped[1:-1].strip().lower()
            if section_name == "subscriptions":
                subscription_section_start = index

    if subscription_section_start is None:
        new_lines = lines + ["", "[subscriptions]", f"uri = {uri}"]
    else:
        if subscription_section_end is None:
            subscription_section_end = len(lines)
        new_lines = (
            lines[:subscription_section_end]
            + [f"uri = {uri}"]
            + lines[subscription_section_end:]
        )

    config_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return True


def remove_subscription_uri(config_path: Path, uri: str) -> bool:
    """Remove a subscription URI from the NomadCast config.

    Returns True if the URI was removed, False if it was not found.
    """
    ensure_default_config(config_path)
    lines = config_path.read_text(encoding="utf-8").splitlines()
    new_lines: list[str] = []
    current_section: str | None = None
    removed = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped[1:-1].strip().lower()
            new_lines.append(line)
            continue

        if current_section == "subscriptions" and stripped.lower().startswith("uri"):
            if "=" in stripped:
                _, value = stripped.split("=", 1)
                existing_uri = value.strip()
                if existing_uri == uri:
                    removed = True
                    continue

        new_lines.append(line)

    if removed:
        config_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        remove_no_mirror_uri(config_path, uri)
    return removed


def set_mirroring_enabled(config_path: Path, enabled: bool) -> None:
    """Set the [mirroring] enabled value in the NomadCast config file."""
    ensure_default_config(config_path)
    lines = config_path.read_text(encoding="utf-8").splitlines()
    mirroring_section_start: int | None = None
    mirroring_section_end: int | None = None
    enabled_index: int | None = None
    in_mirroring = False

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_mirroring and mirroring_section_end is None:
                mirroring_section_end = index
            section_name = stripped[1:-1].strip().lower()
            in_mirroring = section_name == "mirroring"
            if in_mirroring:
                mirroring_section_start = index
            continue

        if in_mirroring and "=" in stripped:
            key, _ = stripped.split("=", 1)
            if key.strip().lower() == "enabled":
                enabled_index = index

    rendered_value = "yes" if enabled else "no"
    if mirroring_section_start is None:
        new_lines = lines + ["", "[mirroring]", f"enabled = {rendered_value}"]
    else:
        if mirroring_section_end is None:
            mirroring_section_end = len(lines)
        if enabled_index is not None:
            lines[enabled_index] = f"enabled = {rendered_value}"
            new_lines = lines
        else:
            new_lines = (
                lines[:mirroring_section_end]
                + [f"enabled = {rendered_value}"]
                + lines[mirroring_section_end:]
            )

    config_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def add_no_mirror_uri(config_path: Path, uri: str) -> bool:
    """Add a no-mirror override for a subscription URI."""
    ensure_default_config(config_path)
    existing = _load_no_mirror_uris(config_path)
    if uri in existing:
        return False

    lines = config_path.read_text(encoding="utf-8").splitlines()
    mirroring_section_start: int | None = None
    mirroring_section_end: int | None = None

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if mirroring_section_start is not None and mirroring_section_end is None:
                mirroring_section_end = index
            section_name = stripped[1:-1].strip().lower()
            if section_name == "mirroring":
                mirroring_section_start = index

    if mirroring_section_start is None:
        new_lines = lines + ["", "[mirroring]", f"no_mirror_uri = {uri}"]
    else:
        if mirroring_section_end is None:
            mirroring_section_end = len(lines)
        new_lines = (
            lines[:mirroring_section_end]
            + [f"no_mirror_uri = {uri}"]
            + lines[mirroring_section_end:]
        )

    config_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return True


def remove_no_mirror_uri(config_path: Path, uri: str) -> bool:
    """Remove a no-mirror override for a subscription URI."""
    ensure_default_config(config_path)
    lines = config_path.read_text(encoding="utf-8").splitlines()
    new_lines: list[str] = []
    current_section: str | None = None
    removed = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped[1:-1].strip().lower()
            new_lines.append(line)
            continue

        if current_section == "mirroring" and stripped.lower().startswith("no_mirror_uri"):
            if "=" in stripped:
                _, value = stripped.split("=", 1)
                existing_uri = value.strip()
                if existing_uri == uri:
                    removed = True
                    continue

        new_lines.append(line)

    if removed:
        config_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return removed


def set_reticulum_config_dir(config_path: Path, config_dir: Path) -> None:
    """Set the [reticulum] config_dir value in the NomadCast config file."""
    ensure_default_config(config_path)
    lines = config_path.read_text(encoding="utf-8").splitlines()
    reticulum_section_start: int | None = None
    reticulum_section_end: int | None = None
    config_dir_index: int | None = None
    in_reticulum = False

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_reticulum and reticulum_section_end is None:
                reticulum_section_end = index
            section_name = stripped[1:-1].strip().lower()
            in_reticulum = section_name == "reticulum"
            if in_reticulum:
                reticulum_section_start = index
            continue

        if in_reticulum and "=" in stripped:
            key, _ = stripped.split("=", 1)
            if key.strip().lower() == "config_dir":
                config_dir_index = index

    rendered_value = str(config_dir)
    if reticulum_section_start is None:
        new_lines = lines + ["", "[reticulum]", f"config_dir = {rendered_value}"]
    else:
        if reticulum_section_end is None:
            reticulum_section_end = len(lines)
        if config_dir_index is not None:
            lines[config_dir_index] = f"config_dir = {rendered_value}"
            new_lines = lines
        else:
            new_lines = (
                lines[:reticulum_section_end]
                + [f"config_dir = {rendered_value}"]
                + lines[reticulum_section_end:]
            )

    config_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def _set_nomadcast_value(config_path: Path, key: str, value: str) -> None:
    """Set a [nomadcast] key in the config file."""
    ensure_default_config(config_path)
    lines = config_path.read_text(encoding="utf-8").splitlines()
    nomadcast_section_start: int | None = None
    nomadcast_section_end: int | None = None
    key_index: int | None = None
    in_nomadcast = False

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_nomadcast and nomadcast_section_end is None:
                nomadcast_section_end = index
            section_name = stripped[1:-1].strip().lower()
            in_nomadcast = section_name == "nomadcast"
            if in_nomadcast:
                nomadcast_section_start = index
            continue

        if in_nomadcast and "=" in stripped:
            key_name, _ = stripped.split("=", 1)
            if key_name.strip().lower() == key.lower():
                key_index = index

    rendered_value = value
    if nomadcast_section_start is None:
        new_lines = lines + ["", "[nomadcast]", f"{key} = {rendered_value}"]
    else:
        if nomadcast_section_end is None:
            nomadcast_section_end = len(lines)
        if key_index is not None:
            lines[key_index] = f"{key} = {rendered_value}"
            new_lines = lines
        else:
            new_lines = (
                lines[:nomadcast_section_end]
                + [f"{key} = {rendered_value}"]
                + lines[nomadcast_section_end:]
            )

    config_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def set_starter_pack_state(
    config_path: Path,
    *,
    installed: bool | None = None,
    prompted: bool | None = None,
    pages_path: Path | None = None,
) -> None:
    """Persist starter pack metadata in the [nomadcast] config section."""
    if installed is not None:
        _set_nomadcast_value(config_path, "starter_pack_installed", "yes" if installed else "no")
    if prompted is not None:
        _set_nomadcast_value(config_path, "starter_pack_prompted", "yes" if prompted else "no")
    if pages_path is not None:
        _set_nomadcast_value(config_path, "starter_pack_pages_path", str(pages_path))
