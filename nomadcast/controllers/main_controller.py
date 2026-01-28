from __future__ import annotations

"""Controller for the NomadCast Tkinter UI."""

import logging

from nomadcast.domain.types import LocatorInput, validate_locator
from nomadcast.services.subscriptions import SubscriptionService
from nomadcast.ui import UiStatus
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
            result = self._service.add_subscription(locator_input.locator)
        except ValueError as exc:
            self._logger.warning("Invalid locator entered: %s", exc)
            status = UiStatus(message=f"Invalid locator: {exc}", is_error=True)
        except OSError as exc:
            self._logger.exception("Failed to update config: %s", exc)
            status = UiStatus(message=f"Failed to update config: {exc}", is_error=True)
        else:
            status = UiStatus(message=result.message, is_error=result.is_error)
        finally:
            self._view.set_busy(False)

        self._view.set_status(status)
