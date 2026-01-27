from __future__ import annotations

import configparser
import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PLACEHOLDER_IDENTITY = "0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f"
PLACEHOLDER_SHOW_NAME = "Example NomadCast Podcast"
PLACEHOLDER_SHOW_SLUG = "ExampleNomadCastPodcast"
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


@dataclass(frozen=True)
class NomadNetIdentityDetection:
    """Resolved NomadNet identity hash plus its origin path."""

    identity: str
    source_path: Path


def detect_nomadnet_identity() -> NomadNetIdentityDetection | None:
    """Attempt to discover a NomadNet identity hash from known locations."""
    config_dir = nomadnet_config_dir()
    identity_path = config_dir / "storage" / "identity"
    identity = _extract_identity_from_rns(identity_path)
    if identity:
        return NomadNetIdentityDetection(identity=identity, source_path=identity_path)
    candidates = [
        config_dir / "config",
        config_dir / "identity",
        config_dir / "node_identity",
    ]
    for candidate in candidates:
        identity = _try_identity_from_path(candidate)
        if identity:
            return NomadNetIdentityDetection(identity=identity, source_path=candidate)
    return None


def detect_nomadnet_node_name() -> str | None:
    """Detect the NomadNet node name from the NomadNet config file."""
    config_dir = nomadnet_config_dir()
    config_path = config_dir / "config"
    if not config_path.is_file():
        return None
    parser = configparser.ConfigParser(strict=False, inline_comment_prefixes=("#", ";"))
    try:
        with config_path.open(encoding="utf-8") as handle:
            parser.read_file(handle)
    except (OSError, configparser.Error):
        return None
    node_name = parser.get("node", "node_name", fallback="").strip()
    return node_name or None


def nomadnet_config_dir() -> Path:
    """Resolve NomadNet's config directory using NomadNet's precedence rules."""
    etc_config = Path("/etc/nomadnetwork/config")
    if etc_config.is_file():
        return etc_config.parent
    xdg_config = Path.home() / ".config" / "nomadnetwork" / "config"
    if xdg_config.is_file():
        return xdg_config.parent
    return Path.home() / ".nomadnetwork"


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
    show_name: str,
    show_name_slug: str,
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
        _clear_existing_storage(pages_path, files_root, show_name_slug)
    pages_path.mkdir(parents=True, exist_ok=True)
    files_root.mkdir(parents=True, exist_ok=True)
    # Copy the bundled page and file trees into the user's storage.
    shutil.copytree(source_pages, pages_path, dirs_exist_ok=True)
    shutil.copytree(source_files, files_root, dirs_exist_ok=True)
    # Replace the placeholder identity with the user's real node hash.
    _replace_identity_in_tree(pages_path, identity)
    _replace_identity_in_tree(files_root, identity)
    _replace_show_name_in_tree(pages_path, show_name, show_name_slug)
    _replace_show_name_in_tree(files_root, show_name, show_name_slug)
    sample_folder = files_root / PLACEHOLDER_SHOW_SLUG
    target_folder = files_root / show_name_slug
    if sample_folder.exists() and sample_folder != target_folder:
        if target_folder.exists():
            if replace_existing:
                shutil.rmtree(target_folder)
            else:
                raise FileExistsError(
                    f"Sample folder already exists: {target_folder}. "
                    "Choose a new podcast name or replace existing pages."
                )
        shutil.move(str(sample_folder), str(target_folder))
    media_path = target_folder / "media"
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


def _clear_existing_storage(pages_path: Path, files_root: Path, show_name_slug: str) -> None:
    """Remove existing sample content before re-installing."""
    if pages_path.exists():
        shutil.rmtree(pages_path)
    for folder in {PLACEHOLDER_SHOW_SLUG, show_name_slug}:
        sample_files = files_root / folder
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


def _replace_show_name_in_tree(destination_root: Path, show_name: str, show_name_slug: str) -> None:
    """Replace placeholder show names inside all text files in a tree."""
    replacements = {
        PLACEHOLDER_SHOW_NAME: show_name,
        PLACEHOLDER_SHOW_SLUG: show_name_slug,
    }
    for file_path in _iter_text_files(destination_root):
        try:
            content = file_path.read_text(encoding="utf-8")
        except OSError:
            continue
        updated = content
        for placeholder, replacement in replacements.items():
            updated = updated.replace(placeholder, replacement)
        if updated != content:
            file_path.write_text(updated, encoding="utf-8")


def sanitize_show_name_for_path(show_name: str) -> str:
    """Convert a show name into a filesystem-safe folder name."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", show_name.strip())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-._")
    return cleaned[:64] if cleaned else "NomadCastPodcast"


def _iter_text_files(root: Path) -> Iterable[Path]:
    """Yield all non-hidden files beneath a root path."""
    for path in root.rglob("*"):
        if path.is_file() and not path.name.startswith("."):
            yield path
