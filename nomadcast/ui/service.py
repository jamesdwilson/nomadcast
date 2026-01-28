from __future__ import annotations

"""NomadCast v0 UI helpers."""
from dataclasses import dataclass

from nomadcast.services.subscriptions import (
    SubscriptionResult,
    SubscriptionService as CoreSubscriptionService,
)


@dataclass(frozen=True)
class UiStatus:
    """Lightweight status payload for UI updates."""

    message: str
    is_error: bool = False


class SubscriptionService:
    """UI adapter that maps subscription results into UiStatus payloads."""

    def __init__(self, subscriptions: CoreSubscriptionService | None = None) -> None:
        self._subscriptions = subscriptions or CoreSubscriptionService()

    def add_subscription(self, locator: str) -> UiStatus:
        """Add a subscription and map the result to a UI payload."""
        result = self._subscriptions.add_subscription(locator)
        return self._to_ui_status(result)

    def _to_ui_status(self, result: SubscriptionResult) -> UiStatus:
        return UiStatus(message=result.message, is_error=result.is_error)

    def manage_daemon(self) -> UiStatus:
        """Future roadmap stub: manage the daemon lifecycle."""
        result = self._subscriptions.manage_daemon()
        return self._to_ui_status(result)

    def edit_subscriptions(self) -> UiStatus:
        """Future roadmap stub: edit subscribed feeds."""
        result = self._subscriptions.edit_subscriptions()
        return self._to_ui_status(result)

    def view_cache_status(self) -> UiStatus:
        """Future roadmap stub: view cache status."""
        result = self._subscriptions.view_cache_status()
        return self._to_ui_status(result)

    def system_tray_integration(self) -> UiStatus:
        """Future roadmap stub: system tray integration."""
        result = self._subscriptions.system_tray_integration()
        return self._to_ui_status(result)

    def health_endpoint(self) -> UiStatus:
        """Future roadmap stub: local health endpoint UI."""
        result = self._subscriptions.health_endpoint()
        return self._to_ui_status(result)
