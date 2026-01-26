import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from nomadcastd.config import NomadCastConfig
from nomadcastd.daemon import NomadCastDaemon, ShowContext
from nomadcastd.fetchers import MockFetcher
from nomadcastd.parsing import parse_subscription_uri
from nomadcastd.storage import CachedEpisode, ShowState, ensure_show_dirs, load_show_state, show_directory


class DaemonBehaviorTests(unittest.TestCase):
    """Unit tests for core daemon runtime behaviors."""

    temp_dir: TemporaryDirectory[str]
    storage_path: Path

    def setUp(self) -> None:
        """Create a temporary storage root for each test."""
        self.temp_dir = TemporaryDirectory()
        self.storage_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        """Dispose of temporary storage after each test."""
        self.temp_dir.cleanup()

    def _build_daemon(self, max_bytes_per_show: int = 0, rss_poll_seconds: int = 900) -> NomadCastDaemon:
        """Create a daemon configured for test-friendly storage and limits."""
        config = NomadCastConfig(
            listen_host="127.0.0.1",
            listen_port=0,
            storage_path=self.storage_path,
            episodes_per_show=5,
            strict_cached_enclosures=True,
            rss_poll_seconds=rss_poll_seconds,
            retry_backoff_seconds=300,
            max_bytes_per_show=max_bytes_per_show,
            public_host=None,
            reticulum_config_dir=None,
            config_path=self.storage_path / "config",
        )
        return NomadCastDaemon(config=config, fetcher=MockFetcher())

    def _add_show(self, daemon: NomadCastDaemon) -> tuple[str, ShowContext]:
        """Attach a single show context to the daemon under test."""
        subscription = parse_subscription_uri(
            "nomadcast:a7c3e9b14f2d6a80715c9e3b1a4d8f20:BestShow"
        )
        show_dir = show_directory(self.storage_path, subscription.destination_hash)
        dirs = ensure_show_dirs(show_dir)
        state = ShowState(subscription_uri=subscription.uri, show_name=subscription.show_name)
        context = ShowContext(
            subscription=subscription,
            show_dir=show_dir,
            episodes_dir=dirs["episodes_dir"],
            tmp_dir=dirs["tmp_dir"],
            state_path=show_dir / "state.json",
            state=state,
        )
        daemon.show_contexts[subscription.show_id] = context
        return subscription.show_id, context

    def test_refresh_debounce_respects_polling_and_pending(self) -> None:
        """Ensure refresh enqueueing respects debounce/polling/backoff rules."""
        daemon = self._build_daemon(rss_poll_seconds=900)
        show_id, context = self._add_show(daemon)

        # A recent refresh should skip enqueueing.
        context.state.last_refresh = time.time()
        daemon.enqueue_refresh(show_id)
        self.assertEqual(daemon.queue.qsize(), 0)

        # A future backoff window should also skip enqueueing.
        context.state.last_refresh = None
        context.next_refresh_time = time.time() + 60
        daemon.enqueue_refresh(show_id)
        self.assertEqual(daemon.queue.qsize(), 0)

        # With no backoff and no pending refresh, enqueue once.
        context.next_refresh_time = 0
        daemon.enqueue_refresh(show_id)
        daemon.enqueue_refresh(show_id)
        self.assertEqual(daemon.queue.qsize(), 1)

    def test_register_failure_sets_backoff_and_persists_state(self) -> None:
        """Verify failure registration updates backoff and state.json."""
        daemon = self._build_daemon()
        _, context = self._add_show(daemon)

        start = time.time()
        daemon._register_failure(context, "boom")

        self.assertGreaterEqual(context.next_refresh_time, start)
        self.assertEqual(context.state.failure_count, 1)
        self.assertEqual(context.state.last_error, "boom")
        self.assertTrue(context.state_path.exists())
        saved = load_show_state(context.state_path, context.subscription.uri, context.subscription.show_name)
        self.assertEqual(saved.failure_count, 1)
        self.assertEqual(saved.last_error, "boom")

    def test_cache_eviction_removes_oldest_media_and_updates_state(self) -> None:
        """Ensure max_bytes_per_show evicts oldest cached media."""
        daemon = self._build_daemon(max_bytes_per_show=10)
        _, context = self._add_show(daemon)

        newest = context.episodes_dir / "newest.mp3"
        oldest = context.episodes_dir / "oldest.mp3"
        newest.write_bytes(b"1234")
        oldest.write_bytes(b"12345")

        # Order index 0 is newest; larger order_index is older.
        context.state.cached_episodes = [
            CachedEpisode(filename="newest.mp3", order_index=0, size_bytes=4),
            CachedEpisode(filename="oldest.mp3", order_index=1, size_bytes=5),
        ]

        allowed = daemon._ensure_space_for(context, new_size=6)

        self.assertTrue(allowed)
        self.assertTrue(newest.exists())
        self.assertFalse(oldest.exists())
        self.assertEqual([item.filename for item in context.state.cached_episodes], ["newest.mp3"])
        persisted = json.loads(context.state_path.read_text(encoding="utf-8"))
        self.assertEqual([item["filename"] for item in persisted["cached_episodes"]], ["newest.mp3"])


if __name__ == "__main__":
    unittest.main()
