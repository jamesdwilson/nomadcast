from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from xml.etree import ElementTree

from nomadcastd.config import NomadCastConfig, set_mirroring_enabled
from nomadcastd.parsing import Subscription, encode_show_path, parse_subscription_uri
from nomadcastd.storage import write_atomic, show_directory

MIRROR_WARNING = (
    "Mirroring is how we build a resilient, decentralized future. NomadCast "
    "will download and store episodes on disk and share them to other "
    "Reticulum peers via your Nomad Network pages, so only turn this on if "
    "you are good with the disk use and serving that content onward."
)
REPO_URL = "https://github.com/jamesdwilson/nomadcast"


@dataclass(frozen=True)
class NomadnetPaths:
    root: Path
    pages_dir: Path
    files_dir: Path


def nomadnet_paths(config: NomadCastConfig) -> NomadnetPaths:
    root = config.nomadnet_root
    return NomadnetPaths(
        root=root,
        pages_dir=root / "pages",
        files_dir=root / "files",
    )


def resolve_mirroring_enabled(
    config: NomadCastConfig,
    *,
    input_fn: Callable[[str], str] = input,
    is_interactive: bool | None = None,
    logger: logging.Logger | None = None,
) -> bool:
    if config.mirror_enabled is not None:
        return config.mirror_enabled
    if is_interactive is None:
        is_interactive = sys.stdin.isatty()
    if logger is None:
        logger = logging.getLogger(__name__)
    if is_interactive:
        print(MIRROR_WARNING)
        answer = input_fn("Enable mirroring for all podcasts going forward? [Y/n]: ").strip().lower()
        enabled = answer not in {"n", "no"}
        set_mirroring_enabled(config.config_path, enabled)
        return enabled
    logger.info(
        "Mirroring enabled by default; disable with --no-mirror or set mirroring.enabled = no in %s",
        config.config_path,
    )
    return True


def should_mirror_subscription(
    config: NomadCastConfig,
    subscription_uri: str,
    default_enabled: bool,
) -> bool:
    if subscription_uri in config.no_mirror_uris:
        return False
    if config.mirror_enabled is None:
        return default_enabled
    return config.mirror_enabled


def mirror_show_root(config: NomadCastConfig, subscription: Subscription) -> Path:
    show_path = encode_show_path(subscription.destination_hash, subscription.show_name)
    return nomadnet_paths(config).files_dir / "nomadcast" / show_path


def mirror_rss_link_path(config: NomadCastConfig, subscription: Subscription) -> Path:
    return mirror_show_root(config, subscription) / "feed.rss"


def mirror_media_link_path(config: NomadCastConfig, subscription: Subscription, filename: str) -> Path:
    return mirror_show_root(config, subscription) / "media" / filename


def mirror_rss_href(subscription: Subscription) -> str:
    show_path = encode_show_path(subscription.destination_hash, subscription.show_name)
    return f"/file/nomadcast/{show_path}/feed.rss"


def ensure_symlink(target: Path, link_path: Path) -> bool:
    if not target.exists():
        return False
    link_path.parent.mkdir(parents=True, exist_ok=True)
    if link_path.is_symlink():
        if link_path.resolve() == target.resolve():
            return False
        link_path.unlink()
    elif link_path.exists():
        return False
    try:
        relative_target = Path(os.path.relpath(target, start=link_path.parent))
    except ValueError:
        relative_target = target
    link_path.symlink_to(relative_target)
    return True


def _load_rss_title(rss_path: Path) -> str | None:
    if not rss_path.exists():
        return None
    try:
        root = ElementTree.fromstring(rss_path.read_bytes())
    except ElementTree.ParseError:
        return None
    channel = root.find("channel")
    if channel is None:
        return None
    title = channel.findtext("title")
    if title:
        return title.strip()
    return None


def _subscription_title(config: NomadCastConfig, subscription: Subscription) -> str:
    show_dir = show_directory(config.storage_path, subscription.destination_hash)
    rss_title = _load_rss_title(show_dir / "publisher_rss.xml")
    if rss_title:
        return rss_title
    if subscription.show_name:
        return subscription.show_name
    return subscription.uri


def render_nomadnet_index(
    config: NomadCastConfig,
    subscriptions: list[Subscription],
    *,
    default_mirroring_enabled: bool,
) -> str:
    lines = [
        "# NomadCast",
        "subscriptions on this node",
        f"[GitHub]({REPO_URL})",
        "",
    ]
    for subscription in subscriptions:
        title = _subscription_title(config, subscription)
        parts = [title]
        if should_mirror_subscription(config, subscription.uri, default_mirroring_enabled):
            parts.append(f"[mirror]({mirror_rss_href(subscription)})")
        parts.append(f"[source]({subscription.uri})")
        lines.append(" ".join(parts))
    return "\n".join(lines).rstrip() + "\n"


def write_nomadnet_index(
    config: NomadCastConfig,
    subscriptions: list[Subscription],
    *,
    default_mirroring_enabled: bool,
) -> Path:
    content = render_nomadnet_index(
        config,
        subscriptions,
        default_mirroring_enabled=default_mirroring_enabled,
    )
    pages_dir = nomadnet_paths(config).pages_dir
    index_path = pages_dir / "nomadcast" / "index.mu"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(index_path, content.encode("utf-8"))
    return index_path


def sync_nomadnet_mirror(
    config: NomadCastConfig,
    subscription: Subscription,
    *,
    default_mirroring_enabled: bool,
) -> None:
    if not should_mirror_subscription(config, subscription.uri, default_mirroring_enabled):
        return
    show_dir = show_directory(config.storage_path, subscription.destination_hash)
    rss_source = show_dir / "publisher_rss.xml"
    ensure_symlink(rss_source, mirror_rss_link_path(config, subscription))
    episodes_dir = show_dir / "episodes"
    if episodes_dir.exists():
        for entry in episodes_dir.iterdir():
            if entry.is_file():
                ensure_symlink(entry, mirror_media_link_path(config, subscription, entry.name))


def parse_subscriptions(subscription_uris: list[str]) -> list[Subscription]:
    subscriptions: list[Subscription] = []
    for uri in subscription_uris:
        try:
            subscriptions.append(parse_subscription_uri(uri))
        except ValueError:
            continue
    return subscriptions
