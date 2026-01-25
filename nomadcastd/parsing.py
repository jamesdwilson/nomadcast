from __future__ import annotations

"""Parsing helpers tied to README's NomadCast locator format.

The README specifies:
- Subscription URI: nomadcast:<DEST_HASH>:<SHOW_NAME>/rss
- Media URI: nomadcast:<DEST_HASH>:<SHOW_NAME>/media/<FILENAME>
- HTTP show_path: URL-encoded DEST_HASH:SHOW_NAME as one segment
"""

import re
from dataclasses import dataclass
from urllib.parse import quote, unquote

NOMADCAST_PREFIX = "nomadcast:"
NOMADCAST_URL_PREFIX = "nomadcast://"
RSS_SUFFIX = "/rss"
MEDIA_PREFIX = "/media/"
MIN_DEST_HASH_LEN = 32
DEST_HASH_RE = re.compile(r"^[0-9a-fA-F]+$")
FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class Subscription:
    uri: str
    destination_hash: str
    show_name: str

    @property
    def show_id(self) -> str:
        return f"{self.destination_hash}:{self.show_name}"


def _strip_nomadcast_prefix(value: str) -> str:
    if value.startswith(NOMADCAST_URL_PREFIX):
        return value[len(NOMADCAST_URL_PREFIX) :]
    if value.startswith(NOMADCAST_PREFIX):
        return value[len(NOMADCAST_PREFIX) :]
    raise ValueError("NomadCast URL must start with nomadcast:")


def parse_subscription_uri(uri: str) -> Subscription:
    """Parse the README-defined subscription URI format."""
    if not uri.endswith(RSS_SUFFIX):
        raise ValueError("Subscription URI must end with /rss")
    body = _strip_nomadcast_prefix(uri[:-len(RSS_SUFFIX)])
    if ":" not in body:
        raise ValueError("Subscription URI must include destination hash and show name")
    destination_hash, show_name = body.split(":", 1)
    if len(destination_hash) < MIN_DEST_HASH_LEN or not DEST_HASH_RE.match(destination_hash):
        raise ValueError("Destination hash must be hex and at least 32 characters")
    if not show_name:
        raise ValueError("Show name is required")
    return Subscription(uri=uri, destination_hash=destination_hash, show_name=show_name)


def normalize_subscription_input(raw_input: str) -> str:
    """Normalize a user-provided locator into a full subscription URI.

    The README allows users to paste either:
    - nomadcast:<DEST_HASH>:<SHOW_NAME>/rss
    - nomadcast://<DEST_HASH>:<SHOW_NAME>/rss
    - <DEST_HASH>:<SHOW_NAME>
    """
    trimmed = raw_input.strip()
    if not trimmed:
        raise ValueError("Subscription locator cannot be empty")

    if trimmed.startswith(NOMADCAST_URL_PREFIX):
        trimmed = f"{NOMADCAST_PREFIX}{trimmed[len(NOMADCAST_URL_PREFIX):]}"

    if trimmed.startswith(NOMADCAST_PREFIX):
        if trimmed.endswith(RSS_SUFFIX):
            return trimmed
        if MEDIA_PREFIX in trimmed:
            raise ValueError("Media URLs are not valid subscription locators")
        return f"{trimmed.rstrip('/')}{RSS_SUFFIX}"

    if ":" not in trimmed:
        raise ValueError("Locator must include destination hash and show name")

    return f"{NOMADCAST_PREFIX}{trimmed}{RSS_SUFFIX}"


def encode_show_path(destination_hash: str, show_name: str) -> str:
    """Encode DEST_HASH:SHOW_NAME into a single URL path segment."""
    return quote(f"{destination_hash}:{show_name}", safe="")


def decode_show_path(show_path: str) -> tuple[str, str]:
    """Decode a show_path back into destination hash and show name."""
    decoded = unquote(show_path)
    if ":" not in decoded:
        raise ValueError("Show path must include destination hash and show name")
    destination_hash, show_name = decoded.split(":", 1)
    if len(destination_hash) < MIN_DEST_HASH_LEN or not DEST_HASH_RE.match(destination_hash):
        raise ValueError("Destination hash must be hex and at least 32 characters")
    if not show_name:
        raise ValueError("Show name is required")
    return destination_hash, show_name


def parse_nomadcast_media_url(url: str) -> tuple[str, str, str]:
    """Parse a nomadcast media URL and validate its filename."""
    if MEDIA_PREFIX not in url:
        raise ValueError("Not a nomadcast media URL")
    prefix, filename = url.split(MEDIA_PREFIX, 1)
    body = _strip_nomadcast_prefix(prefix)
    if ":" not in body:
        raise ValueError("Media URL must include destination hash and show name")
    destination_hash, show_name = body.split(":", 1)
    if len(destination_hash) < MIN_DEST_HASH_LEN or not DEST_HASH_RE.match(destination_hash):
        raise ValueError("Destination hash must be hex and at least 32 characters")
    if not show_name:
        raise ValueError("Show name is required")
    if not sanitize_filename(filename):
        raise ValueError("Invalid filename")
    return destination_hash, show_name, filename


def sanitize_filename(filename: str) -> bool:
    """Return True if filename matches the safe subset in README requirements."""
    if not filename or len(filename) > 255:
        return False
    if "/" in filename or "\\" in filename or ".." in filename:
        return False
    return bool(FILENAME_RE.match(filename))
