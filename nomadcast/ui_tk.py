from __future__ import annotations

"""NomadCast v0 Tkinter UI helpers."""

from dataclasses import dataclass
from typing import Protocol

from nomadcast.app_install import maybe_prompt_install_app
from nomadcast.controllers.main_controller import MainController
from nomadcast.ui import SubscriptionService, UiStatus
from nomadcast.ui.main_view import MainView


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

        view = MainView(
            root,
            on_add=lambda: None,
            on_manage_daemon=lambda: None,
            on_edit_subscriptions=lambda: None,
            on_view_cache=lambda: None,
            on_health_endpoint=lambda: None,
            initial_locator=self._initial_locator,
        )
        view.grid(row=0, column=0, sticky="nsew")

        controller = MainController(view=view, service=service, logger=logger)
        view.set_callbacks(
            on_add=controller.on_add,
            on_manage_daemon=controller.on_manage_daemon,
            on_edit_subscriptions=controller.on_edit_subscriptions,
            on_view_cache=controller.on_view_cache,
            on_health_endpoint=controller.on_health_endpoint,
        )

        def set_status(status: UiStatus) -> None:
            view.set_status(status)

        self._center_window(root)
        try:
            root.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        view.focus_first()

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
