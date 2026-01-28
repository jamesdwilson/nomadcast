"""System tray integration helpers for the Tk UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from nomadcast.ui import UiStatus


TrayCallback = Callable[[], None]


@dataclass
class TkTrayController:
    """Manage the system tray icon and its menu callbacks."""

    icon_path: Path
    set_status: Callable[[UiStatus], None]
    _toggle_callback: Optional[TrayCallback] = None
    _quit_callback: Optional[TrayCallback] = None
    _tray_icon: Optional["pystray.Icon"] = field(default=None, init=False, repr=False)

    def bind_toggle(self, callback: TrayCallback) -> None:
        """Bind the show/hide toggle callback invoked from the tray menu."""
        self._toggle_callback = callback

    def bind_quit(self, callback: TrayCallback) -> None:
        """Bind the quit callback invoked from the tray menu."""
        self._quit_callback = callback

    def start(self) -> bool:
        """Start the tray icon in a detached thread."""
        try:
            from PIL import Image
            import pystray
        except Exception as exc:
            self.set_status(UiStatus(message=f"Tray icon unavailable: {exc}", is_error=True))
            return False

        tray_image = self._load_tray_image(Image)
        self._tray_icon = pystray.Icon("nomadcast", tray_image, "NomadCast", self._build_menu(pystray))

        try:
            self._tray_icon.run_detached()
        except Exception as exc:
            self.set_status(UiStatus(message=f"Tray icon failed to start: {exc}", is_error=True))
            self._tray_icon = None
            return False
        return True

    def stop(self) -> None:
        """Stop the tray icon event loop if it is running."""
        if self._tray_icon is not None:
            self._tray_icon.stop()
            self._tray_icon = None

    def _load_tray_image(self, image_module: "Image") -> "Image.Image":
        if self.icon_path.exists():
            return image_module.open(self.icon_path)
        return image_module.new("RGBA", (64, 64), (17, 22, 30, 255))

    def _build_menu(self, pystray_module: "pystray") -> "pystray.Menu":
        return pystray_module.Menu(
            pystray_module.MenuItem("Show/Hide", self._dispatch_toggle, default=True),
            pystray_module.MenuItem("Quit (does not stop daemon)", self._dispatch_quit),
        )

    def _dispatch_toggle(self, _icon: "pystray.Icon" | None = None, _item: "pystray.MenuItem" | None = None) -> None:
        if self._toggle_callback is not None:
            self._toggle_callback()

    def _dispatch_quit(self, _icon: "pystray.Icon", _item: "pystray.MenuItem") -> None:
        if self._quit_callback is not None:
            self._quit_callback()
