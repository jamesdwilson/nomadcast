from __future__ import annotations

from nomadcast_sample.domain.types import IdentityValidationError, ShowNameValidationError


def validate_identity(identity: str) -> list[IdentityValidationError]:
    trimmed = identity.strip()
    errors: list[IdentityValidationError] = []
    if not trimmed:
        errors.append(IdentityValidationError.MISSING)
    elif len(trimmed) < 16:
        errors.append(IdentityValidationError.TOO_SHORT)
    return errors


def validate_show_name(show_name: str) -> list[ShowNameValidationError]:
    trimmed = show_name.strip()
    errors: list[ShowNameValidationError] = []
    if not trimmed:
        errors.append(ShowNameValidationError.MISSING)
        return errors
    if len(trimmed) < 3:
        errors.append(ShowNameValidationError.TOO_SHORT)
    if len(trimmed) > 80:
        errors.append(ShowNameValidationError.TOO_LONG)
    if not any(char.isalnum() for char in trimmed):
        errors.append(ShowNameValidationError.MISSING_ALNUM)
    return errors
