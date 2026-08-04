"""Commands tab: read-only vocabulary reference + custom command editor."""

import tkinter as tk
from tkinter import scrolledtext, ttk

from ..commands import LIFELINE_COMMANDS, LIFELINE_PHRASES, CommandMatcher
from . import theme, widgets


class CommandsTabMixin:
    """Provides `_build_commands_tab` and the custom-command handling."""

    def _build_commands_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="  \U0001F4CB Commands  ")
        inner = widgets.scrollable_frame(frame)

        self._build_word_reference(inner)
        self._build_phrase_reference(inner)
        self._build_custom_commands_editor(inner)

        widgets.hint_label(
            inner,
            "\u2139  Place audio files named exactly after the command "
            "(e.g. yes.wav, go.wav) in your audio folder.",
        ).pack(anchor="w", padx=12, pady=(0, 10))

    def _build_word_reference(self, inner):
        tk.Label(inner, text="Single-word commands:", bg=theme.BG_WINDOW, fg=theme.FG_MUTED,
                 font=theme.FONT_HINT).pack(anchor="w", padx=12, pady=(8, 2))

        grid = tk.Frame(inner, bg=theme.BG_LOG, bd=1, relief="sunken")
        grid.pack(fill="x", padx=12, pady=4)
        self._fill_word_grid(grid, sorted(LIFELINE_COMMANDS), columns=8, fg=theme.FG_LINK, width=12)

    def _build_phrase_reference(self, inner):
        tk.Label(
            inner, text=f"Official multi-word phrases ({len(LIFELINE_PHRASES)})"
            "  \u2014 say the full phrase in chat to trigger:",
            bg=theme.BG_WINDOW, fg=theme.FG_MUTED, font=theme.FONT_HINT,
        ).pack(anchor="w", padx=12, pady=(8, 2))

        grid = tk.Frame(inner, bg=theme.BG_LOG, bd=1, relief="sunken")
        grid.pack(fill="x", padx=12, pady=4)
        self._fill_word_grid(grid, sorted(LIFELINE_PHRASES), columns=3, fg=theme.FG_ACCENT_ALT, width=36)

    @staticmethod
    def _fill_word_grid(grid, items, *, columns, fg, width):
        for index, text in enumerate(items):
            tk.Label(grid, text=text, bg=theme.BG_LOG, fg=fg, font=theme.FONT_MONO,
                     width=width, anchor="w").grid(row=index // columns, column=index % columns,
                                                    padx=2, pady=1, sticky="w")

    def _build_custom_commands_editor(self, inner):
        sec = widgets.section(inner, "Custom Commands")

        tk.Label(sec, text="Add extra trigger words or phrases (one per line):",
                 bg=theme.BG_PANEL, fg=theme.FG_TEXT, font=theme.FONT_HINT).pack(anchor="w", padx=6, pady=4)

        self.custom_text = scrolledtext.ScrolledText(
            sec, bg=theme.BG_LOG, fg=theme.FG_SUCCESS, font=theme.FONT_MONO_LARGE,
            height=6, borderwidth=0, relief="flat",
        )
        self.custom_text.pack(fill="both", expand=True, padx=6, pady=4)

        ttk.Button(sec, text="\u2705 Apply Custom Commands", command=self._apply_custom_commands).pack(padx=6, pady=4)

    def _apply_custom_commands(self):
        """
        Parse the custom-commands textbox and rebuild `self.command_matcher`
        with the built-in vocabulary plus whatever the user added
        (single words go to the word set, anything with a space is a phrase).
        """
        lines = [
            line.strip().lower()
            for line in self.custom_text.get("1.0", "end").splitlines()
            if line.strip()
        ]
        custom_words = {line for line in lines if " " not in line}
        custom_phrases = {line for line in lines if " " in line}

        active_commands = LIFELINE_COMMANDS | custom_words
        active_phrases = LIFELINE_PHRASES | custom_phrases
        self.command_matcher = CommandMatcher(active_commands, active_phrases)

        self._set_status(
            f"Commands active: {len(active_commands)} words, {len(active_phrases)} phrases"
        )
