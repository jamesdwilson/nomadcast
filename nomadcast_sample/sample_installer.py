from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PLACEHOLDER_IDENTITY = "0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f"
NOMADNET_GUIDE_URL = "https://reticulum.network/manual/"


@dataclass(frozen=True)
class SampleInstallResult:
    """Result payload for a completed sample installation."""

    storage_root: Path
    pages_path: Path
    media_path: Path


def sample_source_root() -> Path:
    """Return the root of the bundled sample storage tree."""
    return Path(__file__).resolve().parent.parent / "examples" / "storage"


def nomadnet_storage_root() -> Path:
    """Return the default NomadNet storage path on disk."""
    return Path.home() / ".nomadnetwork" / "storage"


def detect_nomadnet_identity() -> str | None:
    """Attempt to discover a NomadNet identity hash from common files."""
    # NomadNet and Reticulum configurations store identity data in a handful of
    # predictable locations. We scan those paths in priority order and return
    # the first identity hash we can parse.
    candidates = [
        Path.home() / ".nomadnetwork" / "config",
        Path.home() / ".nomadnetwork" / "identity",
        Path.home() / ".nomadnetwork" / "storage" / "identity",
        Path.home() / ".nomadnetwork" / "node_identity",
    ]
    for candidate in candidates:
        identity = _try_identity_from_path(candidate)
        if identity:
            return identity
    return None


def _try_identity_from_path(path: Path) -> str | None:
    """Try to parse a NomadNet identity hash from a path."""
    if not path.exists():
        return None
    # Text-based config formats come first because they are cheap to parse.
    if path.is_file() and path.suffix in {".txt", ".conf", ".ini", ""}:
        identity = _extract_identity_from_text(path)
        if identity:
            return identity
    # Fall back to parsing the Reticulum identity file format if present.
    identity = _extract_identity_from_rns(path)
    return identity


def _extract_identity_from_text(path: Path) -> str | None:
    """Extract a hex identity hash from a text file."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"\b[0-9a-fA-F]{32}\b", content)
    return match.group(0) if match else None


def _extract_identity_from_rns(path: Path) -> str | None:
    """Extract the Reticulum identity hash from an RNS identity file."""
    try:
        import RNS  # type: ignore[import-untyped]
    except Exception:
        return None
    try:
        identity = RNS.Identity.from_file(str(path))
    except Exception:
        return None
    if not identity:
        return None
    try:
        return identity.hash.hex()
    except Exception:
        return None


def install_sample(
    *,
    storage_root: Path,
    pages_path: Path,
    identity: str,
    replace_existing: bool,
) -> SampleInstallResult:
    """Install the bundled Relay Room content into NomadNet storage."""
    # Ensure the storage root exists before we attempt any copy operations.
    storage_root.mkdir(parents=True, exist_ok=True)
    files_root = storage_root / "files"
    source_root = sample_source_root()
    if not source_root.exists():
        raise FileNotFoundError(f"Sample storage tree missing: {source_root}")
    source_pages = source_root / "pages"
    source_files = source_root / "files"
    if replace_existing:
        # Clearing the destination makes the sample feel like a fresh install.
        _clear_existing_storage(pages_path, files_root)
    pages_path.mkdir(parents=True, exist_ok=True)
    files_root.mkdir(parents=True, exist_ok=True)
    # Copy the bundled page and file trees into the user's storage.
    shutil.copytree(source_pages, pages_path, dirs_exist_ok=True)
    shutil.copytree(source_files, files_root, dirs_exist_ok=True)
    # Replace the placeholder identity with the user's real node hash.
    _replace_identity_in_tree(pages_path, identity)
    _replace_identity_in_tree(files_root, identity)
    media_path = files_root / "ExampleNomadCastPodcast" / "media"
    return SampleInstallResult(
        storage_root=storage_root,
        pages_path=pages_path,
        media_path=media_path,
    )


def open_in_file_browser(path: Path) -> None:
    """Open a filesystem path in the OS-native file browser."""
    if not path.exists():
        raise FileNotFoundError(str(path))
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["open", str(path)], check=False)
    elif system == "Windows":
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def _clear_existing_storage(pages_path: Path, files_root: Path) -> None:
    """Remove existing sample content before re-installing."""
    if pages_path.exists():
        shutil.rmtree(pages_path)
    sample_files = files_root / "ExampleNomadCastPodcast"
    if sample_files.exists():
        shutil.rmtree(sample_files)


def _replace_identity_in_tree(destination_root: Path, identity: str) -> None:
    """Replace placeholder identities inside all text files in a tree."""
    for file_path in _iter_text_files(destination_root):
        try:
            content = file_path.read_text(encoding="utf-8")
        except OSError:
            continue
        updated = content.replace(PLACEHOLDER_IDENTITY, identity)
        if updated != content:
            file_path.write_text(updated, encoding="utf-8")


def _iter_text_files(root: Path) -> Iterable[Path]:
    """Yield all non-hidden files beneath a root path."""
    for path in root.rglob("*"):
        if path.is_file() and not path.name.startswith("."):
            yield path
