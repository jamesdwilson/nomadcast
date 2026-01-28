from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def build_header(parent: ttk.Frame, *, banner_logo: tk.PhotoImage | None) -> None:
    header_frame = ttk.Frame(parent)
    header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
    header_frame.columnconfigure(0, weight=1)

    if banner_logo is not None:
        logo_label = tk.Label(
            header_frame,
            image=banner_logo,
            background="#11161e",
            padx=8,
            pady=8,
        )
        logo_label.grid(row=0, column=0, sticky="n", pady=(0, 8))

    banner_label = tk.Label(
        header_frame,
        text="NOMADCAST SAMPLE CREATOR",
        font=("Segoe UI", 16, "bold"),
        background="#1b2230",
        foreground="#f5f7fa",
        padx=12,
        pady=6,
    )
    banner_label.grid(row=1, column=0, sticky="ew")

    header = ttk.Label(parent, text="FIRST TRANSMISSION STARTS HERE", font=("Segoe UI", 18, "bold"))
    header.grid(row=1, column=0, sticky="n", pady=(12, 10))

    subhead = ttk.Label(parent, text="Radio YOU is on the air.", font=("Segoe UI", 12))
    subhead.grid(row=2, column=0, sticky="n", pady=(0, 10))

    subtitle = ttk.Label(
        parent,
        text=(
            "We’ll carve out a real podcast home in your Nomad Network storage. "
            "It’s yours — decentralized from the first click."
        ),
        wraplength=640,
        justify="center",
    )
    subtitle.grid(row=3, column=0, sticky="n", pady=(0, 16))
