from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from nomadcast_sample.domain.types import (
    IdentityValidationError,
    SampleCreatorInput,
    ShowNameValidationError,
)
from nomadcast_sample.domain.validation import validate_identity, validate_show_name
from nomadcast_sample.sample_installer import SampleInstallResult


class SampleCreatorView(Protocol):
    def get_form_data(self) -> SampleCreatorInput:
        ...

    def set_status(self, message: str, *, is_error: bool = False) -> None:
        ...

    def set_pending_actions(self, items: Sequence[str]) -> None:
        ...

    def clear_pending_actions(self) -> None:
        ...


@dataclass(frozen=True)
class SampleCreatorDependencies:
    install_sample: Callable[..., SampleInstallResult]
    open_in_file_browser: Callable[[Path], None]
    sanitize_show_name_for_path: Callable[[str], str]
    nomadnet_storage_root: Callable[[], Path]
    guide_url: str
    show_info: Callable[..., None]
    confirm_yes_no: Callable[..., bool]
    open_url: Callable[[str], None]


class SampleCreatorController:
    def __init__(
        self,
        *,
        dependencies: SampleCreatorDependencies,
    ) -> None:
        self._dependencies = dependencies
        self._view: SampleCreatorView | None = None
        self._install_result: SampleInstallResult | None = None

    def attach_view(self, view: SampleCreatorView) -> None:
        self._view = view

    def _require_view(self) -> SampleCreatorView:
        if not self._view:
            raise RuntimeError("SampleCreatorView not attached")
        return self._view

    def handle_install(self) -> None:
        view = self._require_view()
        view.set_pending_actions(
            [
                "Create or update the Relay Room pages.",
                "Copy starter media files into the Relay Room.",
                "Write feed settings with your NomadNet node ID and show name.",
            ]
        )
        form_data = view.get_form_data()
        identity = form_data.identity.strip()
        show_name = form_data.show_name.strip()

        identity_errors = validate_identity(identity)
        if identity_errors:
            view.set_status(self._identity_error_message(identity_errors), is_error=True)
            view.clear_pending_actions()
            return

        show_name_errors = validate_show_name(show_name)
        if show_name_errors:
            view.set_status(self._show_name_error_message(show_name_errors), is_error=True)
            view.clear_pending_actions()
            return

        show_name_slug = self._dependencies.sanitize_show_name_for_path(show_name)
        storage_root = self._dependencies.nomadnet_storage_root()
        location_choice = form_data.location_choice

        if location_choice == "replace_pages":
            confirm = self._dependencies.confirm_yes_no(
                title="Replace existing pages?",
                message=(
                    "We’ll replace the NomadNet pages at "
                    "~/.nomadnetwork/storage/pages and refresh the Relay Room "
                    f"starter files under ~/.nomadnetwork/storage/files/{show_name_slug}.\n\n"
                    "Sound good?"
                ),
            )
            if not confirm:
                view.set_status("All good — no changes made.")
                view.clear_pending_actions()
                return
            pages_path = storage_root / "pages"
        elif location_choice == "podcast_pages":
            pages_path = storage_root / "pages" / "podcast"
        else:
            view.set_status("Please pick a landing spot for the pages.", is_error=True)
            view.clear_pending_actions()
            return

        try:
            self._install_result = self._dependencies.install_sample(
                storage_root=storage_root,
                pages_path=pages_path,
                identity=identity,
                show_name=show_name,
                show_name_slug=show_name_slug,
                replace_existing=location_choice == "replace_pages",
            )
        except OSError as exc:
            view.set_status(f"Oops, the install hiccuped: {exc}", is_error=True)
            view.clear_pending_actions()
            return

        view.clear_pending_actions()
        view.set_status(
            "Relay Room is ready! "
            f"Pages: {self._install_result.pages_path} | "
            f"Media: {self._install_result.media_path}"
        )
        self._dependencies.show_info(
            title="Relay Room is ready",
            message="Relay Room files are staged. Open the pages or media folders to continue.",
        )

    def handle_open_pages(self) -> None:
        view = self._require_view()
        if not self._install_result:
            view.set_status("Run Begin Transmission first to set up pages.", is_error=True)
            return
        try:
            self._dependencies.open_in_file_browser(self._install_result.pages_path)
        except OSError as exc:
            view.set_status(f"Could not open pages: {exc}", is_error=True)

    def handle_open_media(self) -> None:
        view = self._require_view()
        if not self._install_result:
            view.set_status("Run Begin Transmission first to set up media.", is_error=True)
            return
        try:
            self._dependencies.open_in_file_browser(self._install_result.media_path)
        except OSError as exc:
            view.set_status(f"Could not open media: {exc}", is_error=True)

    def handle_open_guide(self) -> None:
        self._dependencies.open_url(self._dependencies.guide_url)

    @staticmethod
    def _identity_error_message(errors: Sequence[IdentityValidationError]) -> str:
        if IdentityValidationError.MISSING in errors:
            return "Pop in your NomadNet node ID so links work."
        if IdentityValidationError.TOO_SHORT in errors:
            return "That ID looks a bit short. Could you double-check it?"
        return "Please enter a valid NomadNet node ID."

    @staticmethod
    def _show_name_error_message(errors: Sequence[ShowNameValidationError]) -> str:
        if ShowNameValidationError.MISSING in errors:
            return "Add a podcast name so the install feels personal."
        if ShowNameValidationError.TOO_SHORT in errors:
            return "That podcast name feels a little short."
        if ShowNameValidationError.TOO_LONG in errors:
            return "Podcast names should stay under 80 characters."
        if ShowNameValidationError.MISSING_ALNUM in errors:
            return "Please use a podcast name with letters or numbers."
        return "Please enter a valid podcast name."
