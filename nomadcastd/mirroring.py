from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import quote, urlparse
from xml.etree import ElementTree

from nomadcastd.config import NomadCastConfig, set_mirroring_enabled
from nomadcastd.parsing import Subscription, encode_show_path, parse_nomadcast_media_url, parse_subscription_uri
from nomadcastd.rss import parse_rss_items
from nomadcastd.storage import write_atomic, show_directory

MIRROR_WARNING = (
    "Mirroring is how we build a resilient, decentralized future. NomadCast "
    "will download and store episodes on disk and share them to other "
    "Reticulum peers via your Nomad Network pages, so only turn this on if "
    "you are good with the disk use and serving that content onward."
)
REPO_URL = "https://github.com/jamesdwilson/nomadcast"
INDEX_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "nomadnet_index.mu"
DEFAULT_PLACEHOLDER = "—"
DEFAULT_LINK = "#"
MAX_INDEX_ENTRIES = 10
EPISODE_PREVIEW_COUNT = 3


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


def _load_rss_channel(rss_path: Path) -> ElementTree.Element | None:
    if not rss_path.exists():
        return None
    try:
        root = ElementTree.fromstring(rss_path.read_bytes())
    except ElementTree.ParseError:
        return None
    return root.find("channel")


def _origin_rss_href(subscription: Subscription, channel: ElementTree.Element | None) -> str:
    if channel is not None:
        for atom_link in channel.findall("{http://www.w3.org/2005/Atom}link"):
            if atom_link.get("rel") == "self" and atom_link.get("href"):
                return atom_link.get("href", DEFAULT_LINK)
    return f"/file/{subscription.show_name}/feed.rss"


def _origin_site_href(subscription: Subscription, channel: ElementTree.Element | None) -> str:
    if channel is None:
        return f"/file/{subscription.show_name}/index.mu"
    link = channel.findtext("link")
    if link:
        return link.strip()
    return f"/file/{subscription.show_name}/index.mu"


def _origin_site_name(channel: ElementTree.Element | None, fallback: str) -> str:
    if channel is None:
        return fallback
    link = channel.findtext("link")
    if link:
        parsed = urlparse(link)
        if parsed.netloc:
            return parsed.netloc
    title = channel.findtext("title")
    if title:
        return title.strip()
    return fallback


def _subscription_title(config: NomadCastConfig, subscription: Subscription) -> str:
    show_dir = show_directory(config.storage_path, subscription.destination_hash)
    rss_title = _load_rss_title(show_dir / "publisher_rss.xml")
    if rss_title:
        return rss_title
    if subscription.show_name:
        return subscription.show_name
    return subscription.uri


def _load_index_template() -> str:
    if not INDEX_TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Missing NomadNet index template at {INDEX_TEMPLATE_PATH}")
    return INDEX_TEMPLATE_PATH.read_text(encoding="utf-8")


def _mirror_media_href(subscription: Subscription, filename: str) -> str:
    show_path = encode_show_path(subscription.destination_hash, subscription.show_name)
    encoded_filename = quote(filename, safe="")
    return f"/file/nomadcast/{show_path}/media/{encoded_filename}"


def _sorted_rss_items(items: list) -> list:
    if any(item.pub_date is not None for item in items):
        return sorted(
            items,
            key=lambda item: item.pub_date if item.pub_date is not None else 0,
            reverse=True,
        )
    return items


def _episode_previews(
    rss_path: Path,
    episodes_dir: Path,
    subscription: Subscription,
    *,
    mirrored: bool,
    max_count: int,
) -> list[tuple[str, str]]:
    if not rss_path.exists() or not mirrored:
        return []
    try:
        rss_bytes = rss_path.read_bytes()
    except OSError:
        return []
    try:
        _, items = parse_rss_items(rss_bytes)
    except ElementTree.ParseError:
        return []
    previews: list[tuple[str, str]] = []
    for item in _sorted_rss_items(items):
        if len(previews) >= max_count:
            break
        title = item.element.findtext("title")
        if not title:
            continue
        filename = None
        for url in item.enclosure_urls:
            try:
                dest_hash, show_name, media_filename = parse_nomadcast_media_url(url)
            except ValueError:
                continue
            if dest_hash == subscription.destination_hash and show_name == subscription.show_name:
                filename = media_filename
                break
        if not filename:
            continue
        if not (episodes_dir / filename).exists():
            continue
        previews.append((title.strip(), _mirror_media_href(subscription, filename)))
    return previews


def _render_template(template: str, mapping: dict[str, str]) -> str:
    content = template
    for key, value in mapping.items():
        content = content.replace(f"{{{{{key}}}}}", value)
    return content


def render_nomadnet_index(
    config: NomadCastConfig,
    subscriptions: list[Subscription],
    *,
    default_mirroring_enabled: bool,
) -> str:
    template = _load_index_template()
    mapping: dict[str, str] = {}
    for index in range(1, MAX_INDEX_ENTRIES + 1):
        mapping[f"PodcastName_{index}"] = DEFAULT_PLACEHOLDER
        mapping[f"OriginSiteName_{index}"] = DEFAULT_PLACEHOLDER
        mapping[f"OriginSiteHref_{index}"] = DEFAULT_LINK
        mapping[f"OriginRssHref_{index}"] = DEFAULT_LINK
        mapping[f"MirrorRssHref_{index}"] = DEFAULT_LINK
    for index in range(1, EPISODE_PREVIEW_COUNT + 1):
        for suffix in ("a", "b", "c"):
            mapping[f"EpTitle_{index}{suffix}"] = DEFAULT_PLACEHOLDER
            mapping[f"EpPlayHref_{index}{suffix}"] = DEFAULT_LINK
    for slot_index, subscription in enumerate(subscriptions[:MAX_INDEX_ENTRIES], start=1):
        title = _subscription_title(config, subscription)
        show_dir = show_directory(config.storage_path, subscription.destination_hash)
        rss_path = show_dir / "publisher_rss.xml"
        channel = _load_rss_channel(rss_path)
        mirrored = should_mirror_subscription(config, subscription.uri, default_mirroring_enabled)
        mapping[f"PodcastName_{slot_index}"] = title
        mapping[f"OriginSiteHref_{slot_index}"] = _origin_site_href(subscription, channel)
        mapping[f"OriginSiteName_{slot_index}"] = _origin_site_name(channel, title)
        mapping[f"OriginRssHref_{slot_index}"] = _origin_rss_href(subscription, channel)
        mapping[f"MirrorRssHref_{slot_index}"] = (
            mirror_rss_href(subscription) if mirrored else DEFAULT_LINK
        )
        if slot_index <= EPISODE_PREVIEW_COUNT:
            episodes_dir = show_dir / "episodes"
            previews = _episode_previews(
                rss_path,
                episodes_dir,
                subscription,
                mirrored=mirrored,
                max_count=EPISODE_PREVIEW_COUNT,
            )
            for idx, (episode_title, play_href) in enumerate(previews):
                suffix = chr(ord("a") + idx)
                mapping[f"EpTitle_{slot_index}{suffix}"] = episode_title
                mapping[f"EpPlayHref_{slot_index}{suffix}"] = play_href
    rendered = _render_template(template, mapping)
    return rendered.rstrip() + "\n"


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
