from __future__ import annotations

"""Standalone NomadCast sample creator app.

This module provides a focused Tkinter application that installs the sample
NomadCast "Relay Room" content into a creator's NomadNet storage. It is kept
separate from the main UI so that creator tooling can evolve independently.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from nomadcast_sample.controllers.main_controller import (
    SampleCreatorController,
    SampleCreatorDependencies,
)
from nomadcast_sample.sample_installer import (
    NOMADNET_GUIDE_URL,
    NomadNetIdentityDetection,
    detect_nomadnet_identity,
    detect_nomadnet_node_name,
    install_sample,
    nomadnet_storage_root,
    open_in_file_browser,
    sanitize_show_name_for_path,
)
from nomadcast_sample.ui.main_view import SampleCreatorView


@dataclass(frozen=True)
class SampleCreatorConfig:
    """Configuration for the sample creator window."""

    title: str = "NomadCast Relay Room"
    window_size: str = "760x640"


class SampleCreatorApp:
    """Tkinter launcher for the NomadCast sample creator experience."""

    def __init__(self, config: SampleCreatorConfig | None = None) -> None:
        """Initialize the app with an optional UI configuration."""
        self._config = config or SampleCreatorConfig()

    def launch(self) -> None:
        """Launch the sample creator UI and enter the Tkinter event loop."""
        import tkinter as tk
        from tkinter import messagebox
        import webbrowser

        root = tk.Tk()
        root.tk.call("tk", "appname", "NomadCast")
        try:
            root.tk.call("tk::mac::SetApplicationName", "NomadCast")
        except tk.TclError:
            pass
        root.title(self._config.title)
        root.geometry(self._config.window_size)
        root.configure(background="#11161e")

        icon_path = Path(__file__).resolve().parents[1] / "assets" / "nomadcast-logo.png"
        if icon_path.exists():
            icon_image = tk.PhotoImage(file=str(icon_path))
            root.iconphoto(True, icon_image)
            root.icon_image = icon_image
            banner_logo = icon_image.zoom(2, 2)
            root.banner_logo = banner_logo
        else:
            banner_logo = None

        root.update_idletasks()
        root.deiconify()
        root.lift()
        try:
            root.attributes("-topmost", True)
            root.after(150, lambda: root.attributes("-topmost", False))
        except tk.TclError:
            pass

        detected_identity = detect_nomadnet_identity()
        identity_value = detected_identity.identity if detected_identity else ""
        identity_hint = _identity_hint_text(detected_identity)

        detected_node_name = detect_nomadnet_node_name()
        base_name = detected_node_name or "Nomad Node"
        show_name_suggestions = [
            f"{base_name} Radio",
            f"Dispatches from {base_name}",
            f"{base_name} Relay Room",
            f"Nomad Notes: {base_name}",
        ]
        show_name_value = show_name_suggestions[0] if detected_node_name else ""
        show_name_hint = _show_name_hint_text(detected_node_name)

        dependencies = SampleCreatorDependencies(
            install_sample=install_sample,
            open_in_file_browser=open_in_file_browser,
            sanitize_show_name_for_path=sanitize_show_name_for_path,
            nomadnet_storage_root=nomadnet_storage_root,
            guide_url=NOMADNET_GUIDE_URL,
            show_info=lambda **kwargs: messagebox.showinfo(parent=root, **kwargs),
            confirm_yes_no=lambda **kwargs: messagebox.askyesno(parent=root, **kwargs),
            open_url=webbrowser.open,
        )
        controller = SampleCreatorController(dependencies=dependencies)
        view = SampleCreatorView(
            root,
            banner_logo=banner_logo,
            identity_value=identity_value,
            identity_hint=identity_hint,
            show_name_value=show_name_value,
            show_name_hint=show_name_hint,
            show_name_suggestions=show_name_suggestions,
            on_install=controller.handle_install,
            on_open_pages=controller.handle_open_pages,
            on_open_media=controller.handle_open_media,
            on_open_guide=controller.handle_open_guide,
        )
        controller.attach_view(view)

        view.focus_first()
        root.mainloop()


def _identity_hint_text(detected: NomadNetIdentityDetection | None) -> str:
    """Build the hint text for the identity input."""
    if detected:
        return (
            "Detected from "
            f"{detected.source_path}. We’ll thread this ID into the Relay Room pages and RSS feed."
        )
    return "We’ll thread this ID into the Relay Room pages and RSS feed."


def _show_name_hint_text(detected_node_name: str | None) -> str:
    """Build the hint text for the podcast name input."""
    if detected_node_name:
        return f"Pulled from your NomadNet config: {detected_node_name}."
    return "Pick a show name that matches your node’s vibe."


def main() -> NoReturn:
    """Entry point for launching the sample creator app."""
    SampleCreatorApp().launch()


if __name__ == "__main__":
    main()
