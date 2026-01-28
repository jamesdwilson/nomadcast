from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable


class EpisodeWaiter:
    """Poll for cached episodes in a daemon thread with cooperative cancellation.

    A caller can provide a cancellation event and invoke ``stop()`` to signal
    the background thread to exit early.
    """

    def __init__(
        self,
        episodes_dir: Path,
        feed_url: str,
        handler_url: str,
        has_cached_episode: Callable[[Path], bool],
        open_url: Callable[..., bool],
        logger: logging.Logger,
        *,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
        cancel_event: threading.Event | None = None,
    ) -> None:
        self._episodes_dir = episodes_dir
        self._feed_url = feed_url
        self._handler_url = handler_url
        self._has_cached_episode = has_cached_episode
        self._open_url = open_url
        self._logger = logger
        self._poll_interval = poll_interval
        self._timeout = timeout
        self._cancel_event = cancel_event or threading.Event()
        self._worker: threading.Thread | None = None

    @property
    def cancel_event(self) -> threading.Event:
        """Expose the cancellation token for external coordination."""
        return self._cancel_event

    def start(self) -> None:
        """Start the daemon thread that polls until an episode is cached."""
        if self._worker and self._worker.is_alive():
            return
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def stop(self) -> None:
        """Signal the polling thread to stop and wait briefly for shutdown."""
        self._cancel_event.set()
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=self._poll_interval)

    def _run(self) -> None:
        start_time = time.monotonic()
        self._logger.info("Waiting for first episode in %s", self._episodes_dir)
        while not self._cancel_event.is_set():
            if self._has_cached_episode(self._episodes_dir):
                self._logger.info(
                    "First episode cached; opening podcast handler for %s",
                    self._feed_url,
                )
                self._open_url(self._handler_url, new=2)
                return
            elapsed = time.monotonic() - start_time
            if elapsed >= self._timeout:
                self._logger.warning(
                    "Timed out waiting for first episode in %s after %.1f seconds",
                    self._episodes_dir,
                    elapsed,
                )
                return
            self._cancel_event.wait(self._poll_interval)
