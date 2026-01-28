from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Sequence

from nomadcast_sample.domain.types import SampleCreatorInput
from nomadcast_sample.ui.sections.actions import ActionsSection, build_actions_section
from nomadcast_sample.ui.sections.form_customer import FormSection, build_form_section
from nomadcast_sample.ui.sections.header import build_header
from nomadcast_sample.ui.sections.status import StatusSection, build_status_section


class SampleCreatorView:
    def __init__(
        self,
        root: tk.Tk,
        *,
        banner_logo: tk.PhotoImage | None,
        identity_value: str,
        identity_hint: str,
        show_name_value: str,
        show_name_hint: str,
        show_name_suggestions: list[str],
        on_install: Callable[[], None],
        on_open_pages: Callable[[], None],
        on_open_media: Callable[[], None],
        on_open_guide: Callable[[], None],
    ) -> None:
        self._root = root

        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        frame = ttk.Frame(root, padding=28)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)

        build_header(frame, banner_logo=banner_logo)
        self._form_section: FormSection = build_form_section(
            frame,
            identity_value=identity_value,
            identity_hint=identity_hint,
            show_name_value=show_name_value,
            show_name_hint=show_name_hint,
            show_name_suggestions=show_name_suggestions,
        )
        self._status_section: StatusSection = build_status_section(frame)
        self._actions_section: ActionsSection = build_actions_section(
            frame,
            on_install=on_install,
            on_open_guide=on_open_guide,
            on_open_pages=on_open_pages,
            on_open_media=on_open_media,
        )

        self._resize_window_to_content()
        self._root.bind("<Return>", lambda event: self._actions_section.install_button.invoke())

    def focus_first(self) -> None:
        self._form_section.identity_input.focus()

    def get_form_data(self) -> SampleCreatorInput:
        return SampleCreatorInput(
            identity=self._form_section.identity_var.get(),
            show_name=self._form_section.show_name_var.get(),
            location_choice=self._form_section.location_var.get(),
        )

    def set_status(self, message: str, *, is_error: bool = False) -> None:
        self._status_section.status_var.set(message)
        self._status_section.status_label.configure(
            foreground="#f28072" if is_error else "#b8c7d6"
        )

    def set_pending_actions(self, items: Sequence[str]) -> None:
        pending_list = self._status_section.pending_list
        pending_list.delete(0, tk.END)
        for action in items:
            pending_list.insert(tk.END, f"• {action}")
        self._status_section.pending_frame.grid()
        self._resize_window_to_content()

    def clear_pending_actions(self) -> None:
        pending_list = self._status_section.pending_list
        pending_list.delete(0, tk.END)
        self._status_section.pending_frame.grid_remove()
        self._resize_window_to_content()

    def _resize_window_to_content(self) -> None:
        self._root.update_idletasks()
        width = self._root.winfo_reqwidth()
        height = self._root.winfo_reqheight()
        self._root.geometry(f"{width}x{height}")
        self._center_window()

    def _center_window(self) -> None:
        self._root.update_idletasks()
        window_width = self._root.winfo_width()
        window_height = self._root.winfo_height()
        screen_width = self._root.winfo_screenwidth()
        screen_height = self._root.winfo_screenheight()
        position_x = max((screen_width - window_width) // 2, 0)
        position_y = max((screen_height - window_height) // 2, 0)
        self._root.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")
