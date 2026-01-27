from __future__ import annotations

"""Standalone NomadCast sample creator app."""

from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from nomadcast.sample_installer import (
    NOMADNET_GUIDE_URL,
    PLACEHOLDER_IDENTITY,
    SampleInstallResult,
    detect_nomadnet_identity,
    install_sample,
    nomadnet_storage_root,
    open_in_file_browser,
)


@dataclass(frozen=True)
class SampleCreatorConfig:
    title: str = "NomadCast Relay Room"
    window_size: str = "720x520"


class SampleCreatorApp:
    def __init__(self, config: SampleCreatorConfig | None = None) -> None:
        self._config = config or SampleCreatorConfig()

    def _center_window(self, root: "tk.Tk") -> None:
        root.update_idletasks()
        window_width = root.winfo_width()
        window_height = root.winfo_height()
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        position_x = max((screen_width - window_width) // 2, 0)
        position_y = max((screen_height - window_height) // 2, 0)
        root.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")

    def launch(self) -> None:
        import tkinter as tk
        from tkinter import messagebox, ttk
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

        icon_path = Path(__file__).resolve().parents[2] / "assets" / "nomadcast-logo.png"
        if icon_path.exists():
            icon_image = tk.PhotoImage(file=str(icon_path))
            root.iconphoto(True, icon_image)
            root.icon_image = icon_image

        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        frame = ttk.Frame(root, padding=28)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)

        header = ttk.Label(frame, text="FIRST TRANSMISSION STARTS HERE", font=("Segoe UI", 20, "bold"))
        header.grid(row=0, column=0, sticky="n", pady=(0, 12))

        subhead = ttk.Label(frame, text="Radio YOU is on the air.", font=("Segoe UI", 12))
        subhead.grid(row=1, column=0, sticky="n", pady=(0, 10))

        subtitle = ttk.Label(
            frame,
            text=(
                "We’ll carve out a real podcast home in your Nomad Network storage. "
                "It’s yours — decentralized from the first click."
            ),
            wraplength=640,
            justify="center",
        )
        subtitle.grid(row=2, column=0, sticky="n", pady=(0, 16))

        identity_label = ttk.Label(frame, text="NomadNet node ID (used in links + feeds)")
        identity_label.grid(row=3, column=0, sticky="w")

        detected_identity = detect_nomadnet_identity() or PLACEHOLDER_IDENTITY
        identity_var = tk.StringVar(value=detected_identity)
        identity_input = ttk.Entry(frame, textvariable=identity_var)
        identity_input.grid(row=4, column=0, sticky="ew", pady=(4, 12))

        identity_hint = ttk.Label(
            frame,
            text="We’ll thread this ID into the Relay Room pages and RSS feed.",
            foreground="#8ea3b7",
        )
        identity_hint.grid(row=5, column=0, sticky="w", pady=(0, 12))

        choice_label = ttk.Label(frame, text="Where should we place the Relay Room pages?")
        choice_label.grid(row=6, column=0, sticky="w")

        location_var = tk.StringVar(value="replace_pages")
        replace_button = ttk.Radiobutton(
            frame,
            text=(
                "Replace the pages at ~/.nomadnetwork/storage/pages "
                "(also refreshes Relay Room files under ~/.nomadnetwork/storage/files/ExampleNomadCastPodcast)"
            ),
            value="replace_pages",
            variable=location_var,
        )
        replace_button.grid(row=7, column=0, sticky="w", pady=(4, 2))

        subdir_button = ttk.Radiobutton(
            frame,
            text=(
                "Nest pages under ~/.nomadnetwork/storage/pages/podcast "
                "(Relay Room files still go to ~/.nomadnetwork/storage/files/ExampleNomadCastPodcast)"
            ),
            value="podcast_pages",
            variable=location_var,
        )
        subdir_button.grid(row=8, column=0, sticky="w", pady=(0, 16))

        status_var = tk.StringVar(value="Ready when you are. Let’s bring the Relay Room online.")
        status_label = ttk.Label(frame, textvariable=status_var, foreground="#b8c7d6")
        status_label.grid(row=9, column=0, sticky="w", pady=(0, 12))

        install_result: SampleInstallResult | None = None

        def update_status(message: str, *, is_error: bool = False) -> None:
            status_var.set(message)
            status_label.configure(foreground="#f28072" if is_error else "#b8c7d6")

        def ensure_identity() -> str | None:
            identity = identity_var.get().strip()
            if not identity:
                update_status("Pop in your NomadNet node ID so links work.", is_error=True)
                return None
            if len(identity) < 16:
                update_status("That ID looks a bit short. Could you double-check it?", is_error=True)
                return None
            return identity

        def handle_install() -> None:
            nonlocal install_result
            identity = ensure_identity()
            if not identity:
                return
            storage_root = nomadnet_storage_root()
            location_choice = location_var.get()
            replace_existing = location_choice == "replace_pages"
            if replace_existing:
                confirm = messagebox.askyesno(
                    title="Replace existing pages?",
                    message=(
                        "We’ll replace the NomadNet pages at "
                        "~/.nomadnetwork/storage/pages and refresh the Relay Room "
                        "starter files under ~/.nomadnetwork/storage/files/ExampleNomadCastPodcast.\n\n"
                        "Sound good?"
                    ),
                    parent=root,
                )
                if not confirm:
                    update_status("All good — no changes made.")
                    return
                pages_path = storage_root / "pages"
            elif location_choice == "podcast_pages":
                pages_path = storage_root / "pages" / "podcast"
            else:
                update_status("Please pick a landing spot for the pages.", is_error=True)
                return

            try:
                install_result = install_sample(
                    storage_root=storage_root,
                    pages_path=pages_path,
                    identity=identity,
                    replace_existing=replace_existing,
                )
            except OSError as exc:
                update_status(f"Oops, the install hiccuped: {exc}", is_error=True)
                return

            open_pages_button.state(["!disabled"])
            open_media_button.state(["!disabled"])
            update_status(
                f"Relay Room is ready! Pages: {install_result.pages_path} | "
                f"Media: {install_result.media_path}"
            )

        def handle_open_pages() -> None:
            if not install_result:
                return
            try:
                open_in_file_browser(install_result.pages_path)
            except OSError as exc:
                update_status(f"Could not open pages: {exc}", is_error=True)

        def handle_open_media() -> None:
            if not install_result:
                return
            try:
                open_in_file_browser(install_result.media_path)
            except OSError as exc:
                update_status(f"Could not open media: {exc}", is_error=True)

        def handle_open_guide() -> None:
            webbrowser.open(NOMADNET_GUIDE_URL)

        actions_row = ttk.Frame(frame)
        actions_row.grid(row=10, column=0, sticky="w", pady=(4, 16))

        install_button = ttk.Button(actions_row, text="BEGIN TRANSMISSION", command=handle_install)
        install_button.configure(default="active")
        install_button.grid(row=0, column=0, sticky="w")

        guide_button = ttk.Button(actions_row, text="NomadNet page hosting guide", command=handle_open_guide)
        guide_button.grid(row=0, column=1, sticky="w", padx=(12, 0))

        links_row = ttk.Frame(frame)
        links_row.grid(row=11, column=0, sticky="w")

        open_pages_button = ttk.Button(links_row, text="📁 Open Pages root", command=handle_open_pages)
        open_pages_button.state(["disabled"])
        open_pages_button.grid(row=0, column=0, sticky="w")

        open_media_button = ttk.Button(links_row, text="📁 Open Media root", command=handle_open_media)
        open_media_button.state(["disabled"])
        open_media_button.grid(row=0, column=1, sticky="w", padx=(12, 0))

        footer = ttk.Label(
            frame,
            text=(
                "Tip: You’ve made it to the Relay Room — now you can swap in fresh episodes and update the RSS feed "
                "whenever your broadcast needs shift."
            ),
            foreground="#8ea3b7",
        )
        footer.grid(row=12, column=0, sticky="w", pady=(16, 0))

        self._center_window(root)
        identity_input.focus()
        root.bind("<Return>", lambda event: install_button.invoke())
        root.mainloop()


def main() -> NoReturn:
    SampleCreatorApp().launch()


if __name__ == "__main__":
    main()
