from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk


@dataclass
class StatusSection:
    status_var: tk.StringVar
    status_label: ttk.Label
    pending_frame: ttk.Frame
    pending_list: tk.Listbox


def build_status_section(parent: ttk.Frame) -> StatusSection:
    pending_frame = ttk.Frame(parent)
    pending_frame.grid(row=15, column=0, sticky="w", pady=(0, 12))
    pending_frame.columnconfigure(0, weight=1)
    pending_frame.grid_remove()

    pending_label = ttk.Label(pending_frame, text="Pending actions")
    pending_label.grid(row=0, column=0, sticky="w")

    pending_list = tk.Listbox(
        pending_frame,
        height=4,
        width=62,
        background="#101720",
        foreground="#f5f7fa",
        highlightthickness=0,
        borderwidth=0,
    )
    pending_list.grid(row=1, column=0, sticky="w", pady=(4, 0))

    status_var = tk.StringVar(value="Ready when you are. Let’s bring the Relay Room online.")
    status_label = ttk.Label(parent, textvariable=status_var, foreground="#b8c7d6")
    status_label.grid(row=16, column=0, sticky="w", pady=(0, 12))

    return StatusSection(
        status_var=status_var,
        status_label=status_label,
        pending_frame=pending_frame,
        pending_list=pending_list,
    )
