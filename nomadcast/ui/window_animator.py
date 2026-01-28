"""Tk window visibility helpers for the UI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TkWindowAnimator:
    """Utilities for centering and fading a Tk window."""

    root: "tk.Tk"

    def apply_tray_window_hints(self) -> None:
        """Apply best-effort window hints to hide dock/taskbar entries."""
        import platform
        import tkinter as tk

        system = platform.system()
        if system == "Windows":
            try:
                self.root.wm_attributes("-toolwindow", True)
            except tk.TclError:
                pass
        elif system == "Linux":
            # X11-only hint for utility windows; ignored on Wayland.
            try:
                self.root.wm_attributes("-type", "utility")
            except tk.TclError:
                pass
        elif system == "Darwin":
            # Hiding the Dock icon is typically controlled via app bundles;
            # this is a best-effort hint for Tk builds that support it.
            try:
                self.root.tk.call("tk::mac::ShowHide", "hide")
            except tk.TclError:
                pass

    def center_window(self) -> None:
        """Center the window on the active screen."""
        self.root.update_idletasks()
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        position_x = max((screen_width - window_width) // 2, 0)
        position_y = max((screen_height - window_height) // 2, 0)
        self.root.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")

    def animate_visibility(
        self,
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
            current_alpha = float(self.root.attributes("-alpha"))
        except (tk.TclError, ValueError):
            current_alpha = 1.0 if show else 0.0
        start_alpha = max(0.0, min(1.0, current_alpha))
        end_alpha = 1.0 if show else 0.0
        delta = (end_alpha - start_alpha) / steps
        interval = max(duration_ms // steps, 1)

        def step(index: int, alpha: float) -> None:
            try:
                self.root.attributes("-alpha", max(0.0, min(1.0, alpha)))
            except tk.TclError:
                return
            if index < steps:
                self.root.after(interval, step, index + 1, alpha + delta)
            elif not show:
                self.root.withdraw()

        if show:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        step(0, start_alpha)
