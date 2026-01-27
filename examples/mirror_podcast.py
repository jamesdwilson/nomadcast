#!/usr/bin/env python3
"""
One-shot NomadCast mirror script (manual sync).

This script only runs when executed manually. It checks the timestamp of the
last successful sync and exits if the mirror is newer than the freshness
threshold. Otherwise, it fetches the parent RSS feed, downloads missing or
updated enclosures, and regenerates a local RSS feed if changes are detected.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


# ==== Configuration (pre-filled by NomadCast) ====
MIRROR_NAME = "ExampleNomadCastPodcast"
PRIMARY_RSS = "https://example.com/podcast/feed.rss"
FALLBACK_RSS = [
    # "https://mirror1.example.com/podcast/feed.rss",
]
FRESHNESS_HOURS = 12
# ===============================================


STATE_FILENAME = ".mirror_state.json"
DEFAULT_USER_AGENT = "NomadCastMirror/1.0 (+https://github.com/jamesdwilson/nomadcast)"
RSS_TIMEOUT_SECONDS = 20
DOWNLOAD_TIMEOUT_SECONDS = 60
CHUNK_SIZE = 1024 * 256


def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _load_state(state_path: Path) -> dict:
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state_path: Path, state: dict) -> None:
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _is_fresh(state: dict, threshold_hours: int) -> bool:
    last_sync = state.get("last_sync")
    if not last_sync:
        return False
    try:
        last_dt = dt.datetime.fromisoformat(last_sync)
    except ValueError:
        return False
    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=dt.timezone.utc)
    return (_now_utc() - last_dt) < dt.timedelta(hours=threshold_hours)


def _request(url: str, method: str = "GET") -> urllib.request.Request:
    return urllib.request.Request(
        url,
        method=method,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
        },
    )


def _fetch_rss(urls: list[str]) -> tuple[str, bytes]:
    last_error = None
    for url in urls:
        try:
            with urllib.request.urlopen(_request(url), timeout=RSS_TIMEOUT_SECONDS) as response:
                return url, response.read()
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            print(f"[warn] failed to fetch RSS from {url}: {exc}", file=sys.stderr)
            last_error = exc
    raise RuntimeError("Unable to fetch RSS from any source") from last_error


def _findall(parent: ET.Element, tag: str) -> list[ET.Element]:
    return parent.findall(f".//{{*}}{tag}")


def _find(parent: ET.Element, tag: str) -> ET.Element | None:
    return parent.find(f".//{{*}}{tag}")


def _head_metadata(url: str) -> dict[str, str | int | None]:
    try:
        with urllib.request.urlopen(_request(url, method="HEAD"), timeout=RSS_TIMEOUT_SECONDS) as response:
            size = response.headers.get("Content-Length")
            etag = response.headers.get("ETag")
            return {
                "size": int(size) if size and size.isdigit() else None,
                "etag": etag,
            }
    except (urllib.error.URLError, urllib.error.HTTPError):
        return {"size": None, "etag": None}


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, destination: Path) -> dict[str, str | int]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_name(f"{destination.name}.part")
    digest = hashlib.sha256()
    size = 0
    try:
        with urllib.request.urlopen(_request(url), timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            with temp_path.open("wb") as handle:
                while True:
                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    handle.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
        temp_path.replace(destination)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return {"size": size, "sha256": digest.hexdigest()}


def _sanitize_filename(url: str, guid: str | None) -> str:
    parsed = urllib.parse.urlparse(url)
    name = os.path.basename(parsed.path)
    if name:
        return name
    if guid:
        return f"{guid}.bin".replace(os.sep, "_")
    return f"episode-{int(time.time())}.bin"


def main() -> int:
    mirror_root = (
        Path.home()
        / ".nomadnetwork"
        / "storage"
        / "files"
        / MIRROR_NAME
    )
    media_dir = mirror_root / "media"
    state_path = mirror_root / STATE_FILENAME
    mirror_root.mkdir(parents=True, exist_ok=True)

    state = _load_state(state_path)
    if _is_fresh(state, FRESHNESS_HOURS):
        print(f"[info] mirror fresh (< {FRESHNESS_HOURS}h). nothing to do.")
        return 0

    rss_url, rss_bytes = _fetch_rss([PRIMARY_RSS, *FALLBACK_RSS])
    print(f"[info] using RSS source: {rss_url}")

    root = ET.fromstring(rss_bytes)
    channel = _find(root, "channel")
    if channel is None:
        print("[error] RSS channel not found.", file=sys.stderr)
        return 1

    items = _findall(channel, "item")
    if not items:
        print("[warn] no items found in RSS feed.")

    files_state = state.get("files", {})
    changes_detected = False
    downloaded = 0

    for item in items:
        guid_elem = _find(item, "guid")
        guid = guid_elem.text.strip() if guid_elem is not None and guid_elem.text else None

        enclosure = _find(item, "enclosure")
        if enclosure is None:
            continue
        enclosure_url = enclosure.attrib.get("url")
        if not enclosure_url:
            continue

        filename = _sanitize_filename(enclosure_url, guid)
        local_path = media_dir / filename
        metadata = files_state.get(enclosure_url, {})
        remote_meta = _head_metadata(enclosure_url)

        local_exists = local_path.exists()
        if local_exists:
            local_size = local_path.stat().st_size
            if remote_meta["size"] and local_size == remote_meta["size"]:
                continue
            if metadata.get("sha256") and _hash_file(local_path) == metadata["sha256"]:
                continue
            if metadata.get("etag") and remote_meta.get("etag") == metadata["etag"]:
                continue

        print(f"[info] downloading {enclosure_url} -> {local_path}")
        download_meta = _download(enclosure_url, local_path)
        files_state[enclosure_url] = {
            "filename": filename,
            "size": download_meta["size"],
            "sha256": download_meta["sha256"],
            "etag": remote_meta.get("etag"),
            "guid": guid,
        }
        downloaded += 1
        changes_detected = True

    # Update enclosures in RSS to point to local media path.
    for item in items:
        enclosure = _find(item, "enclosure")
        if enclosure is None:
            continue
        enclosure_url = enclosure.attrib.get("url")
        if not enclosure_url:
            continue
        guid_elem = _find(item, "guid")
        guid = guid_elem.text.strip() if guid_elem is not None and guid_elem.text else None
        filename = _sanitize_filename(enclosure_url, guid)
        enclosure.attrib["url"] = f"media/{filename}"
        if (media_dir / filename).exists():
            enclosure.attrib["length"] = str((media_dir / filename).stat().st_size)

    rss_path = mirror_root / "feed.rss"
    rss_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    if rss_path.exists():
        if rss_path.read_bytes() != rss_xml:
            rss_path.write_bytes(rss_xml)
            changes_detected = True
    else:
        rss_path.write_bytes(rss_xml)
        changes_detected = True

    state["last_sync"] = _now_utc().isoformat()
    state["files"] = files_state
    _save_state(state_path, state)

    if changes_detected:
        print(f"[info] sync complete; {downloaded} file(s) downloaded.")
    else:
        print("[info] sync complete; no changes detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
