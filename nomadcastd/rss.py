from __future__ import annotations

"""RSS parsing and rewrite helpers based on README rules.

We keep RSS structure intact and only rewrite enclosure URLs to localhost
media endpoints. In strict_cached_enclosures mode, only cached items are
advertised (README v0 cache policy).
"""

import email.utils
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import quote
from xml.etree import ElementTree

from nomadcastd.parsing import parse_nomadcast_media_url


@dataclass
class RssItem:
    element: ElementTree.Element
    enclosure_urls: list[str]
    pub_date: float | None


def _parse_pub_date(value: str | None) -> float | None:
    if not value:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        return parsed.timestamp()
    except (TypeError, ValueError):
        return None


def parse_rss_items(rss_bytes: bytes) -> tuple[ElementTree.ElementTree, list[RssItem]]:
    """Parse RSS bytes into a tree and item metadata for selection."""
    root = ElementTree.fromstring(rss_bytes)
    tree = ElementTree.ElementTree(root)
    items: list[RssItem] = []
    for item in root.findall(".//item"):
        enclosures = []
        for enclosure in item.findall("enclosure"):
            url = enclosure.get("url")
            if url:
                enclosures.append(url)
        pub_date = None
        pub_date_element = item.find("pubDate")
        if pub_date_element is not None:
            pub_date = _parse_pub_date(pub_date_element.text)
        items.append(RssItem(element=item, enclosure_urls=enclosures, pub_date=pub_date))
    return tree, items


def _sorted_items(items: list[RssItem]) -> list[RssItem]:
    """Sort items by pubDate when available (README: prefer recent episodes)."""
    if any(item.pub_date is not None for item in items):
        return sorted(
            items,
            key=lambda item: item.pub_date if item.pub_date is not None else 0,
            reverse=True,
        )
    return items


def rewrite_rss(
    rss_bytes: bytes,
    listen_host: str,
    listen_port: int,
    show_path: str,
    cached_filenames: set[str],
    episodes_per_show: int,
    strict_cached: bool,
) -> bytes:
    """Rewrite enclosure URLs to localhost and filter items per README rules."""
    tree, items = parse_rss_items(rss_bytes)
    root = tree.getroot()
    ordered_items = _sorted_items(items)
    allowed_items: list[ElementTree.Element] = []
    for item in ordered_items:
        if len(allowed_items) >= episodes_per_show:
            break
        include = True
        nomadcast_enclosures: list[tuple[ElementTree.Element, str]] = []
        for enclosure in item.element.findall("enclosure"):
            url = enclosure.get("url")
            if not url:
                continue
            try:
                _, _, filename = parse_nomadcast_media_url(url)
            except ValueError:
                continue
            nomadcast_enclosures.append((enclosure, filename))
        # README v0: strict_cached_enclosures means only include items whose
        # enclosures are fully cached. If no nomadcast enclosures exist, we
        # drop the item to avoid pointing clients to non-local media.
        if strict_cached:
            if not nomadcast_enclosures:
                include = False
            else:
                include = all(filename in cached_filenames for _, filename in nomadcast_enclosures)
        if include:
            allowed_items.append(item.element)
            for enclosure, filename in nomadcast_enclosures:
                encoded_filename = quote(filename, safe="")
                enclosure.set(
                    "url",
                    f"http://{listen_host}:{listen_port}/media/{show_path}/{encoded_filename}",
                )
    channel = root.find("channel")
    if channel is not None:
        for item in list(channel.findall("item")):
            channel.remove(item)
        for item in allowed_items:
            channel.append(item)
    return ElementTree.tostring(root, encoding="utf-8")


def extract_nomadcast_enclosures(items: Iterable[RssItem]) -> list[tuple[RssItem, str]]:
    enclosures: list[tuple[RssItem, str]] = []
    for item in items:
        for url in item.enclosure_urls:
            try:
                _, _, filename = parse_nomadcast_media_url(url)
            except ValueError:
                continue
            enclosures.append((item, filename))
    return enclosures
