from __future__ import annotations

"""NomadCast v0 Tkinter UI helpers."""

from dataclasses import dataclass

from nomadcast.app_install import maybe_prompt_install_app
from nomadcast.controllers.main_controller import MainController
from nomadcast.ui import SubscriptionService, UiStatus
from nomadcast.ui.main_view import MainView
from nomadcast.ui.style import init_style
from nomadcast.ui.tray import TkTrayController
from nomadcast.ui.window_animator import TkWindowAnimator


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
        init_style(ttk.Style(root))
        icon_path = Path(__file__).resolve().parent.parent / "assets" / "nomadcast-logo.png"
        if icon_path.exists():
            icon_image = tk.PhotoImage(file=str(icon_path))
            root.iconphoto(True, icon_image)
            root.icon_image = icon_image

        root.withdraw()
        animator = TkWindowAnimator(root)
        animator.apply_tray_window_hints()

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

        animator.center_window()
        try:
            root.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        view.focus_first()

        def toggle_visibility() -> None:
            """Toggle the Tk window visibility with a fade animation."""
            is_visible = root.state() != "withdrawn"
            if is_visible:
                animator.animate_visibility(show=False)
            else:
                animator.center_window()
                animator.animate_visibility(show=True)

        tray_controller = TkTrayController(icon_path=icon_path, set_status=set_status)

        def schedule_toggle() -> None:
            """Schedule a toggle from the tray thread."""
            root.after(0, toggle_visibility)

        def schedule_quit() -> None:
            """Schedule a quit from the tray thread."""
            root.after(0, handle_quit)

        def handle_quit() -> None:
            """Quit the UI without stopping the daemon."""
            tray_controller.stop()
            root.quit()

        tray_controller.bind_toggle(schedule_toggle)
        tray_controller.bind_quit(schedule_quit)

        root.protocol("WM_DELETE_WINDOW", lambda: root.after(0, toggle_visibility))

        if not tray_controller.start():
            animator.center_window()
            animator.animate_visibility(show=True)
        root.after(0, lambda: maybe_prompt_install_app(root))
        root.mainloop()
