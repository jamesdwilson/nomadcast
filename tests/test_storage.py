import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from nomadcastd.storage import CachedEpisode, ShowState, load_show_state, save_show_state


class StorageStateTests(unittest.TestCase):
    """Unit tests for storage helpers and state persistence."""

    temp_dir: TemporaryDirectory[str]
    state_path: Path

    def setUp(self) -> None:
        """Create a temporary state.json path for each test."""
        self.temp_dir = TemporaryDirectory()
        self.state_path = Path(self.temp_dir.name) / "state.json"

    def tearDown(self) -> None:
        """Clean up the temporary directory."""
        self.temp_dir.cleanup()

    def test_load_save_round_trip_preserves_episode_order(self) -> None:
        """Round-trip state should preserve cached episode ordering."""
        state = ShowState(
            subscription_uri="nomadcast:abc123abc123abc123abc123abc123ab:Show/rss",
            show_name="Show",
            last_refresh=123.0,
            cached_episodes=[
                CachedEpisode(filename="b.mp3", order_index=1, size_bytes=20),
                CachedEpisode(filename="a.mp3", order_index=0, size_bytes=10),
            ],
        )

        save_show_state(self.state_path, state)
        loaded = load_show_state(self.state_path, state.subscription_uri, state.show_name)

        self.assertEqual(loaded.subscription_uri, state.subscription_uri)
        self.assertEqual(loaded.show_name, state.show_name)
        self.assertEqual(loaded.last_refresh, 123.0)
        self.assertEqual(
            [episode.filename for episode in loaded.cached_episodes],
            ["b.mp3", "a.mp3"],
        )

    def test_save_show_state_writes_atomically(self) -> None:
        """State writes should replace the final file without leaving tmp artifacts."""
        state = ShowState(subscription_uri="nomadcast:abc123abc123abc123abc123abc123ab:Show/rss", show_name="Show")
        save_show_state(self.state_path, state)

        tmp_path = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        self.assertTrue(self.state_path.exists())
        self.assertFalse(tmp_path.exists())

        updated = ShowState(
            subscription_uri=state.subscription_uri,
            show_name="Show",
            failure_count=2,
            cached_episodes=[CachedEpisode(filename="ep.mp3", order_index=0, size_bytes=1)],
        )
        save_show_state(self.state_path, updated)

        contents = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(contents["failure_count"], 2)
        self.assertFalse(tmp_path.exists())

    def test_load_show_state_defaults_when_missing(self) -> None:
        """Missing state.json should yield defaults seeded from inputs."""
        state = load_show_state(
            self.state_path,
            subscription_uri="nomadcast:abc123abc123abc123abc123abc123ab:Show/rss",
            show_name="Show",
        )
        self.assertEqual(state.subscription_uri, "nomadcast:abc123abc123abc123abc123abc123ab:Show/rss")
        self.assertEqual(state.show_name, "Show")
        self.assertEqual(state.cached_episodes, [])


if __name__ == "__main__":
    unittest.main()
