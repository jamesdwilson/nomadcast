from __future__ import annotations

"""Tkinter UI view for the NomadCast application."""

import tkinter as tk
from tkinter import ttk
from typing import Callable

from nomadcast.ui.metrics import (
    BUTTON_SPACING_X,
    BUTTON_ROW_PAD_Y,
    COMING_SOON_PAD_Y,
    ENTRY_PAD_Y,
    FUTURE_ROW_PAD_Y,
    HEADER_PAD_Y,
    STATUS_PAD_Y,
    SUBTITLE_PAD_Y,
    SUBTITLE_WRAP,
    WINDOW_PADDING,
)
from nomadcast.ui.service import UiStatus


class MainView(ttk.Frame):
    """Primary Tkinter view for NomadCast."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        on_add: Callable[[], None],
        on_manage_daemon: Callable[[], None],
        on_edit_subscriptions: Callable[[], None],
        on_view_cache: Callable[[], None],
        on_health_endpoint: Callable[[], None],
        initial_locator: str = "",
    ) -> None:
        super().__init__(master, padding=WINDOW_PADDING)
        self._on_add = on_add
        self._on_manage_daemon = on_manage_daemon
        self._on_edit_subscriptions = on_edit_subscriptions
        self._on_view_cache = on_view_cache
        self._on_health_endpoint = on_health_endpoint
        self._locator_var = tk.StringVar(value=initial_locator)
        self._status_var = tk.StringVar(value="Ready to add a show.")
        self._locator_input: ttk.Entry | None = None
        self._add_button: ttk.Button | None = None
        self._daemon_button: ttk.Button | None = None
        self._subscriptions_button: ttk.Button | None = None
        self._cache_button: ttk.Button | None = None
        self._health_button: ttk.Button | None = None
        self._interactive_widgets: list[ttk.Widget] = []
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)

        header = ttk.Label(self, text="NomadCast v0", style="Title.TLabel")
        header.grid(row=0, column=0, sticky="w", pady=HEADER_PAD_Y)

        subtitle = ttk.Label(
            self,
            text=(
                "Paste a NomadCast locator to subscribe. "
                "NomadCast will add the feed to your local daemon and open "
                "your podcast app once the first episode finishes downloading."
            ),
            wraplength=SUBTITLE_WRAP,
            style="Subtitle.TLabel",
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=SUBTITLE_PAD_Y)

        locator_input = ttk.Entry(self, textvariable=self._locator_var)
        locator_input.grid(row=2, column=0, sticky="ew", pady=ENTRY_PAD_Y)
        self._locator_input = locator_input

        button_row = ttk.Frame(self)
        button_row.grid(row=3, column=0, sticky="ew", pady=BUTTON_ROW_PAD_Y)
        button_row.columnconfigure(0, weight=1)

        add_button = ttk.Button(
            button_row,
            text="Add subscription",
            command=self._on_add,
            style="Primary.TButton",
        )
        add_button.configure(default="active")
        add_button.grid(row=0, column=0, sticky="w")
        self._add_button = add_button

        daemon_button = ttk.Button(button_row, text="Manage daemon", command=self._on_manage_daemon)
        daemon_button.state(["disabled"])
        daemon_button.grid(row=0, column=1, sticky="w", padx=BUTTON_SPACING_X)
        self._daemon_button = daemon_button

        subscriptions_button = ttk.Button(
            button_row, text="Edit subscriptions", command=self._on_edit_subscriptions
        )
        subscriptions_button.state(["disabled"])
        subscriptions_button.grid(row=0, column=2, sticky="w", padx=BUTTON_SPACING_X)
        self._subscriptions_button = subscriptions_button

        cache_button = ttk.Button(button_row, text="View cache", command=self._on_view_cache)
        cache_button.state(["disabled"])
        cache_button.grid(row=0, column=3, sticky="w", padx=BUTTON_SPACING_X)
        self._cache_button = cache_button

        status_label = ttk.Label(self, textvariable=self._status_var, style="Muted.TLabel")
        status_label.grid(row=4, column=0, sticky="w", pady=STATUS_PAD_Y)
        self._status_label = status_label

        future_row = ttk.Frame(self)
        future_row.grid(row=5, column=0, sticky="ew", pady=FUTURE_ROW_PAD_Y)

        health_button = ttk.Button(
            future_row, text="Health endpoint", command=self._on_health_endpoint
        )
        health_button.state(["disabled"])
        health_button.grid(row=0, column=0, sticky="w")
        self._health_button = health_button

        coming_soon = ttk.Label(
            self,
            text="More features are under development—thanks for trying NomadCast!",
            style="Subtle.TLabel",
        )
        coming_soon.grid(row=6, column=0, sticky="w", pady=COMING_SOON_PAD_Y)

        self._interactive_widgets = [locator_input, add_button]

        if self._locator_input is not None:
            self._locator_input.bind("<Return>", lambda event: self._on_add())

    def set_callbacks(
        self,
        *, 
        on_add: Callable[[], None],
        on_manage_daemon: Callable[[], None],
        on_edit_subscriptions: Callable[[], None],
        on_view_cache: Callable[[], None],
        on_health_endpoint: Callable[[], None],
    ) -> None:
        """Update callback handlers for interactive widgets."""
        self._on_add = on_add
        self._on_manage_daemon = on_manage_daemon
        self._on_edit_subscriptions = on_edit_subscriptions
        self._on_view_cache = on_view_cache
        self._on_health_endpoint = on_health_endpoint
        if self._add_button is not None:
            self._add_button.configure(command=self._on_add)
        if self._daemon_button is not None:
            self._daemon_button.configure(command=self._on_manage_daemon)
        if self._subscriptions_button is not None:
            self._subscriptions_button.configure(command=self._on_edit_subscriptions)
        if self._cache_button is not None:
            self._cache_button.configure(command=self._on_view_cache)
        if self._health_button is not None:
            self._health_button.configure(command=self._on_health_endpoint)

    def get_locator(self) -> str:
        """Return the locator string from the entry widget."""
        return self._locator_var.get()

    def set_status(self, status: UiStatus) -> None:
        """Update the status label using the provided UiStatus."""
        self._status_var.set(status.message)
        self._status_label.configure(style="Error.TLabel" if status.is_error else "Muted.TLabel")

    def set_busy(self, is_busy: bool) -> None:
        """Enable or disable interactive widgets while busy."""
        state = "disabled" if is_busy else "!disabled"
        for widget in self._interactive_widgets:
            widget.state([state])

    def focus_first(self) -> None:
        """Focus the locator entry widget."""
        if self._locator_input is not None:
            self._locator_input.focus()
