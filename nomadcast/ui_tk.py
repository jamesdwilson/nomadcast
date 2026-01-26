from __future__ import annotations

"""NomadCast v0 Tkinter UI helpers."""

from dataclasses import dataclass
from typing import Callable

from nomadcast.app_install import maybe_prompt_install_app
from nomadcast.ui import SubscriptionService, UiStatus


@dataclass(frozen=True)
class TkUiConfig:
    """Configuration for the Tkinter UI layout."""

    title: str = "NomadCast v0"
    window_size: str = "720x420"


class TkUiLauncher:
    """Tkinter UI launcher for the NomadCast v0 application."""

    def __init__(self, initial_locator: str | None = None, config: TkUiConfig | None = None) -> None:
        self._initial_locator = initial_locator or ""
        self._config = config or TkUiConfig()

    def launch(self) -> None:
        """Launch the Tkinter UI application."""
        import tkinter as tk
        from tkinter import ttk
        from pathlib import Path

        service = SubscriptionService()

        root = tk.Tk()
        root.tk.call("tk", "appname", "NomadCast")
        root.title(self._config.title)
        root.geometry(self._config.window_size)
        root.configure(background="#11161e")
        icon_path = Path(__file__).resolve().parent.parent / "assets" / "nomadcast-logo.png"
        if icon_path.exists():
            icon_image = tk.PhotoImage(file=str(icon_path))
            root.iconphoto(True, icon_image)
            root.icon_image = icon_image

        root.withdraw()
        maybe_prompt_install_app(root)
        root.deiconify()

        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        frame = ttk.Frame(root, padding=24)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)

        header = ttk.Label(frame, text="NomadCast v0", font=("Segoe UI", 18, "bold"))
        header.grid(row=0, column=0, sticky="w", pady=(0, 12))

        subtitle = ttk.Label(
            frame,
            text=(
                "Paste a NomadCast locator to subscribe. "
                "NomadCast will add the feed to your local daemon and open "
                "your podcast app."
            ),
            wraplength=640,
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(0, 16))

        locator_var = tk.StringVar(value=self._initial_locator)
        locator_input = ttk.Entry(frame, textvariable=locator_var)
        locator_input.grid(row=2, column=0, sticky="ew", pady=(0, 16))

        button_row = ttk.Frame(frame)
        button_row.grid(row=3, column=0, sticky="ew", pady=(0, 16))
        button_row.columnconfigure(0, weight=1)

        status_var = tk.StringVar(value="Ready to add a show.")
        status_label = ttk.Label(frame, textvariable=status_var, foreground="#b8c7d6")
        status_label.grid(row=4, column=0, sticky="w")

        def set_status(status: UiStatus) -> None:
            status_var.set(status.message)
            status_label.configure(foreground="#f28072" if status.is_error else "#b8c7d6")

        def handle_add() -> None:
            locator = locator_var.get()
            try:
                status = service.add_subscription(locator)
            except ValueError as exc:
                status = UiStatus(message=f"Invalid locator: {exc}", is_error=True)
            except OSError as exc:
                status = UiStatus(message=f"Failed to update config: {exc}", is_error=True)
            set_status(status)

        def handle_not_implemented(action: Callable[[], UiStatus]) -> Callable[[], None]:
            def handler() -> None:
                try:
                    status = action()
                except NotImplementedError as exc:
                    status = UiStatus(message=str(exc), is_error=True)
                set_status(status)

            return handler

        add_button = ttk.Button(button_row, text="Add subscription", command=handle_add)
        add_button.configure(default="active")
        add_button.grid(row=0, column=0, sticky="w")

        daemon_button = ttk.Button(
            button_row, text="Manage daemon", command=handle_not_implemented(service.manage_daemon)
        )
        daemon_button.state(["disabled"])
        daemon_button.grid(row=0, column=1, sticky="w", padx=(12, 0))

        subscriptions_button = ttk.Button(
            button_row, text="Edit subscriptions", command=handle_not_implemented(service.edit_subscriptions)
        )
        subscriptions_button.state(["disabled"])
        subscriptions_button.grid(row=0, column=2, sticky="w", padx=(12, 0))

        cache_button = ttk.Button(
            button_row, text="View cache", command=handle_not_implemented(service.view_cache_status)
        )
        cache_button.state(["disabled"])
        cache_button.grid(row=0, column=3, sticky="w", padx=(12, 0))

        future_row = ttk.Frame(frame)
        future_row.grid(row=5, column=0, sticky="ew", pady=(8, 0))

        tray_button = ttk.Button(
            future_row, text="System tray", command=handle_not_implemented(service.system_tray_integration)
        )
        tray_button.state(["disabled"])
        tray_button.grid(row=0, column=0, sticky="w")

        health_button = ttk.Button(
            future_row, text="Health endpoint", command=handle_not_implemented(service.health_endpoint)
        )
        health_button.state(["disabled"])
        health_button.grid(row=0, column=1, sticky="w", padx=(12, 0))

        root.update_idletasks()
        window_width = root.winfo_width()
        window_height = root.winfo_height()
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        position_x = max((screen_width - window_width) // 2, 0)
        position_y = max((screen_height - window_height) // 2, 0)
        root.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")
        root.attributes("-topmost", True)
        root.lift()
        root.focus_force()
        root.after(250, lambda: root.attributes("-topmost", False))
        locator_input.focus()
        root.bind("<Return>", lambda event: add_button.invoke())
        coming_soon = ttk.Label(
            frame,
            text="More features are under development—thanks for trying NomadCast!",
            foreground="#8ea3b7",
        )
        coming_soon.grid(row=6, column=0, sticky="w", pady=(16, 0))
        root.mainloop()
