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


class SubscriptionService:
    """Service wrapper for subscription writes and podcast handler launches."""

    def __init__(self, config_loader: Callable[[], NomadCastConfig] = load_config) -> None:
        self._config_loader = config_loader
        self._logger = logging.getLogger(__name__)

    def _episodes_dir(self, subscription: Subscription, config: NomadCastConfig) -> Path:
        show_dir = show_directory(config.storage_path, subscription.destination_hash)
        return show_dir / "episodes"

    def _has_cached_episode(self, episodes_dir: Path) -> bool:
        try:
            entries = list(episodes_dir.iterdir())
        except FileNotFoundError:
            return False
        return any(entry.is_file() for entry in entries)

    def _wait_and_open_player(self, subscription: Subscription, config: NomadCastConfig) -> None:
        feed_url = _subscription_feed_url(subscription, config)
        handler_url = _podcast_handler_url(feed_url)
        episodes_dir = self._episodes_dir(subscription, config)
        self._logger.info("Waiting for first episode in %s", episodes_dir)
        while True:
            if self._has_cached_episode(episodes_dir):
                self._logger.info("First episode cached; opening podcast handler for %s", feed_url)
                webbrowser.open(handler_url, new=2)
                return
            time.sleep(2)

    def _start_waiter(self, subscription: Subscription, config: NomadCastConfig) -> None:
        worker = threading.Thread(
            target=self._wait_and_open_player,
            args=(subscription, config),
            daemon=True,
        )
        worker.start()

    def add_subscription(self, locator: str) -> UiStatus:
        """Add a subscription and open the podcast handler URL."""
        uri = normalize_subscription_input(locator)
        subscription = parse_subscription_uri(uri)
        config = self._config_loader()
        added = add_subscription_uri(config.config_path, uri)
        feed_url = _subscription_feed_url(subscription, config)

        episodes_dir = self._episodes_dir(subscription, config)
        if self._has_cached_episode(episodes_dir):
            handler_url = _podcast_handler_url(feed_url)
            self._logger.info("Cached episode found; opening podcast handler for %s", feed_url)
            webbrowser.open(handler_url, new=2)
        else:
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
