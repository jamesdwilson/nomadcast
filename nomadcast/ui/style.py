from __future__ import annotations

"""Shared Tkinter ttk styles for NomadCast."""

from tkinter import ttk

from nomadcast.ui.metrics import PAD, PAD_SM

FONT_BASE = ("Segoe UI", 11)
FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_SUBTITLE = ("Segoe UI", 11)

COLOR_TEXT_MUTED = "#b8c7d6"
COLOR_TEXT_SUBTLE = "#8ea3b7"
COLOR_TEXT_ERROR = "#f28072"


def init_style(style: ttk.Style) -> None:
    """Initialize shared ttk styles for the NomadCast UI."""
    style.configure("TLabel", font=FONT_BASE)
    style.configure("Title.TLabel", font=FONT_TITLE)
    style.configure("Subtitle.TLabel", font=FONT_SUBTITLE)
    style.configure("Muted.TLabel", font=FONT_BASE, foreground=COLOR_TEXT_MUTED)
    style.configure("Subtle.TLabel", font=FONT_BASE, foreground=COLOR_TEXT_SUBTLE)
    style.configure("Error.TLabel", font=FONT_BASE, foreground=COLOR_TEXT_ERROR)

    style.configure("Primary.TButton", font=FONT_BASE, padding=(PAD, PAD_SM))
