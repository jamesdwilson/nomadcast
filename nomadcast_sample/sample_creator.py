from __future__ import annotations

"""Standalone NomadCast sample creator app.

This module provides a focused Tkinter application that installs the sample
NomadCast "Relay Room" content into a creator's NomadNet storage. It is kept
separate from the main UI so that creator tooling can evolve independently.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from nomadcast_sample.sample_installer import (
    NOMADNET_GUIDE_URL,
    NomadNetIdentityDetection,
    SampleInstallResult,
    detect_nomadnet_identity,
    detect_nomadnet_node_name,
    install_sample,
    nomadnet_storage_root,
    open_in_file_browser,
    sanitize_show_name_for_path,
)


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

    def _center_window(self, root: "tk.Tk") -> None:
        """Center the Tkinter window on the active screen."""
        # Measure the window and screen so we can calculate a centered geometry.
        root.update_idletasks()
        window_width = root.winfo_width()
        window_height = root.winfo_height()
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        position_x = max((screen_width - window_width) // 2, 0)
        position_y = max((screen_height - window_height) // 2, 0)
        root.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")

    def launch(self) -> None:
        """Launch the sample creator UI and enter the Tkinter event loop."""
        # Import Tkinter lazily so that simply importing the module doesn't
        # require a GUI environment.
        import tkinter as tk
        from tkinter import messagebox, ttk
        import webbrowser

        # --- Window + theme setup -------------------------------------------------
        root = tk.Tk()
        root.tk.call("tk", "appname", "NomadCast")
        try:
            # macOS-specific app name for the menu bar and Dock.
            root.tk.call("tk::mac::SetApplicationName", "NomadCast")
        except tk.TclError:
            # Ignore if the Tk build doesn't support the call.
            pass
        root.title(self._config.title)
        root.geometry(self._config.window_size)
        root.configure(background="#11161e")

        # Use the shared NomadCast icon if it's available in the repo tree.
        icon_path = Path(__file__).resolve().parents[2] / "assets" / "nomadcast-logo.png"
        if icon_path.exists():
            icon_image = tk.PhotoImage(file=str(icon_path))
            root.iconphoto(True, icon_image)
            # Keep a reference to avoid the Tk image being garbage collected.
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

        # --- Layout scaffolding ---------------------------------------------------
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        frame = ttk.Frame(root, padding=28)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)

        header_frame = ttk.Frame(frame)
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header_frame.columnconfigure(0, weight=1)

        if banner_logo is not None:
            logo_label = ttk.Label(header_frame, image=banner_logo)
            logo_label.grid(row=0, column=0, sticky="n", pady=(0, 8))

        banner_label = tk.Label(
            header_frame,
            text="NOMADCAST SAMPLE CREATOR",
            font=("Segoe UI", 16, "bold"),
            background="#1b2230",
            foreground="#f5f7fa",
            padx=12,
            pady=6,
        )
        banner_label.grid(row=1, column=0, sticky="ew")

        header = ttk.Label(frame, text="FIRST TRANSMISSION STARTS HERE", font=("Segoe UI", 18, "bold"))
        header.grid(row=1, column=0, sticky="n", pady=(12, 10))

        subhead = ttk.Label(frame, text="Radio YOU is on the air.", font=("Segoe UI", 12))
        subhead.grid(row=2, column=0, sticky="n", pady=(0, 10))

        subtitle = ttk.Label(
            frame,
            text=(
                "We’ll carve out a real podcast home in your Nomad Network storage. "
                "It’s yours — decentralized from the first click."
            ),
            wraplength=640,
            justify="center",
        )
        subtitle.grid(row=3, column=0, sticky="n", pady=(0, 16))

        # --- Identity input -------------------------------------------------------
        identity_label = ttk.Label(frame, text="NomadNet node ID (used in links + feeds)")
        identity_label.grid(row=4, column=0, sticky="w")

        # Pre-fill with any identity we can detect; leave blank if none found.
        detected_identity = detect_nomadnet_identity()
        identity_value = detected_identity.identity if detected_identity else ""
        identity_var = tk.StringVar(value=identity_value)
        identity_input = ttk.Entry(frame, textvariable=identity_var)
        identity_input.grid(row=5, column=0, sticky="ew", pady=(4, 12))

        identity_hint = ttk.Label(frame, foreground="#8ea3b7")
        identity_hint.configure(text=_identity_hint_text(detected_identity))
        identity_hint.grid(row=6, column=0, sticky="w", pady=(0, 12))

        # --- Podcast name input --------------------------------------------------
        detected_node_name = detect_nomadnet_node_name()
        base_name = detected_node_name or "Nomad Node"
        show_name_suggestions = [
            f"{base_name} Radio",
            f"Dispatches from {base_name}",
            f"{base_name} Relay Room",
            f"Nomad Notes: {base_name}",
        ]
        show_name_value = show_name_suggestions[0] if detected_node_name else ""
        show_name_var = tk.StringVar(value=show_name_value)

        show_name_label = ttk.Label(frame, text="Podcast name")
        show_name_label.grid(row=7, column=0, sticky="w")

        show_name_input = ttk.Entry(frame, textvariable=show_name_var)
        show_name_input.grid(row=8, column=0, sticky="ew", pady=(4, 6))

        show_name_hint = ttk.Label(frame, foreground="#8ea3b7")
        show_name_hint.configure(text=_show_name_hint_text(detected_node_name))
        show_name_hint.grid(row=9, column=0, sticky="w", pady=(0, 8))

        suggestions_label = ttk.Label(frame, text="Name templates")
        suggestions_label.grid(row=10, column=0, sticky="w")

        suggestions_list = tk.Listbox(
            frame,
            height=4,
            width=62,
            background="#101720",
            foreground="#f5f7fa",
            highlightthickness=0,
            borderwidth=0,
        )
        for suggestion in show_name_suggestions:
            suggestions_list.insert(tk.END, suggestion)
        suggestions_list.grid(row=11, column=0, sticky="w", pady=(4, 12))

        def handle_show_name_select(event: tk.Event) -> None:
            selection = suggestions_list.curselection()
            if selection:
                show_name_var.set(suggestions_list.get(selection[0]))

        suggestions_list.bind("<<ListboxSelect>>", handle_show_name_select)

        # --- Page placement choices ----------------------------------------------
        choice_label = ttk.Label(frame, text="Where should we place the Relay Room pages?")
        choice_label.grid(row=12, column=0, sticky="w")

        location_var = tk.StringVar(value="replace_pages")
        replace_button = ttk.Radiobutton(
            frame,
            text=(
                "Replace the pages at ~/.nomadnetwork/storage/pages"
            ),
            value="replace_pages",
            variable=location_var,
        )
        replace_button.grid(row=13, column=0, sticky="w", pady=(4, 2))

        subdir_button = ttk.Radiobutton(
            frame,
            text=(
                "Create new folder at ~/.nomadnetwork/storage/pages/podcast"
            ),
            value="podcast_pages",
            variable=location_var,
        )
        subdir_button.grid(row=14, column=0, sticky="w", pady=(0, 16))

        pending_frame = ttk.Frame(frame)
        pending_frame.grid(row=15, column=0, sticky="w", pady=(0, 12))
        pending_frame.columnconfigure(0, weight=1)
        pending_frame.grid_remove()

        pending_label = ttk.Label(pending_frame, text="Pending actions")
        pending_label.grid(row=0, column=0, sticky="w")

        pending_list = tk.Listbox(
            pending_frame,
            height=4,
            width=62,
            background="#101720",
            foreground="#f5f7fa",
            highlightthickness=0,
            borderwidth=0,
        )
        pending_list.grid(row=1, column=0, sticky="w", pady=(4, 0))

        # --- Status line ----------------------------------------------------------
        status_var = tk.StringVar(value="Ready when you are. Let’s bring the Relay Room online.")
        status_label = ttk.Label(frame, textvariable=status_var, foreground="#b8c7d6")
        status_label.grid(row=16, column=0, sticky="w", pady=(0, 12))

        # Remember the install result so we can open the folders afterward.
        install_result: SampleInstallResult | None = None

        def update_status(message: str, *, is_error: bool = False) -> None:
            """Update the status message with optional error styling."""
            status_var.set(message)
            status_label.configure(foreground="#f28072" if is_error else "#b8c7d6")

        def show_pending_actions() -> None:
            pending_list.delete(0, tk.END)
            pending_actions = [
                "Create or update the Relay Room pages.",
                "Copy starter media files into the Relay Room.",
                "Write feed settings with your NomadNet node ID and show name.",
            ]
            for action in pending_actions:
                pending_list.insert(tk.END, f"• {action}")
            pending_frame.grid()

        def clear_pending_actions() -> None:
            pending_list.delete(0, tk.END)
            pending_frame.grid_remove()

        def ensure_identity() -> str | None:
            """Validate the identity input and return the trimmed value."""
            identity = identity_var.get().strip()
            if not identity:
                update_status("Pop in your NomadNet node ID so links work.", is_error=True)
                return None
            if len(identity) < 16:
                update_status("That ID looks a bit short. Could you double-check it?", is_error=True)
                return None
            return identity

        def ensure_show_name() -> str | None:
            """Validate the podcast name input and return the trimmed value."""
            show_name = show_name_var.get().strip()
            if not show_name:
                update_status("Add a podcast name so the install feels personal.", is_error=True)
                return None
            if len(show_name) < 3:
                update_status("That podcast name feels a little short.", is_error=True)
                return None
            if len(show_name) > 80:
                update_status("Podcast names should stay under 80 characters.", is_error=True)
                return None
            if not any(char.isalnum() for char in show_name):
                update_status("Please use a podcast name with letters or numbers.", is_error=True)
                return None
            return show_name

        def handle_install() -> None:
            """Install the sample content based on the selected options."""
            nonlocal install_result
            show_pending_actions()
            identity = ensure_identity()
            show_name = ensure_show_name()
            if not identity or not show_name:
                clear_pending_actions()
                return
            show_name_slug = sanitize_show_name_for_path(show_name)

            # Resolve the NomadNet storage root and the user's placement choice.
            storage_root = nomadnet_storage_root()
            location_choice = location_var.get()
            replace_existing = location_choice == "replace_pages"

            if replace_existing:
                # Ask for confirmation before wiping the existing pages directory.
                confirm = messagebox.askyesno(
                    title="Replace existing pages?",
                    message=(
                        "We’ll replace the NomadNet pages at "
                        "~/.nomadnetwork/storage/pages and refresh the Relay Room "
                        f"starter files under ~/.nomadnetwork/storage/files/{show_name_slug}.\n\n"
                        "Sound good?"
                    ),
                    parent=root,
                )
                if not confirm:
                    update_status("All good — no changes made.")
                    clear_pending_actions()
                    return
                pages_path = storage_root / "pages"
            elif location_choice == "podcast_pages":
                pages_path = storage_root / "pages" / "podcast"
            else:
                update_status("Please pick a landing spot for the pages.", is_error=True)
                clear_pending_actions()
                return

            # Run the installer and handle any file-system errors gracefully.
            try:
                install_result = install_sample(
                    storage_root=storage_root,
                    pages_path=pages_path,
                    identity=identity,
                    show_name=show_name,
                    show_name_slug=show_name_slug,
                    replace_existing=replace_existing,
                )
            except OSError as exc:
                update_status(f"Oops, the install hiccuped: {exc}", is_error=True)
                clear_pending_actions()
                return

            clear_pending_actions()
            update_status(
                f"Relay Room is ready! Pages: {install_result.pages_path} | "
                f"Media: {install_result.media_path}"
            )
            messagebox.showinfo(
                title="Relay Room is ready",
                message="Relay Room files are staged. Open the pages or media folders to continue.",
                parent=root,
            )

        def handle_open_pages() -> None:
            """Open the generated pages folder in the OS file browser."""
            if not install_result:
                update_status("Run Begin Transmission first to set up pages.", is_error=True)
                return
            try:
                open_in_file_browser(install_result.pages_path)
            except OSError as exc:
                update_status(f"Could not open pages: {exc}", is_error=True)

        def handle_open_media() -> None:
            """Open the generated media folder in the OS file browser."""
            if not install_result:
                update_status("Run Begin Transmission first to set up media.", is_error=True)
                return
            try:
                open_in_file_browser(install_result.media_path)
            except OSError as exc:
                update_status(f"Could not open media: {exc}", is_error=True)

        def handle_open_guide() -> None:
            """Launch the NomadNet hosting guide in a browser."""
            webbrowser.open(NOMADNET_GUIDE_URL)

        # --- Action buttons -------------------------------------------------------
        actions_row = ttk.Frame(frame)
        actions_row.grid(row=17, column=0, sticky="w", pady=(4, 16))

        install_button = ttk.Button(actions_row, text="BEGIN TRANSMISSION", command=handle_install)
        install_button.configure(default="active")
        install_button.grid(row=0, column=0, sticky="w")

        guide_button = ttk.Button(actions_row, text="NomadNet page hosting guide", command=handle_open_guide)
        guide_button.grid(row=0, column=1, sticky="w", padx=(12, 0))

        # --- Folder shortcuts -----------------------------------------------------
        links_row = ttk.Frame(frame)
        links_row.grid(row=18, column=0, sticky="w")

        open_pages_button = ttk.Button(links_row, text="📁 Open Pages root", command=handle_open_pages)
        open_pages_button.grid(row=0, column=0, sticky="w")

        open_media_button = ttk.Button(links_row, text="📁 Open Media root", command=handle_open_media)
        open_media_button.grid(row=0, column=1, sticky="w", padx=(12, 0))

        self._center_window(root)
        identity_input.focus()
        root.bind("<Return>", lambda event: install_button.invoke())
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
