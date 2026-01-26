from __future__ import annotations

"""NomadCast v0 Tkinter UI helpers."""

from dataclasses import dataclass
from typing import Callable, Protocol

from nomadcast.app_install import maybe_prompt_install_app
from nomadcast.ui import SubscriptionService, UiStatus


class TrayIcon(Protocol):
    """Protocol for tray icon behaviors used by the UI."""

    def stop(self) -> None:
        """Stop the tray icon event loop."""


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

    def _apply_tray_window_hints(self, root: "tk.Tk") -> None:
        """Apply best-effort window hints to hide dock/taskbar entries."""
        import platform
        import tkinter as tk

        system = platform.system()
        if system == "Windows":
            try:
                root.wm_attributes("-toolwindow", True)
            except tk.TclError:
                pass
        elif system == "Linux":
            # X11-only hint for utility windows; ignored on Wayland.
            try:
                root.wm_attributes("-type", "utility")
            except tk.TclError:
                pass
        elif system == "Darwin":
            # Hiding the Dock icon is typically controlled via app bundles;
            # this is a best-effort hint for Tk builds that support it.
            try:
                root.tk.call("tk::mac::ShowHide", "hide")
            except tk.TclError:
                pass

    def _center_window(self, root: "tk.Tk") -> None:
        """Center the window on the active screen."""
        root.update_idletasks()
        window_width = root.winfo_width()
        window_height = root.winfo_height()
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        position_x = max((screen_width - window_width) // 2, 0)
        position_y = max((screen_height - window_height) // 2, 0)
        root.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")

    def _animate_visibility(
        self,
        root: "tk.Tk",
        *,
        show: bool,
        duration_ms: int = 180,
        steps: int = 12,
    ) -> None:
        """Fade the window in or out with a short animation."""
        import tkinter as tk

        if steps <= 0:
            steps = 1
        try:
            current_alpha = float(root.attributes("-alpha"))
        except (tk.TclError, ValueError):
            current_alpha = 1.0 if show else 0.0
        start_alpha = max(0.0, min(1.0, current_alpha))
        end_alpha = 1.0 if show else 0.0
        delta = (end_alpha - start_alpha) / steps
        interval = max(duration_ms // steps, 1)

        def step(index: int, alpha: float) -> None:
            try:
                root.attributes("-alpha", max(0.0, min(1.0, alpha)))
            except tk.TclError:
                return
            if index < steps:
                root.after(interval, step, index + 1, alpha + delta)
            elif not show:
                root.withdraw()

        if show:
            root.deiconify()
            root.lift()
            root.focus_force()
        step(0, start_alpha)

    def launch(self) -> None:
        """Launch the Tkinter UI application."""
        import tkinter as tk
        from tkinter import ttk
        from pathlib import Path
        import platform
        import os
        import logging

        service = SubscriptionService()
        logger = logging.getLogger(__name__)

        if platform.system() == "Darwin":
            os.environ.setdefault("CFBundleName", "NomadCast")
            os.environ.setdefault("CFBundleDisplayName", "NomadCast")

        root = tk.Tk()
        root.tk.call("tk", "appname", "NomadCast")
        if platform.system() == "Darwin":
            try:
                root.tk.call("tk::mac::SetApplicationName", "NomadCast")
            except tk.TclError:
                pass
        root.title(self._config.title)
        root.geometry(self._config.window_size)
        root.configure(background="#11161e")
        icon_path = Path(__file__).resolve().parent.parent / "assets" / "nomadcast-logo.png"
        if icon_path.exists():
            icon_image = tk.PhotoImage(file=str(icon_path))
            root.iconphoto(True, icon_image)
            root.icon_image = icon_image

        root.withdraw()
        self._apply_tray_window_hints(root)

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
                logger.warning("Invalid locator entered: %s", exc)
                status = UiStatus(message=f"Invalid locator: {exc}", is_error=True)
            except OSError as exc:
                logger.exception("Failed to update config: %s", exc)
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

        health_button = ttk.Button(
            future_row, text="Health endpoint", command=handle_not_implemented(service.health_endpoint)
        )
        health_button.state(["disabled"])
        health_button.grid(row=0, column=0, sticky="w")

        self._center_window(root)
        try:
            root.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        locator_input.focus()
        root.bind("<Return>", lambda event: add_button.invoke())
        coming_soon = ttk.Label(
            frame,
            text="More features are under development—thanks for trying NomadCast!",
            foreground="#8ea3b7",
        )
        coming_soon.grid(row=6, column=0, sticky="w", pady=(16, 0))

        def toggle_visibility() -> None:
            """Toggle the Tk window visibility with a fade animation."""
            is_visible = root.state() != "withdrawn"
            if is_visible:
                self._animate_visibility(root, show=False)
            else:
                self._center_window(root)
                self._animate_visibility(root, show=True)

        tray_icon: TrayIcon | None = None

        def handle_quit() -> None:
            """Quit the UI without stopping the daemon."""
            if tray_icon is not None:
                tray_icon.stop()
            root.quit()

        def schedule_toggle(_icon: "pystray.Icon" | None = None, _item: "pystray.MenuItem" | None = None) -> None:
            """Schedule a toggle from the tray thread."""
            root.after(0, toggle_visibility)

        def schedule_quit(_icon: "pystray.Icon", _item: "pystray.MenuItem") -> None:
            """Schedule a quit from the tray thread."""
            root.after(0, handle_quit)

        def start_tray_icon() -> bool:
            """Start the system tray/menu bar integration."""
            nonlocal tray_icon
            try:
                from PIL import Image
                import pystray
            except Exception as exc:
                set_status(UiStatus(message=f"Tray icon unavailable: {exc}", is_error=True))
                return False

            def build_menu() -> pystray.Menu:
                """Build the tray/menu bar menu."""
                return pystray.Menu(
                    pystray.MenuItem("Show/Hide", schedule_toggle, default=True),
                    pystray.MenuItem("Quit (does not stop daemon)", schedule_quit),
                )

            if icon_path.exists():
                tray_image = Image.open(icon_path)
            else:
                tray_image = Image.new("RGBA", (64, 64), (17, 22, 30, 255))
            tray_icon = pystray.Icon("nomadcast", tray_image, "NomadCast", build_menu())

            root.protocol("WM_DELETE_WINDOW", lambda: root.after(0, toggle_visibility))

            try:
                tray_icon.run_detached()
            except Exception as exc:
                set_status(UiStatus(message=f"Tray icon failed to start: {exc}", is_error=True))
                tray_icon = None
                return False
            return True

        if not start_tray_icon():
            self._center_window(root)
            self._animate_visibility(root, show=True)
        root.after(0, lambda: maybe_prompt_install_app(root))
        root.mainloop()
