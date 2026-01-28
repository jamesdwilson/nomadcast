from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IdentityValidationError(Enum):
    MISSING = "missing"
    TOO_SHORT = "too_short"


class ShowNameValidationError(Enum):
    MISSING = "missing"
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    MISSING_ALNUM = "missing_alnum"


@dataclass(frozen=True)
class SampleCreatorInput:
    identity: str
    show_name: str
    location_choice: str
