from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk


@dataclass
class FormSection:
    identity_var: tk.StringVar
    show_name_var: tk.StringVar
    location_var: tk.StringVar
    identity_input: ttk.Entry


def build_form_section(
    parent: ttk.Frame,
    *,
    identity_value: str,
    identity_hint: str,
    show_name_value: str,
    show_name_hint: str,
    show_name_suggestions: list[str],
) -> FormSection:
    identity_label = ttk.Label(parent, text="NomadNet node ID (used in links + feeds)")
    identity_label.grid(row=4, column=0, sticky="w")

    identity_var = tk.StringVar(value=identity_value)
    identity_input = ttk.Entry(parent, textvariable=identity_var)
    identity_input.grid(row=5, column=0, sticky="ew", pady=(4, 12))

    identity_hint_label = ttk.Label(parent, foreground="#8ea3b7")
    identity_hint_label.configure(text=identity_hint)
    identity_hint_label.grid(row=6, column=0, sticky="w", pady=(0, 12))

    base_show_name = show_name_value
    show_name_var = tk.StringVar(value=base_show_name)

    show_name_label = ttk.Label(parent, text="Podcast name")
    show_name_label.grid(row=7, column=0, sticky="w")

    show_name_input = ttk.Entry(parent, textvariable=show_name_var)
    show_name_input.grid(row=8, column=0, sticky="ew", pady=(4, 6))

    show_name_hint_label = ttk.Label(parent, foreground="#8ea3b7")
    show_name_hint_label.configure(text=show_name_hint)
    show_name_hint_label.grid(row=9, column=0, sticky="w", pady=(0, 8))

    suggestions_label = ttk.Label(parent, text="Name templates")
    suggestions_label.grid(row=10, column=0, sticky="w")

    suggestions_list = tk.Listbox(
        parent,
        height=4,
        width=62,
        background="#101720",
        foreground="#f5f7fa",
        highlightthickness=0,
        borderwidth=0,
    )
    for suggestion in show_name_suggestions:
        suggestions_list.insert(tk.END, suggestion)
    suggestions_list.grid(row=11, column=0, sticky="w", pady=(4, 12))

    def handle_show_name_select(event: tk.Event) -> None:
        selection = suggestions_list.curselection()
        if selection:
            show_name_var.set(suggestions_list.get(selection[0]))

    suggestions_list.bind("<<ListboxSelect>>", handle_show_name_select)

    choice_label = ttk.Label(parent, text="Where should we place the Relay Room pages?")
    choice_label.grid(row=12, column=0, sticky="w")

    location_var = tk.StringVar(value="replace_pages")
    replace_button = ttk.Radiobutton(
        parent,
        text="Replace the pages at ~/.nomadnetwork/storage/pages",
        value="replace_pages",
        variable=location_var,
    )
    replace_button.grid(row=13, column=0, sticky="w", pady=(4, 2))

    subdir_button = ttk.Radiobutton(
        parent,
        text="Create new folder at ~/.nomadnetwork/storage/pages/podcast",
        value="podcast_pages",
        variable=location_var,
    )
    subdir_button.grid(row=14, column=0, sticky="w", pady=(0, 16))

    return FormSection(
        identity_var=identity_var,
        show_name_var=show_name_var,
        location_var=location_var,
        identity_input=identity_input,
    )
