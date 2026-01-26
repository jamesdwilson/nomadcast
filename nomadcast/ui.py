from __future__ import annotations

"""NomadCast v0 UI helpers."""
import webbrowser
from dataclasses import dataclass
from typing import Callable

from nomadcastd.config import NomadCastConfig, add_subscription_uri, load_config
from nomadcastd.parsing import (
    Subscription,
    encode_show_path,
    normalize_subscription_input,
    parse_subscription_uri,
)


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

    def add_subscription(self, locator: str) -> UiStatus:
        """Add a subscription and open the podcast handler URL."""
        uri = normalize_subscription_input(locator)
        subscription = parse_subscription_uri(uri)
        config = self._config_loader()
        added = add_subscription_uri(config.config_path, uri)

        feed_url = _subscription_feed_url(subscription, config)
        handler_url = _podcast_handler_url(feed_url)
        webbrowser.open(handler_url, new=2)

        if added:
            return UiStatus(
                message=f"Added subscription. Opening podcast app for {feed_url}.",
                is_error=False,
            )

        return UiStatus(
            message=f"Subscription already exists. Opening podcast app for {feed_url}.",
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

