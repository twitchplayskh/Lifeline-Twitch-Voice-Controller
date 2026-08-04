"""
Small widget-building helpers.

The original code hand-built the same "label + spinbox + hint" and
"scrollable canvas with mousewheel support" patterns several times over,
with only the row numbers and variables changing. Extracting them here
removes that duplication and makes each settings section read as a short
list of what it contains, not how grid() is used.
"""

import tkinter as tk
from tkinter import ttk

from . import theme


def section(parent, title: str) -> tk.LabelFrame:
    """A titled group box in the app's panel color scheme."""
    frame = tk.LabelFrame(
        parent, text=f" {title} ", bg=theme.BG_PANEL, fg=theme.FG_ACCENT,
        font=theme.FONT_LABEL_BOLD, bd=1, relief="groove",
    )
    frame.pack(fill="x", padx=12, pady=8)
    return frame


def hint_label(parent, text: str, **grid_kwargs) -> tk.Label:
    """Small dim text used for tips/help lines under a control."""
    label = tk.Label(parent, text=text, bg=parent["bg"], fg=theme.FG_DIM,
                      font=theme.FONT_HINT, justify="left")
    if grid_kwargs:
        label.grid(**grid_kwargs)
    return label


def checkbutton(parent, text, variable, *, bold=False, fg=theme.FG_TEXT, command=None):
    """A checkbox styled to match the dark panel background."""
    return tk.Checkbutton(
        parent, text=text, variable=variable,
        bg=parent["bg"], fg=fg, selectcolor=theme.BG_INPUT,
        activebackground=parent["bg"], activeforeground=fg,
        font=theme.FONT_LABEL_BOLD if bold else theme.FONT_LABEL,
        command=command,
    )


def labeled_spinbox(parent, variable, label_text, row, *, from_, to, increment, hint=""):
    """One grid row: a right-aligned label, a spinbox, and an optional hint."""
    tk.Label(parent, text=label_text, bg=parent["bg"], fg=theme.FG_TEXT,
              font=theme.FONT_LABEL).grid(row=row, column=0, sticky="e", padx=8, pady=3)
    row_frame = ttk.Frame(parent)
    row_frame.grid(row=row, column=1, sticky="w", padx=8, pady=3)
    ttk.Spinbox(row_frame, from_=from_, to=to, increment=increment, textvariable=variable,
                width=7, format="%.2f").pack(side="left")
    if hint:
        tk.Label(row_frame, text=hint, bg=parent["bg"], fg=theme.FG_DIM,
                 font=theme.FONT_HINT).pack(side="left", padx=6)
    return row_frame


def scrollable_frame(parent) -> tk.Frame:
    """
    A vertically scrollable area, sized to `parent`'s width, that only
    captures the mouse wheel while the pointer is over it (so scrolling one
    tab doesn't hijack the wheel on another).

    Returns the inner Frame that content should be packed/gridded into.
    """
    canvas = tk.Canvas(parent, bg=theme.BG_WINDOW, highlightthickness=0)
    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    inner = tk.Frame(canvas, bg=theme.BG_WINDOW)
    inner_window = canvas.create_window((0, 0), window=inner, anchor="nw")

    def on_canvas_resized(event):
        canvas.itemconfig(inner_window, width=event.width)

    def on_inner_resized(_event):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    canvas.bind("<Configure>", on_canvas_resized)
    inner.bind("<Configure>", on_inner_resized)
    canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", on_mousewheel))
    canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

    return inner
