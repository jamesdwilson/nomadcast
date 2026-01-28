from __future__ import annotations

"""Controller for the NomadCast Tkinter UI."""

import logging
from typing import Callable

from nomadcast.domain.types import LocatorInput, validate_locator
from nomadcast.ui import SubscriptionService, UiStatus
from nomadcast.ui.main_view import MainView


class MainController:
    """Coordinate actions between the main view and subscription service."""

    def __init__(
        self,
        view: MainView,
        service: SubscriptionService,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._view = view
        self._service = service
        self._logger = logger or logging.getLogger(__name__)

    def on_add(self) -> None:
        """Handle the add subscription action."""
        locator = self._view.get_locator()
        locator_input = LocatorInput(locator=locator)
        errors = validate_locator(locator_input)
        if errors:
            self._view.set_status(UiStatus(message=" ".join(errors), is_error=True))
            return

        self._view.set_busy(True)
        try:
            status = self._service.add_subscription(locator_input.locator)
        except ValueError as exc:
            self._logger.warning("Invalid locator entered: %s", exc)
            status = UiStatus(message=f"Invalid locator: {exc}", is_error=True)
        except OSError as exc:
            self._logger.exception("Failed to update config: %s", exc)
            status = UiStatus(message=f"Failed to update config: {exc}", is_error=True)
        finally:
            self._view.set_busy(False)

        self._view.set_status(status)

    def on_manage_daemon(self) -> None:
        """Handle manage daemon action."""
        self._handle_not_implemented(self._service.manage_daemon)

    def on_edit_subscriptions(self) -> None:
        """Handle edit subscriptions action."""
        self._handle_not_implemented(self._service.edit_subscriptions)

    def on_view_cache(self) -> None:
        """Handle view cache action."""
        self._handle_not_implemented(self._service.view_cache_status)

    def on_health_endpoint(self) -> None:
        """Handle health endpoint action."""
        self._handle_not_implemented(self._service.health_endpoint)

    def _handle_not_implemented(self, action: Callable[[], UiStatus]) -> None:
        try:
            status = action()
        except NotImplementedError as exc:
            status = UiStatus(message=str(exc), is_error=True)
        self._view.set_status(status)
