from __future__ import annotations

"""Local storage helpers following README on-disk layout."""

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass
class CachedEpisode:
    filename: str
    order_index: int
    size_bytes: int


@dataclass
class ShowState:
    subscription_uri: str
    show_name: str
    last_refresh: float | None = None
    last_error: str | None = None
    failure_count: int = 0
    cached_episodes: list[CachedEpisode] = field(default_factory=list)

    def to_json(self) -> dict:
        data = asdict(self)
        data["cached_episodes"] = [asdict(item) for item in self.cached_episodes]
        return data

    @classmethod
    def from_json(cls, data: dict) -> "ShowState":
        episodes = [CachedEpisode(**item) for item in data.get("cached_episodes", [])]
        return cls(
            subscription_uri=data.get("subscription_uri", ""),
            show_name=data.get("show_name", ""),
            last_refresh=data.get("last_refresh"),
            last_error=data.get("last_error"),
            failure_count=data.get("failure_count", 0),
            cached_episodes=episodes,
        )


def show_directory(base_path: Path, destination_hash: str) -> Path:
    """Return the README-specified show directory path."""
    return base_path / "shows" / destination_hash


def ensure_show_dirs(show_dir: Path) -> dict[str, Path]:
    """Ensure the show storage layout exists (episodes/, tmp/, etc.)."""
    episodes_dir = show_dir / "episodes"
    tmp_dir = show_dir / "tmp"
    show_dir.mkdir(parents=True, exist_ok=True)
    episodes_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return {
        "show_dir": show_dir,
        "episodes_dir": episodes_dir,
        "tmp_dir": tmp_dir,
    }


def write_atomic(target_path: Path, data: bytes) -> None:
    """Write bytes atomically via a temp file + rename (README requirement)."""
    tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    with open(tmp_path, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    tmp_path.replace(target_path)


def load_show_state(state_path: Path, subscription_uri: str, show_name: str) -> ShowState:
    if state_path.exists():
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
            state = ShowState.from_json(data)
            if not state.subscription_uri:
                state.subscription_uri = subscription_uri
            if not state.show_name:
                state.show_name = show_name
            return state
        except json.JSONDecodeError:
            pass
    return ShowState(subscription_uri=subscription_uri, show_name=show_name)


def save_show_state(state_path: Path, state: ShowState) -> None:
    write_atomic(state_path, json.dumps(state.to_json(), indent=2).encode("utf-8"))


def cached_episode_filenames(episodes: Iterable[CachedEpisode]) -> set[str]:
    return {episode.filename for episode in episodes}
