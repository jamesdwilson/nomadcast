from __future__ import annotations

"""NomadCast v0 Tkinter UI helpers."""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
import platform
import tkinter as tk
from tkinter import ttk

from nomadcast.app_install import maybe_prompt_install_app
from nomadcast.controllers.main_controller import MainController
from nomadcast.services.subscriptions import SubscriptionService
from nomadcast.ui import UiStatus
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
        self._root: tk.Tk | None = None
        self._animator: TkWindowAnimator | None = None
        self._tray_controller: TkTrayController | None = None
        self._icon_path: Path | None = None
        self._view: MainView | None = None

    def launch(self) -> None:
        """Launch the Tkinter UI application."""
        service = SubscriptionService()
        logger = logging.getLogger(__name__)

        if platform.system() == "Darwin":
            os.environ.setdefault("CFBundleName", "NomadCast")
            os.environ.setdefault("CFBundleDisplayName", "NomadCast")

        root = self._configure_root()
        self._root = root
        animator = TkWindowAnimator(root)
        animator.apply_tray_window_hints()
        self._animator = animator
        view = self._build_view(root)
        self._view = view
        self._wire_controller(view, service, logger)
        animator.center_window()
        try:
            root.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        view.focus_first()

        tray_controller = self._setup_tray(root, animator, view, self._icon_path)
        self._tray_controller = tray_controller

        root.protocol("WM_DELETE_WINDOW", lambda: root.after(0, self._toggle_visibility))

        if not tray_controller.start():
            animator.center_window()
            animator.animate_visibility(show=True)
        root.after(0, lambda: maybe_prompt_install_app(root))
        root.mainloop()

    def _configure_root(self) -> tk.Tk:
        """Create and configure the root Tk instance."""
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
        self._icon_path = Path(__file__).resolve().parent.parent / "assets" / "nomadcast-logo.png"
        if self._icon_path.exists():
            icon_image = tk.PhotoImage(file=str(self._icon_path))
            root.iconphoto(True, icon_image)
            root.icon_image = icon_image
        root.withdraw()
        return root

    def _build_view(self, root: tk.Tk) -> MainView:
        """Build the main view for the root window."""
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
        return view

    def _wire_controller(
        self,
        view: MainView,
        service: SubscriptionService,
        logger: logging.Logger,
    ) -> MainController:
        """Connect the view callbacks to the main controller."""
        controller = MainController(view=view, service=service, logger=logger)
        view.set_callbacks(
            on_add=controller.on_add,
            on_manage_daemon=controller.on_manage_daemon,
            on_edit_subscriptions=controller.on_edit_subscriptions,
            on_view_cache=controller.on_view_cache,
            on_health_endpoint=controller.on_health_endpoint,
        )
        return controller

    def _setup_tray(
        self,
        root: tk.Tk,
        animator: TkWindowAnimator,
        view: MainView,
        icon_path: Path | None,
    ) -> TkTrayController:
        """Create and configure the tray controller."""
        _ = animator

        def set_status(status: UiStatus) -> None:
            view.set_status(status)

        tray_controller = TkTrayController(icon_path=icon_path, set_status=set_status)
        tray_controller.bind_toggle(self._schedule_toggle)
        tray_controller.bind_quit(self._schedule_quit)
        return tray_controller

    def _toggle_visibility(self) -> None:
        """Toggle the Tk window visibility with a fade animation."""
        if not self._root or not self._animator:
            return
        is_visible = self._root.state() != "withdrawn"
        if is_visible:
            self._animator.animate_visibility(show=False)
        else:
            self._animator.center_window()
            self._animator.animate_visibility(show=True)

    def _schedule_toggle(self) -> None:
        """Schedule a toggle from the tray thread."""
        if not self._root:
            return
        self._root.after(0, self._toggle_visibility)

    def _schedule_quit(self) -> None:
        """Schedule a quit from the tray thread."""
        if not self._root:
            return
        self._root.after(0, self._handle_quit)

    def _handle_quit(self) -> None:
        """Quit the UI without stopping the daemon."""
        if self._tray_controller:
            self._tray_controller.stop()
        if self._root:
            self._root.quit()
