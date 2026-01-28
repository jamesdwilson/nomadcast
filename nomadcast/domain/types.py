from __future__ import annotations

"""Domain input types and validation helpers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LocatorInput:
    """Input payload for a subscription locator."""

    locator: str


def validate_locator(locator: LocatorInput) -> list[str]:
    """Validate the locator input and return error messages."""
    errors: list[str] = []
    if not locator.locator.strip():
        errors.append("Locator cannot be empty.")
    return errors
