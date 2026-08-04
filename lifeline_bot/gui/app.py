"""The Tk application: composes the engines/services and the three tabs."""

import os
import queue
import tkinter as tk
from tkinter import ttk

from .. import config as config_module
from ..audio_engine import AudioEngine
from ..commands import LIFELINE_COMMANDS, LIFELINE_PHRASES, CommandMatcher
from ..controller_engine import ControllerEngine
from ..paths import app_base_dir
from ..playback_service import PlaybackService
from ..tts_engine import TTSEngine
from ..word_filter import WordFilter
from . import theme
from .commands_tab import CommandsTabMixin
from .main_tab import MainTabMixin
from .settings_tab import SettingsTabMixin

WINDOW_TITLE = "\U0001F3AE Lifeline Twitch Voice Controller"
WINDOW_SIZE = "900x680"


class App(tk.Tk, MainTabMixin, SettingsTabMixin, CommandsTabMixin):
    """
    Composes:
      - the engines (audio, TTS, controller, word filter) and the
        CommandMatcher / PlaybackService that use them,
      - the three tabs, each provided by a mixin (Main / Settings / Commands).
    """

    def __init__(self):
        super().__init__()
        self.title(WINDOW_TITLE)
        self.geometry(WINDOW_SIZE)
        self.configure(bg=theme.BG_WINDOW)
        self.resizable(True, True)

        self.cfg = config_module.load_config()
        self.bot = None

        self._init_engines_and_services()
        self._init_queues_and_counters()

        self._build_ui()
        self._apply_config()
        self._poll_queues()

    def _init_engines_and_services(self):
        self.audio = AudioEngine()
        self.controller = ControllerEngine()
        self.tts = TTSEngine()
        self.word_filter = WordFilter()
        self.command_matcher = CommandMatcher(LIFELINE_COMMANDS, LIFELINE_PHRASES)

        tts_cache_dir = os.path.join(app_base_dir(), "_tts_cache")
        self.playback = PlaybackService(
            audio_engine=self.audio,
            tts_engine=self.tts,
            controller_engine=self.controller,
            word_filter=self.word_filter,
            tts_cache_dir=tts_cache_dir,
            log_callback=lambda kind, message: self.log_queue.put((kind, message)),
            get_settings=self._current_playback_settings,
            get_blocked_trigger_phrases=self._blocked_trigger_phrases,
            on_word_played=self._increment_play_count,
        )

    def _init_queues_and_counters(self):
        self.log_queue = queue.Queue()
        self.chat_queue = queue.Queue()
        self.last_played = {}   # command -> timestamp last played, for cooldowns
        self.play_count = 0

    def _increment_play_count(self):
        self.play_count += 1

    # ── UI construction ──────────────────────────────────────────────────
    def _build_ui(self):
        self._configure_ttk_style()

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)
        self._build_main_tab(notebook)
        self._build_config_tab(notebook)
        self._build_commands_tab(notebook)

        self.status_var = tk.StringVar(value="Ready. Configure settings and connect.")
        status_bar = tk.Label(self, textvariable=self.status_var, bg=theme.BG_INPUT,
                               fg=theme.FG_SUCCESS, anchor="w", padx=10, font=theme.FONT_HINT)
        status_bar.pack(fill="x", side="bottom")

    def _configure_ttk_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook", background=theme.BG_WINDOW, borderwidth=0)
        style.configure("TNotebook.Tab", background=theme.BG_PANEL, foreground=theme.FG_TEXT,
                        padding=[12, 6], font=theme.FONT_LABEL_BOLD)
        style.map("TNotebook.Tab", background=[("selected", theme.BG_INPUT)],
                  foreground=[("selected", theme.FG_ACCENT)])
        style.configure("TFrame", background=theme.BG_WINDOW)
        style.configure("TLabel", background=theme.BG_WINDOW, foreground=theme.FG_TEXT, font=theme.FONT_LABEL)
        style.configure("TEntry", fieldbackground=theme.BG_PANEL, foreground=theme.FG_TEXT,
                        insertcolor="white", borderwidth=1)
        style.configure("TButton", background=theme.BG_INPUT, foreground=theme.FG_TEXT,
                        font=theme.FONT_LABEL_BOLD, borderwidth=0, padding=6)
        style.map("TButton", background=[("active", theme.FG_ACCENT)])
        style.configure("Green.TButton", background="#1a472a", foreground=theme.FG_SUCCESS)
        style.map("Green.TButton", background=[("active", "#2d6a4f")])
        style.configure("Red.TButton", background="#6b1a1a", foreground="#ff9999")
        style.map("Red.TButton", background=[("active", "#9b2335")])

    def on_closing(self):
        if self.bot:
            self.bot.stop()
        self.controller.destroy()
        self.playback.stop()
        self.tts.stop()
        self.destroy()
