from __future__ import annotations

"""NomadCast v0 UI helpers."""
import logging
import threading
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from nomadcastd.config import NomadCastConfig, add_subscription_uri, load_config
from nomadcastd.parsing import (
    Subscription,
    encode_show_path,
    normalize_subscription_input,
    parse_subscription_uri,
)
from nomadcastd.storage import show_directory


def _subscription_feed_url(subscription: Subscription, config: NomadCastConfig) -> str:
    """Build the local HTTP feed URL for a subscription."""
    host = config.public_host or config.listen_host
    if host == "0.0.0.0":
        host = "127.0.0.1"
    show_path = encode_show_path(subscription.destination_hash, subscription.show_name)
    return f"http://{host}:{config.listen_port}/feeds/{show_path}"


def _podcast_handler_url(feed_url: str) -> str:
    """Convert an HTTP feed URL into a podcast:// handler URL."""
    if feed_url.startswith("http://"):
        return f"podcast://{feed_url[len('http://'):] }"
    if feed_url.startswith("https://"):
        return f"podcast://{feed_url[len('https://'):] }"
    return feed_url


@dataclass(frozen=True)
class UiStatus:
    """Lightweight status payload for UI updates."""

    message: str
    is_error: bool = False


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
        self._logger = logger
        self._poll_interval = poll_interval
        self._timeout = timeout
        self._cancel_event = cancel_event or threading.Event()
        self._worker: threading.Thread | None = None

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
                webbrowser.open(self._handler_url, new=2)
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


class SubscriptionService:
    """Service wrapper for subscription writes and podcast handler launches."""

    def __init__(
        self,
        config_loader: Callable[[], NomadCastConfig] = load_config,
        *,
        poll_interval: float = 2.0,
        wait_timeout: float = 300.0,
    ) -> None:
        self._config_loader = config_loader
        self._logger = logging.getLogger(__name__)
        self._poll_interval = poll_interval
        self._wait_timeout = wait_timeout

    def _episodes_dir(self, subscription: Subscription, config: NomadCastConfig) -> Path:
        show_dir = show_directory(config.storage_path, subscription.destination_hash)
        return show_dir / "episodes"

    def _has_cached_episode(self, episodes_dir: Path) -> bool:
        try:
            entries = list(episodes_dir.iterdir())
        except FileNotFoundError:
            return False
        return any(entry.is_file() for entry in entries)

    def _start_waiter(self, subscription: Subscription, config: NomadCastConfig) -> EpisodeWaiter:
        """Create and start an EpisodeWaiter for the subscription.

        The returned waiter can be used to cancel the background thread.
        """
        feed_url = _subscription_feed_url(subscription, config)
        handler_url = _podcast_handler_url(feed_url)
        episodes_dir = self._episodes_dir(subscription, config)
        waiter = EpisodeWaiter(
            episodes_dir,
            feed_url,
            handler_url,
            self._has_cached_episode,
            self._logger,
            poll_interval=self._poll_interval,
            timeout=self._wait_timeout,
        )
        waiter.start()
        return waiter

    def add_subscription(self, locator: str) -> UiStatus:
        """Add a subscription and start a cancellable background poller.

        Subscription processing is synchronous, but episode polling happens in a
        daemon thread that can be cancelled via the returned EpisodeWaiter from
        ``_start_waiter``.
        """
        uri = normalize_subscription_input(locator)
        subscription = parse_subscription_uri(uri)
        config = self._config_loader()
        added = add_subscription_uri(config.config_path, uri)
        feed_url = _subscription_feed_url(subscription, config)
        self._start_waiter(subscription, config)

        if added:
            self._logger.info(
                "Subscription added for %s; waiting for first episode to arrive.",
                feed_url,
            )
            return UiStatus(
                message=(
                    "Added subscription. NomadCast will open your podcast app "
                    "as soon as the first episode finishes downloading."
                ),
                is_error=False,
            )

        self._logger.info("Subscription already exists for %s", feed_url)
        return UiStatus(
            message=(
                "Subscription already exists. NomadCast will open your podcast app "
                "as soon as the first episode finishes downloading."
            ),
            is_error=False,
        )

    def manage_daemon(self) -> UiStatus:
        """Future roadmap stub: manage the daemon lifecycle."""
        raise NotImplementedError("Daemon management UI is not implemented yet.")

    def edit_subscriptions(self) -> UiStatus:
        """Future roadmap stub: edit subscribed feeds."""
        raise NotImplementedError("Subscription editor is not implemented yet.")

    def view_cache_status(self) -> UiStatus:
        """Future roadmap stub: view cache status."""
        raise NotImplementedError("Cache status view is not implemented yet.")

    def system_tray_integration(self) -> UiStatus:
        """Future roadmap stub: system tray integration."""
        raise NotImplementedError("System tray integration is not implemented yet.")

    def health_endpoint(self) -> UiStatus:
        """Future roadmap stub: local health endpoint UI."""
        raise NotImplementedError("Health endpoint UI is not implemented yet.")
