import http.client
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from nomadcastd.parsing import encode_show_path
from nomadcastd.server import NomadCastHTTPServer, NomadCastRequestHandler


class StubDaemon:
    """Minimal daemon stub to exercise server endpoints in isolation."""

    show_id: str
    show_path: str
    cached_rss: bytes | None
    media_path: Path | None
    refresh_calls: list[str]
    media_calls: list[tuple[str, str]]

    def __init__(self, show_id: str, show_path: str) -> None:
        self.show_id = show_id
        self.show_path = show_path
        self.cached_rss = None
        self.media_path = None
        self.refresh_calls = []
        self.media_calls = []

    def show_id_from_path(self, show_path: str) -> str | None:
        if show_path == self.show_path:
            return self.show_id
        return None

    def enqueue_refresh(self, show_id: str) -> None:
        self.refresh_calls.append(show_id)

    def get_cached_rss(self, show_id: str) -> bytes | None:
        return self.cached_rss

    def get_media_path(self, show_id: str, filename: str) -> Path | None:
        return self.media_path

    def enqueue_media_fetch(self, show_id: str, filename: str) -> None:
        self.media_calls.append((show_id, filename))


class ServerEndpointTests(unittest.TestCase):
    """HTTP endpoint tests for cached feeds and media."""

    temp_dir: TemporaryDirectory[str]
    show_path: str
    show_id: str
    daemon: StubDaemon
    server: NomadCastHTTPServer
    thread: threading.Thread
    port: int

    def setUp(self) -> None:
        """Start a temporary HTTP server bound to an ephemeral port."""
        self.temp_dir = TemporaryDirectory()
        destination_hash = "a7c3e9b14f2d6a80715c9e3b1a4d8f20"
        show_name = "BestShow"
        self.show_path = encode_show_path(destination_hash, show_name)
        self.show_id = f"{destination_hash}:{show_name}"
        self.daemon = StubDaemon(self.show_id, self.show_path)

        self.server = NomadCastHTTPServer(("127.0.0.1", 0), NomadCastRequestHandler)
        self.server.daemon = self.daemon
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self) -> None:
        """Stop the HTTP server and clean up temporary files."""
        self.server.shutdown()
        self.server.server_close()
        self.temp_dir.cleanup()

    def test_feeds_returns_503_when_cache_missing(self) -> None:
        """A missing cached feed should return 503 and enqueue refresh."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", f"/feeds/{self.show_path}")
        resp = conn.getresponse()
        body = resp.read()
        conn.close()

        self.assertEqual(resp.status, 503)
        self.assertIn(b"Refresh queued", body)
        self.assertEqual(self.daemon.refresh_calls, [self.show_id])

    def test_media_returns_404_when_cache_missing(self) -> None:
        """A missing cached media file should return 404 and enqueue fetch."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", f"/media/{self.show_path}/episode.mp3")
        resp = conn.getresponse()
        resp.read()
        conn.close()

        self.assertEqual(resp.status, 404)
        self.assertEqual(self.daemon.media_calls, [(self.show_id, "episode.mp3")])

    def test_media_range_response_reads_from_cache(self) -> None:
        """Range requests should return partial content from cached media."""
        media_path = Path(self.temp_dir.name) / "episode.mp3"
        media_path.write_bytes(b"hello world")
        self.daemon.media_path = media_path

        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request(
            "GET",
            f"/media/{self.show_path}/episode.mp3",
            headers={"Range": "bytes=0-4"},
        )
        resp = conn.getresponse()
        body = resp.read()
        conn.close()

        self.assertEqual(resp.status, 206)
        self.assertEqual(body, b"hello")


if __name__ == "__main__":
    unittest.main()
