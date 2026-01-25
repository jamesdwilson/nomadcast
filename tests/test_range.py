import http.client
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from nomadcastd.config import NomadCastConfig
from nomadcastd.daemon import NomadCastDaemon, ShowContext
from nomadcastd.fetchers import MockFetcher
from nomadcastd.parsing import encode_show_path, parse_subscription_uri
from nomadcastd.server import NomadCastHTTPServer, NomadCastRequestHandler
from nomadcastd.storage import ShowState, ensure_show_dirs, show_directory


class RangeTests(unittest.TestCase):
    """Validate HTTP Range semantics for cached media responses."""
    def setUp(self) -> None:
        self.temp_dir: TemporaryDirectory[str] = TemporaryDirectory()
        storage_path = Path(self.temp_dir.name)
        self.config = NomadCastConfig(
            listen_host="127.0.0.1",
            listen_port=0,
            storage_path=storage_path,
            episodes_per_show=5,
            strict_cached_enclosures=True,
            rss_poll_seconds=900,
            retry_backoff_seconds=300,
            max_bytes_per_show=0,
            public_host=None,
            reticulum_config_dir=None,
            config_path=storage_path / "config",
        )
        self.daemon: NomadCastDaemon = NomadCastDaemon(config=self.config, fetcher=MockFetcher())
        subscription = parse_subscription_uri(
            "nomadcast:a7c3e9b14f2d6a80715c9e3b1a4d8f20:BestShow/rss"
        )
        show_dir = show_directory(storage_path, subscription.destination_hash)
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
        self.daemon.show_contexts[subscription.show_id] = context
        self.filename: str = "episode.mp3"
        (context.episodes_dir / self.filename).write_bytes(b"hello world")
        self.show_path: str = encode_show_path(subscription.destination_hash, subscription.show_name)

        self.server: NomadCastHTTPServer = NomadCastHTTPServer(("127.0.0.1", 0), NomadCastRequestHandler)
        self.server.daemon = self.daemon
        self.thread: threading.Thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port: int = self.server.server_address[1]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.temp_dir.cleanup()

    def test_range_request(self) -> None:
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request(
            "GET",
            f"/media/{self.show_path}/{self.filename}",
            headers={"Range": "bytes=0-4"},
        )
        resp = conn.getresponse()
        body = resp.read()
        self.assertEqual(resp.status, 206)
        self.assertEqual(body, b"hello")
        conn.close()

    def test_invalid_range(self) -> None:
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request(
            "GET",
            f"/media/{self.show_path}/{self.filename}",
            headers={"Range": "bytes=100-200"},
        )
        resp = conn.getresponse()
        resp.read()
        self.assertEqual(resp.status, 416)
        conn.close()


if __name__ == "__main__":
    unittest.main()
