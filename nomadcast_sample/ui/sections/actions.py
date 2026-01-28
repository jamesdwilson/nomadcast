from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from tkinter import ttk


@dataclass
class ActionsSection:
    install_button: ttk.Button
    guide_button: ttk.Button
    open_pages_button: ttk.Button
    open_media_button: ttk.Button


def build_actions_section(
    parent: ttk.Frame,
    *,
    on_install: Callable[[], None],
    on_open_guide: Callable[[], None],
    on_open_pages: Callable[[], None],
    on_open_media: Callable[[], None],
) -> ActionsSection:
    actions_row = ttk.Frame(parent)
    actions_row.grid(row=17, column=0, sticky="w", pady=(4, 16))

    install_button = ttk.Button(actions_row, text="BEGIN TRANSMISSION", command=on_install)
    install_button.configure(default="active")
    install_button.grid(row=0, column=0, sticky="w")

    guide_button = ttk.Button(actions_row, text="NomadNet page hosting guide", command=on_open_guide)
    guide_button.grid(row=0, column=1, sticky="w", padx=(12, 0))

    links_row = ttk.Frame(parent)
    links_row.grid(row=18, column=0, sticky="w")

    open_pages_button = ttk.Button(links_row, text="📁 Open Pages root", command=on_open_pages)
    open_pages_button.grid(row=0, column=0, sticky="w")

    open_media_button = ttk.Button(links_row, text="📁 Open Media root", command=on_open_media)
    open_media_button.grid(row=0, column=1, sticky="w", padx=(12, 0))

    return ActionsSection(
        install_button=install_button,
        guide_button=guide_button,
        open_pages_button=open_pages_button,
        open_media_button=open_media_button,
    )
