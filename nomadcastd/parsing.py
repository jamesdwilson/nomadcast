from __future__ import annotations

"""Parsing helpers tied to README's NomadCast locator format.

The README specifies:
- Subscription URI: nomadcast:<DEST_HASH>:<SHOW_NAME>
- Media URI: nomadcast:<DEST_HASH>:<SHOW_NAME>/media/<FILENAME>
- HTTP show_path: URL-encoded DEST_HASH:SHOW_NAME as one segment
"""

import re
from dataclasses import dataclass
from urllib.parse import quote, unquote

NOMADCAST_PREFIX = "nomadcast:"
NOMADCAST_URL_PREFIX = "nomadcast://"
MEDIA_PREFIX = "/media/"
MIN_DEST_HASH_LEN = 32
DEST_HASH_RE = re.compile(r"^[0-9a-fA-F]+$")


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


def _validate_destination_show(destination_hash: str, show_name: str) -> None:
    """Validate destination hash + show name pairs.

    Validation rules:
    - Destination hash must be hexadecimal and at least 32 characters.
    - Show name must be non-empty.

    Raises:
        ValueError: If any validation rule fails.
    """
    if len(destination_hash) < MIN_DEST_HASH_LEN or not DEST_HASH_RE.match(destination_hash):
        raise ValueError("Destination hash must be hex and at least 32 characters")
    if not show_name:
        raise ValueError("Show name is required")


def parse_subscription_uri(uri: str) -> Subscription:
    """Parse the README-defined subscription URI format.

    Validation rules:
    - URL must include destination hash and show name (separated by a colon).
    - Media URLs are rejected.
    - Destination hash and show name are validated by `_validate_destination_show`.

    Raises:
        ValueError: If the subscription URI is invalid.
    """
    body = _strip_nomadcast_prefix(uri)
    if body.endswith("/rss"):
        body = body[: -len("/rss")]
    if ":" not in body:
        raise ValueError("Subscription URI must include destination hash and show name")
    if MEDIA_PREFIX in body:
        raise ValueError("Media URLs are not valid subscription locators")
    destination_hash, show_name = body.split(":", 1)
    _validate_destination_show(destination_hash, show_name)
    return Subscription(uri=uri, destination_hash=destination_hash, show_name=show_name)


def normalize_subscription_input(raw_input: str) -> str:
    """Normalize a user-provided locator into a full subscription URI.

    The README allows users to paste either:
    - nomadcast:<DEST_HASH>:<SHOW_NAME>
    - nomadcast://<DEST_HASH>:<SHOW_NAME>
    - <DEST_HASH>:<SHOW_NAME>
    """
    trimmed = raw_input.strip()
    if not trimmed:
        raise ValueError("Subscription locator cannot be empty")

    if trimmed.startswith(NOMADCAST_URL_PREFIX):
        trimmed = f"{NOMADCAST_PREFIX}{trimmed[len(NOMADCAST_URL_PREFIX):]}"

    if trimmed.startswith(NOMADCAST_PREFIX):
        if trimmed.endswith("/rss"):
            return trimmed[: -len("/rss")]
        if MEDIA_PREFIX in trimmed:
            raise ValueError("Media URLs are not valid subscription locators")
        return trimmed.rstrip("/")

    if ":" not in trimmed:
        raise ValueError("Locator must include destination hash and show name")

    return f"{NOMADCAST_PREFIX}{trimmed}"


def encode_show_path(destination_hash: str, show_name: str) -> str:
    """Encode DEST_HASH:SHOW_NAME into a single URL path segment."""
    return quote(f"{destination_hash}:{show_name}", safe="")


def decode_show_path(show_path: str) -> tuple[str, str]:
    """Decode a show_path back into destination hash and show name.

    Validation rules:
    - show_path must include destination hash and show name (separated by a colon).
    - Destination hash and show name are validated by `_validate_destination_show`.

    Raises:
        ValueError: If the show path is invalid.
    """
    decoded = unquote(show_path)
    if ":" not in decoded:
        raise ValueError("Show path must include destination hash and show name")
    destination_hash, show_name = decoded.split(":", 1)
    _validate_destination_show(destination_hash, show_name)
    return destination_hash, show_name


def parse_nomadcast_media_url(url: str) -> tuple[str, str, str]:
    """Parse a nomadcast media URL and validate its filename.

    Validation rules:
    - URL must include destination hash, show name, and a /media/ filename.
    - Destination hash and show name are validated by `_validate_destination_show`.
    - Filename is validated by `sanitize_filename`.

    Raises:
        ValueError: If the media URL or filename is invalid.
    """
    if MEDIA_PREFIX not in url:
        raise ValueError("Not a nomadcast media URL")
    prefix, filename = url.split(MEDIA_PREFIX, 1)
    filename = unquote(filename)
    body = _strip_nomadcast_prefix(prefix)
    if ":" not in body:
        raise ValueError("Media URL must include destination hash and show name")
    destination_hash, show_name = body.split(":", 1)
    _validate_destination_show(destination_hash, show_name)
    if not sanitize_filename(filename):
        raise ValueError("Invalid filename")
    return destination_hash, show_name, filename


def sanitize_filename(filename: str) -> bool:
    """Return True if filename matches the safe subset in README requirements."""
    if not filename or len(filename) > 255:
        return False
    if "/" in filename or "\\" in filename or ".." in filename:
        return False
    if not filename.isprintable():
        return False
    return True
