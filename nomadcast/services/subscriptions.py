from __future__ import annotations

import logging
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from nomadcast.services.episode_waiter import EpisodeWaiter
from nomadcastd.config import NomadCastConfig, add_no_mirror_uri, add_subscription_uri, load_config
from nomadcastd.parsing import (
    Subscription,
    encode_show_path,
    normalize_subscription_input,
    parse_subscription_uri,
)
from nomadcastd.storage import show_directory


def subscription_feed_url(subscription: Subscription, config: NomadCastConfig) -> str:
    """Build the local HTTP feed URL for a subscription."""
    host = config.public_host or config.listen_host
    if host == "0.0.0.0":
        host = "127.0.0.1"
    show_path = encode_show_path(subscription.destination_hash, subscription.show_name)
    return f"http://{host}:{config.listen_port}/feeds/{show_path}"


def podcast_handler_url(feed_url: str) -> str:
    """Convert an HTTP feed URL into a podcast:// handler URL."""
    if feed_url.startswith("http://"):
        return f"podcast://{feed_url[len('http://'):] }"
    if feed_url.startswith("https://"):
        return f"podcast://{feed_url[len('https://'):] }"
    return feed_url


@dataclass(frozen=True)
class SubscriptionResult:
    """Result payload returned from subscription writes."""

    message: str
    is_error: bool = False
    waiter: EpisodeWaiter | None = None


class SubscriptionService:
    """Service wrapper for subscription writes and podcast handler launches."""

    def __init__(
        self,
        config_loader: Callable[[], NomadCastConfig] = load_config,
        *,
        poll_interval: float = 2.0,
        wait_timeout: float = 300.0,
        open_url: Callable[..., bool] = webbrowser.open,
        has_cached_episode: Callable[[Path], bool] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._config_loader = config_loader
        self._logger = logger or logging.getLogger(__name__)
        self._poll_interval = poll_interval
        self._wait_timeout = wait_timeout
        self._open_url = open_url
        self._has_cached_episode = has_cached_episode or self._default_has_cached_episode

    def _episodes_dir(self, subscription: Subscription, config: NomadCastConfig) -> Path:
        show_dir = show_directory(config.storage_path, subscription.destination_hash)
        return show_dir / "episodes"

    def _default_has_cached_episode(self, episodes_dir: Path) -> bool:
        try:
            entries = list(episodes_dir.iterdir())
        except FileNotFoundError:
            return False
        return any(entry.is_file() for entry in entries)

    def _start_waiter(self, subscription: Subscription, config: NomadCastConfig) -> EpisodeWaiter:
        """Create and start an EpisodeWaiter for the subscription.

        The returned waiter can be used to cancel the background thread.
        """
        feed_url = subscription_feed_url(subscription, config)
        handler_url = podcast_handler_url(feed_url)
        episodes_dir = self._episodes_dir(subscription, config)
        waiter = EpisodeWaiter(
            episodes_dir,
            feed_url,
            handler_url,
            self._has_cached_episode,
            self._open_url,
            self._logger,
            poll_interval=self._poll_interval,
            timeout=self._wait_timeout,
        )
        waiter.start()
        return waiter

    def add_subscription(self, locator: str, *, mirror_enabled: bool = True) -> SubscriptionResult:
        """Add a subscription and start a cancellable background poller.

        Subscription processing is synchronous, but episode polling happens in a
        daemon thread that can be cancelled via the returned EpisodeWaiter from
        ``_start_waiter``.
        """
        uri = normalize_subscription_input(locator)
        subscription = parse_subscription_uri(uri)
        config = self._config_loader()
        added = add_subscription_uri(config.config_path, uri)
        if not mirror_enabled:
            add_no_mirror_uri(config.config_path, uri)
        feed_url = subscription_feed_url(subscription, config)
        waiter = self._start_waiter(subscription, config)

        if added:
            self._logger.info(
                "Subscription added for %s; waiting for first episode to arrive.",
                feed_url,
            )
            return SubscriptionResult(
                message=(
                    "Added subscription. NomadCast will open your podcast app "
                    "as soon as the first episode finishes downloading."
                ),
                is_error=False,
                waiter=waiter,
            )

        self._logger.info("Subscription already exists for %s", feed_url)
        return SubscriptionResult(
            message=(
                "Subscription already exists. NomadCast will open your podcast app "
                "as soon as the first episode finishes downloading."
            ),
            is_error=False,
            waiter=waiter,
        )

    def manage_daemon(self) -> SubscriptionResult:
        """Future roadmap stub: manage the daemon lifecycle."""
        raise NotImplementedError("Daemon management UI is not implemented yet.")

    def edit_subscriptions(self) -> SubscriptionResult:
        """Future roadmap stub: edit subscribed feeds."""
        raise NotImplementedError("Subscription editor is not implemented yet.")

    def view_cache_status(self) -> SubscriptionResult:
        """Future roadmap stub: view cache status."""
        raise NotImplementedError("Cache status view is not implemented yet.")

    def system_tray_integration(self) -> SubscriptionResult:
        """Future roadmap stub: system tray integration."""
        raise NotImplementedError("System tray integration is not implemented yet.")

    def health_endpoint(self) -> SubscriptionResult:
        """Future roadmap stub: local health endpoint UI."""
        raise NotImplementedError("Health endpoint UI is not implemented yet.")
