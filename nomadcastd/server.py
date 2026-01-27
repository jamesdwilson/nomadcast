from __future__ import annotations

"""HTTP server endpoints defined in README.

Endpoints:
- GET /feeds/<show_path>
- GET /media/<show_path>/<filename> (Range support required)
- POST /reload
"""

import logging
import os
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from nomadcastd.daemon import NomadCastDaemon
from nomadcastd.parsing import decode_show_path, sanitize_filename

RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


class NomadCastHTTPServer(ThreadingHTTPServer):
    """Threading HTTP server that exposes NomadCast daemon endpoints."""

    daemon: NomadCastDaemon


class NomadCastRequestHandler(BaseHTTPRequestHandler):
    """Handle HTTP requests for cached feeds and media."""

    server: NomadCastHTTPServer

    def do_GET(self) -> None:
        """Handle GET requests for feed and media endpoints."""
        # README: serve cached RSS and media over HTTP to normal podcast apps.
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        if path.startswith("/feeds/"):
            self._handle_feed(path)
        elif path.startswith("/media/"):
            self._handle_media(path)
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self) -> None:
        """Handle POST requests for administrative endpoints."""
        # README: POST /reload triggers local config + subscription reload.
        parsed_path = urlparse(self.path)
        if parsed_path.path == "/reload":
            self.server.daemon.reload_config()
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def _handle_feed(self, path: str) -> None:
        """Serve the cached RSS feed or queue a refresh.

        Side Effects:
            Enqueues a refresh job for the show and serves client_rss.xml if
            available, otherwise responds with 503.

        Error Conditions:
            Returns 404 for invalid or missing show paths.
        """
        # README: return cached RSS (200) or 503 if missing, and enqueue refresh.
        parts = path.split("/", 2)
        if len(parts) < 3 or not parts[2]:
            self.send_error(HTTPStatus.NOT_FOUND, "Missing show path")
            return
        show_path = parts[2]
        show_id = self.server.daemon.show_id_from_path(show_path)
        if not show_id:
            self.send_error(HTTPStatus.NOT_FOUND, "Invalid show path")
            return
        self.server.daemon.enqueue_refresh(show_id)
        cached = self.server.daemon.get_cached_rss(show_id)
        logger = logging.getLogger("nomadcastd.feed")
        if cached is None:
            retry_after = self.server.daemon.config.rss_poll_seconds
            logger.info(
                "RSS cache miss for %s; refresh queued; retry_after=%s",
                show_id,
                retry_after,
            )
            self.send_response(HTTPStatus.SERVICE_UNAVAILABLE)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Retry-After", str(retry_after))
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.end_headers()
            self.wfile.write(b"RSS not yet cached. Refresh queued.\n")
            return
        logger.info("RSS cache hit for %s; bytes=%s", show_id, len(cached))
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/rss+xml; charset=utf-8")
        self.send_header("Content-Length", str(len(cached)))
        self.end_headers()
        self.wfile.write(cached)

    def _handle_media(self, path: str) -> None:
        """Serve cached media with Range support.

        Side Effects:
            Enqueues a media fetch if the file is missing from cache.

        Error Conditions:
            Returns 400 for invalid filenames, 404 for missing show/filename,
            404 for cache misses, and 416 for unsatisfiable ranges.
        """
        # README: serve cached media with Range support; queue fetch if missing.
        parts = path.split("/", 3)
        if len(parts) < 4:
            self.send_error(HTTPStatus.NOT_FOUND, "Missing show path or filename")
            return
        show_path, raw_filename = parts[2], parts[3]
        filename = unquote(raw_filename)
        if not sanitize_filename(filename):
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid filename")
            return
        try:
            decode_show_path(show_path)
        except ValueError:
            self.send_error(HTTPStatus.NOT_FOUND, "Invalid show path")
            return
        show_id = self.server.daemon.show_id_from_path(show_path)
        if not show_id:
            self.send_error(HTTPStatus.NOT_FOUND, "Invalid show path")
            return
        media_path = self.server.daemon.get_media_path(show_id, filename)
        if media_path is None:
            logging.getLogger("nomadcastd.media").info("Cache miss for %s/%s", show_id, filename)
            self.server.daemon.enqueue_media_fetch(show_id, filename)
            self.send_error(HTTPStatus.NOT_FOUND, "Media not cached")
            return
        logging.getLogger("nomadcastd.media").info("Cache hit for %s/%s", show_id, filename)
        file_size = os.path.getsize(media_path)
        range_header = self.headers.get("Range")
        if range_header:
            # README: accept byte ranges and respond with 206/416 as required.
            range_result = _parse_range(range_header, file_size)
            if range_result is None:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{file_size}")
                self.end_headers()
                return
            start, end = range_result
            self.send_response(HTTPStatus.PARTIAL_CONTENT)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.send_header("Content-Length", str(end - start + 1))
            self.end_headers()
            with open(media_path, "rb") as handle:
                handle.seek(start)
                self.wfile.write(handle.read(end - start + 1))
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(file_size))
        self.end_headers()
        with open(media_path, "rb") as handle:
            self.wfile.write(handle.read())

    def log_message(self, format: str, *args: object) -> None:
        """Route HTTP logs through the nomadcastd.http logger."""
        logging.getLogger("nomadcastd.http").info("%s - %s", self.address_string(), format % args)


def _parse_range(range_header: str, file_size: int) -> tuple[int, int] | None:
    """Parse a single HTTP Range header for bytes.

    Inputs:
        range_header: The raw Range header value.
        file_size: Total size of the resource in bytes.

    Outputs:
        A (start, end) byte range tuple, inclusive, or None if invalid.
    """
    match = RANGE_RE.match(range_header.strip())
    if not match:
        return None
    start_str, end_str = match.groups()
    if start_str == "" and end_str == "":
        return None
    if start_str == "":
        try:
            suffix = int(end_str)
        except ValueError:
            return None
        if suffix <= 0:
            return None
        start = max(file_size - suffix, 0)
        return start, file_size - 1
    try:
        start = int(start_str)
    except ValueError:
        return None
    if end_str:
        try:
            end = int(end_str)
        except ValueError:
            return None
    else:
        end = file_size - 1
    if start >= file_size or start < 0:
        return None
    end = min(end, file_size - 1)
    if end < start:
        return None
    return start, end
