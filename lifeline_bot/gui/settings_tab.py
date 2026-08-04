"""
Settings tab: Twitch credentials, audio device/folder, controller timing,
chat-triggered buttons, and TTS options — plus the config load/save glue and
the `PlaybackSettings` snapshot the playback worker reads each sentence.
"""

import threading
import time as time_module
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .. import config as config_module
from ..playback_service import PlaybackSettings
from ..tts_engine import HAS_TTS
from . import theme, widgets

# (button_label, ps2_function, default_chat_word, default_enabled)
CHAT_BUTTON_DEFINITIONS = [
    ("Square \u25a1",   "Confirm",             "confirm",  False),
    ("Cross \u00d7",     "Cancel",              "cancel",   False),
    ("Triangle \u25b3",  "Analysis/Weak spots", "analysis", False),
    ("L1",               "Open map",            "map",      False),
    ("R1",                "Item list",           "items",    False),
    ("L2",                "Skip event",          "skip",     False),
    ("Start",             "Pause",               "pause",    False),
    ("Select",            "Skip (menu)",         "select",   False),
]


class SettingsTabMixin:
    """Provides `_build_config_tab` and all its supporting handlers."""

    def _build_config_tab(self, notebook):
        outer = ttk.Frame(notebook)
        notebook.add(outer, text="  \u2699\ufe0f Settings  ")
        frame = widgets.scrollable_frame(outer)

        self._build_twitch_section(frame)
        self._build_audio_section(frame)
        self._build_playback_section(frame)
        self._build_controller_section(frame)
        self._build_tts_section(frame)

        ttk.Button(frame, text="\U0001F4BE Save Settings", command=self._save_config).pack(pady=10)
        self._refresh_devices()

    # ── Twitch ───────────────────────────────────────────────────────────
    def _build_twitch_section(self, frame):
        sec = widgets.section(frame, "Twitch IRC")

        tk.Label(sec, text="Channel name:", bg=theme.BG_PANEL, fg=theme.FG_TEXT,
                 font=theme.FONT_LABEL).grid(row=0, column=0, sticky="e", padx=12, pady=5)
        self.channel_var = tk.StringVar()
        ttk.Entry(sec, textvariable=self.channel_var, width=32).grid(row=0, column=1, sticky="w", padx=12, pady=5)

        tk.Label(sec, text="OAuth token:", bg=theme.BG_PANEL, fg=theme.FG_TEXT,
                 font=theme.FONT_LABEL).grid(row=1, column=0, sticky="e", padx=12, pady=5)
        self.oauth_var = tk.StringVar()
        ttk.Entry(sec, textvariable=self.oauth_var, width=40, show="*").grid(
            row=1, column=1, sticky="w", padx=12, pady=5)
        widgets.hint_label(sec, "Get token: https://twitchapps.com/tmi/",
                            row=2, column=1, sticky="w", padx=12)

    # ── Audio ────────────────────────────────────────────────────────────
    def _build_audio_section(self, frame):
        sec = widgets.section(frame, "Audio")

        tk.Label(sec, text="Audio files folder:", bg=theme.BG_PANEL, fg=theme.FG_TEXT,
                 font=theme.FONT_LABEL).grid(row=0, column=0, sticky="e", padx=12, pady=5)
        self.folder_var = tk.StringVar()
        folder_frame = ttk.Frame(sec)
        folder_frame.grid(row=0, column=1, sticky="w", padx=12, pady=5)
        ttk.Entry(folder_frame, textvariable=self.folder_var, width=32).pack(side="left")
        ttk.Button(folder_frame, text="Browse\u2026", command=self._browse_folder).pack(side="left", padx=4)

        tk.Label(sec, text="Output device:", bg=theme.BG_PANEL, fg=theme.FG_TEXT,
                 font=theme.FONT_LABEL).grid(row=1, column=0, sticky="e", padx=12, pady=5)
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(sec, textvariable=self.device_var, width=38, state="readonly")
        self.device_combo.grid(row=1, column=1, sticky="w", padx=12, pady=5)
        ttk.Button(sec, text="\u21bb Refresh devices", command=self._refresh_devices).grid(
            row=2, column=1, sticky="w", padx=12, pady=2)

        widgets.hint_label(
            sec,
            "\U0001F4A1 Tip: Install VB-Cable or VoiceMeeter and select it as output device.\n"
            "   Then set the same virtual device as your mic input in the PS2 emulator / capture card.",
            row=3, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 6),
        )

    # ── Playback ─────────────────────────────────────────────────────────
    def _build_playback_section(self, frame):
        sec = widgets.section(frame, "Playback")

        tk.Label(sec, text="Command cooldown (s):", bg=theme.BG_PANEL, fg=theme.FG_TEXT,
                 font=theme.FONT_LABEL).grid(row=0, column=0, sticky="e", padx=12, pady=5)
        self.cooldown_var = tk.DoubleVar(value=1.5)
        ttk.Spinbox(sec, from_=0, to=30, increment=0.5, textvariable=self.cooldown_var,
                    width=8).grid(row=0, column=1, sticky="w", padx=12, pady=5)

        tk.Label(sec, text="Volume:", bg=theme.BG_PANEL, fg=theme.FG_TEXT,
                 font=theme.FONT_LABEL).grid(row=1, column=0, sticky="e", padx=12, pady=5)
        self.volume_var = tk.DoubleVar(value=1.0)
        volume_frame = ttk.Frame(sec)
        volume_frame.grid(row=1, column=1, sticky="w", padx=12, pady=5)
        tk.Scale(volume_frame, from_=0.0, to=2.0, resolution=0.1, orient="horizontal",
                 variable=self.volume_var, bg=theme.BG_PANEL, fg=theme.FG_TEXT,
                 troughcolor=theme.BG_INPUT, highlightthickness=0, length=160).pack(side="left")
        tk.Label(volume_frame, textvariable=self.volume_var, bg=theme.BG_PANEL, fg=theme.FG_ACCENT,
                 font=theme.FONT_MONO_LARGE).pack(side="left", padx=6)

    # ── Controller ───────────────────────────────────────────────────────
    def _build_controller_section(self, frame):
        sec = widgets.section(frame, "Virtual Controller")

        self.ctrl_enabled_var = tk.BooleanVar(value=False)
        widgets.checkbutton(sec, "Enable virtual controller", self.ctrl_enabled_var,
                             command=self._on_ctrl_toggle).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=12, pady=6)

        self.ctrl_type_var = tk.StringVar(value="DS4")
        tk.Label(sec, text="Controller type:", bg=theme.BG_PANEL, fg=theme.FG_TEXT,
                 font=theme.FONT_LABEL).grid(row=1, column=0, sticky="e", padx=12, pady=4)
        type_frame = ttk.Frame(sec)
        type_frame.grid(row=1, column=1, columnspan=2, sticky="w", padx=12)
        for label, value in (("DS4 (PlayStation)", "DS4"), ("Xbox 360", "X360")):
            tk.Radiobutton(type_frame, text=label, variable=self.ctrl_type_var, value=value,
                           bg=theme.BG_PANEL, fg=theme.FG_TEXT, selectcolor=theme.BG_INPUT,
                           activebackground=theme.BG_PANEL, font=theme.FONT_LABEL).pack(side="left", padx=4)

        tk.Label(sec, text="Mic input button:  Circle \u25cb  (fixed \u2014 this is how Lifeline works)",
                 bg=theme.BG_PANEL, fg=theme.FG_LINK, font=theme.FONT_LABEL_BOLD).grid(
            row=2, column=0, columnspan=3, sticky="w", padx=12, pady=(6, 2))
        widgets.hint_label(sec, "Circle is held for the duration of every voice command automatically.",
                            row=3, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 6))

        self._build_voice_timing_subsection(sec)
        self._build_chat_button_subsection(sec)

        self.ctrl_status_lbl = tk.Label(sec, text="Status: not initialised",
                                         bg=theme.BG_PANEL, fg=theme.FG_MUTED, font=theme.FONT_LABEL)
        self.ctrl_status_lbl.grid(row=6, column=0, columnspan=3, sticky="w", padx=12, pady=(4, 2))

        test_frame = ttk.Frame(sec)
        test_frame.grid(row=7, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 4))
        ttk.Button(test_frame, text="Test Circle timing", command=self._test_circle).pack(side="left", padx=(0, 6))
        ttk.Button(test_frame, text="Reset to defaults", command=self._reset_ctrl_timing).pack(side="left")

        widgets.hint_label(
            sec,
            "Requires: pip install vgamepad  +  ViGEmBus driver "
            "(https://github.com/nefarius/ViGEmBus/releases)\n"
            "In PCSX2: assign the virtual controller to Player 1 in Settings > Controllers.",
            row=8, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 6),
        )

    def _build_voice_timing_subsection(self, parent):
        timing = tk.LabelFrame(parent, text=" Voice Timing ", bg=theme.BG_PANEL, fg=theme.FG_MUTED,
                                font=theme.FONT_HINT, bd=1, relief="groove")
        timing.grid(row=4, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 6))

        self.ctrl_full_hold_var = tk.BooleanVar(value=True)
        widgets.checkbutton(
            timing, "Hold Circle for full audio duration  (recommended for long words)",
            self.ctrl_full_hold_var, bold=True, fg=theme.FG_WARNING,
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=4)

        widgets.hint_label(
            timing, "[PRESS Circle]  \u2192  pause  \u2192  [AUDIO plays fully]  \u2192  [RELEASE]  \u2190 recommended",
            row=1, column=0, columnspan=3, sticky="w", padx=20, pady=(0, 4),
        )

        self.ctrl_pre_delay_var = tk.DoubleVar(value=0.0)
        widgets.labeled_spinbox(timing, self.ctrl_pre_delay_var, "1. Delay before press (s):", 2,
                                 from_=0.0, to=5.0, increment=0.05,
                                 hint="Extra wait before pressing  (usually 0.00)")

        self.ctrl_hold_before_var = tk.DoubleVar(value=0.50)
        widgets.labeled_spinbox(timing, self.ctrl_hold_before_var, "2. Pause after press (s):", 3,
                                 from_=0.0, to=5.0, increment=0.05,
                                 hint="Hold before speaking  (recommended: 0.50)")

        self.ctrl_post_hold_var = tk.DoubleVar(value=0.0)
        widgets.labeled_spinbox(timing, self.ctrl_post_hold_var, "3. Hold after audio (s):", 4,
                                 from_=0.0, to=5.0, increment=0.05,
                                 hint="Keep held after speaking ends  (usually 0.00)")

        self.ctrl_release_delay_var = tk.DoubleVar(value=0.0)
        widgets.labeled_spinbox(timing, self.ctrl_release_delay_var, "4. Pause after release (s):", 5,
                                 from_=0.0, to=5.0, increment=0.05,
                                 hint="Dead-time before next command  (usually 0.00)")

        self.ctrl_timeline_var = tk.StringVar()
        tk.Label(timing, textvariable=self.ctrl_timeline_var, bg=theme.BG_PANEL, fg=theme.FG_LINK,
                 font=theme.FONT_HINT).grid(row=6, column=0, columnspan=3, sticky="w", padx=10, pady=(2, 4))

        timing_vars = (self.ctrl_pre_delay_var, self.ctrl_hold_before_var,
                       self.ctrl_post_hold_var, self.ctrl_release_delay_var, self.ctrl_full_hold_var)
        for var in timing_vars:
            var.trace_add("write", self._update_ctrl_timeline_preview)
        self._update_ctrl_timeline_preview()

    def _update_ctrl_timeline_preview(self, *_trace_args):
        pre = self.ctrl_pre_delay_var.get()
        hold_before = self.ctrl_hold_before_var.get()
        hold_after = self.ctrl_post_hold_var.get()
        release_delay = self.ctrl_release_delay_var.get()
        audio_part = "[AUDIO...full length]" if self.ctrl_full_hold_var.get() else "[AUDIO starts]"

        steps = []
        if pre > 0:
            steps.append(f"wait {pre:.2f}s")
        steps.append("[PRESS Circle]")
        if hold_before > 0:
            steps.append(f"pause {hold_before:.2f}s")
        steps.append(audio_part)
        if hold_after > 0:
            steps.append(f"hold {hold_after:.2f}s")
        steps.append("[RELEASE Circle]")
        if release_delay > 0:
            steps.append(f"pause {release_delay:.2f}s")

        self.ctrl_timeline_var.set("  \u2192  ".join(steps))

    def _build_chat_button_subsection(self, parent):
        chat_frame = tk.LabelFrame(parent, text=" Chat-Triggered Button Commands ",
                                    bg=theme.BG_PANEL, fg=theme.FG_MUTED, font=theme.FONT_HINT,
                                    bd=1, relief="groove")
        chat_frame.grid(row=5, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 6))

        widgets.hint_label(
            chat_frame, "When someone types a trigger word in chat, the mapped button is pressed and released.",
            row=0, column=0, columnspan=4, sticky="w", padx=8, pady=(4, 6),
        )

        headers = ("Button", "Function", "Chat trigger word", "On")
        widths = (12, 18, 18, None)
        for column, (header_text, width) in enumerate(zip(headers, widths)):
            kwargs = {"width": width} if width else {}
            tk.Label(chat_frame, text=header_text, bg=theme.BG_PANEL, fg=theme.FG_MUTED,
                     font=theme.FONT_HINT + ("bold",), **kwargs).grid(row=1, column=column, padx=4, sticky="w")

        self._chat_btn_enabled = {}
        self._chat_btn_words = {}
        for row_offset, (button_label, function, default_word, default_on) in enumerate(CHAT_BUTTON_DEFINITIONS):
            self._build_chat_button_row(chat_frame, row_offset + 2, button_label, function, default_word, default_on)

        widgets.hint_label(
            chat_frame, "Trigger words are in addition to voice commands and do not hold Circle.",
            row=len(CHAT_BUTTON_DEFINITIONS) + 2, column=0, columnspan=4, sticky="w", padx=8, pady=(4, 6),
        )

    def _build_chat_button_row(self, parent, row, button_label, function, default_word, default_on):
        button_key = button_label.split()[0]  # "Square", "Cross", etc.

        enabled_var = tk.BooleanVar(value=default_on)
        word_var = tk.StringVar(value=default_word)
        self._chat_btn_enabled[button_key] = enabled_var
        self._chat_btn_words[button_key] = word_var

        tk.Label(parent, text=button_label, bg=theme.BG_PANEL, fg=theme.FG_ACCENT_ALT,
                 font=theme.FONT_MONO, width=12, anchor="w").grid(row=row, column=0, padx=8, sticky="w")
        tk.Label(parent, text=function, bg=theme.BG_PANEL, fg=theme.FG_MUTED,
                 font=theme.FONT_HINT, width=18, anchor="w").grid(row=row, column=1, padx=4, sticky="w")
        ttk.Entry(parent, textvariable=word_var, width=16).grid(row=row, column=2, padx=4, pady=2, sticky="w")
        tk.Checkbutton(parent, variable=enabled_var, bg=theme.BG_PANEL,
                       selectcolor=theme.BG_INPUT, activebackground=theme.BG_PANEL).grid(row=row, column=3, padx=4)

    def _on_ctrl_toggle(self):
        if not self.ctrl_enabled_var.get():
            self.controller.destroy()
            self.ctrl_status_lbl.configure(text="Status: disabled", fg=theme.FG_MUTED)
            return

        prefer_ds4 = self.ctrl_type_var.get() == "DS4"
        success, message = self.controller.init(prefer_ds4=prefer_ds4)
        self.ctrl_status_lbl.configure(
            text=f"Status: {message}", fg=theme.FG_SUCCESS if success else theme.FG_ERROR
        )
        if not success:
            self.ctrl_enabled_var.set(False)

    def _test_circle(self):
        if not self.controller.ready:
            messagebox.showwarning("Not ready", "Enable the virtual controller first.")
            return

        def run_test():
            pre = self.ctrl_pre_delay_var.get()
            hold_before = self.ctrl_hold_before_var.get()
            hold_after = self.ctrl_post_hold_var.get()
            release_delay = self.ctrl_release_delay_var.get()
            self.log_queue.put(("command",
                f"Test: pre={pre:.2f}s hb={hold_before:.2f}s ha={hold_after:.2f}s rd={release_delay:.2f}s"))
            if pre > 0:
                time_module.sleep(pre)
            self.controller.press_button()
            self.log_queue.put(("command", "Test: \u25cf Circle HELD"))
            if hold_before > 0:
                time_module.sleep(hold_before)
            self.log_queue.put(("command", "Test: [audio would play here]"))
            time_module.sleep(0.4)  # simulate audio duration
            if hold_after > 0:
                time_module.sleep(hold_after)
            self.controller.release_button()
            self.log_queue.put(("command", "Test: \u25cb Circle released"))
            if release_delay > 0:
                time_module.sleep(release_delay)
            self.log_queue.put(("command", "Test: done"))

        threading.Thread(target=run_test, daemon=True).start()

    def _reset_ctrl_timing(self):
        """Reset to the community-recommended Lifeline sequence."""
        self.ctrl_pre_delay_var.set(0.0)
        self.ctrl_hold_before_var.set(0.50)  # the half-second pause
        self.ctrl_post_hold_var.set(0.0)
        self.ctrl_release_delay_var.set(0.0)
        self.ctrl_full_hold_var.set(True)

    # ── TTS ──────────────────────────────────────────────────────────────
    def _build_tts_section(self, frame):
        sec = widgets.section(frame, "Text-to-Speech (TTS)")

        self.tts_enabled_var = tk.BooleanVar(value=False)
        widgets.checkbutton(sec, "Enable TTS  (synthesise words that have no audio file)",
                             self.tts_enabled_var).grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=6)

        self.tts_always_var = tk.BooleanVar(value=False)
        widgets.checkbutton(sec, "Always use TTS  (ignore audio files, synthesise everything)",
                             self.tts_always_var).grid(row=1, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 6))

        self.tts_filter_var = tk.BooleanVar(value=True)
        widgets.checkbutton(sec, "Filter hateful / explicit words  (blocks word from being spoken)",
                             self.tts_filter_var, bold=True, fg=theme.FG_WARNING).grid(
            row=2, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 6))

        tk.Label(sec, text="TTS voice:", bg=theme.BG_PANEL, fg=theme.FG_TEXT,
                 font=theme.FONT_LABEL).grid(row=3, column=0, sticky="e", padx=12, pady=4)
        self.tts_voice_var = tk.StringVar(value="Default")
        self.tts_voice_combo = ttk.Combobox(sec, textvariable=self.tts_voice_var, width=36, state="readonly")
        self.tts_voice_combo.grid(row=3, column=1, sticky="w", padx=8, pady=4)
        ttk.Button(sec, text="\u21bb", width=3, command=self._refresh_tts_voices).grid(row=3, column=2, padx=4)

        self._build_tts_rate_row(sec)
        self._build_tts_gap_row(sec)

        self.tts_preview_var = tk.StringVar()
        tk.Label(sec, textvariable=self.tts_preview_var, bg=theme.BG_PANEL, fg=theme.FG_LINK,
                 font=theme.FONT_HINT).grid(row=7, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 4))
        for var in (self.tts_rate_var, self.tts_gap_var):
            var.trace_add("write", self._update_tts_preview)
        self._update_tts_preview()

        button_frame = ttk.Frame(sec)
        button_frame.grid(row=8, column=0, columnspan=3, sticky="w", padx=12, pady=(2, 6))
        ttk.Button(button_frame, text="Test TTS", command=self._test_tts).pack(side="left", padx=(0, 6))
        ttk.Button(button_frame, text="Reset TTS defaults", command=self._reset_tts_defaults).pack(side="left")

        widgets.hint_label(
            sec, "Requires: pip install pyttsx3  |  Filter: pip install better-profanity",
            row=9, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 6),
        )

    def _build_tts_rate_row(self, sec):
        tk.Label(sec, text="Speech rate (wpm):", bg=theme.BG_PANEL, fg=theme.FG_TEXT,
                 font=theme.FONT_LABEL).grid(row=4, column=0, sticky="e", padx=12, pady=4)
        self.tts_rate_var = tk.IntVar(value=150)
        rate_frame = ttk.Frame(sec)
        rate_frame.grid(row=4, column=1, columnspan=2, sticky="w", padx=8, pady=4)
        tk.Scale(rate_frame, from_=50, to=400, resolution=5, orient="horizontal",
                 variable=self.tts_rate_var, length=180, bg=theme.BG_PANEL, fg=theme.FG_TEXT,
                 troughcolor=theme.BG_INPUT, highlightthickness=0).pack(side="left")
        tk.Label(rate_frame, textvariable=self.tts_rate_var, width=4, bg=theme.BG_PANEL,
                 fg=theme.FG_ACCENT, font=theme.FONT_MONO_LARGE).pack(side="left", padx=4)
        tk.Label(rate_frame, text="wpm", bg=theme.BG_PANEL, fg=theme.FG_DIM,
                 font=theme.FONT_HINT).pack(side="left")

    def _build_tts_gap_row(self, sec):
        tk.Label(sec, text="Gap between words (s):", bg=theme.BG_PANEL, fg=theme.FG_TEXT,
                 font=theme.FONT_LABEL).grid(row=5, column=0, sticky="e", padx=12, pady=4)
        self.tts_gap_var = tk.DoubleVar(value=0.0)
        gap_frame = ttk.Frame(sec)
        gap_frame.grid(row=5, column=1, columnspan=2, sticky="w", padx=8, pady=4)
        tk.Scale(gap_frame, from_=-1.0, to=2.0, resolution=0.05, orient="horizontal",
                 variable=self.tts_gap_var, length=220, bg=theme.BG_PANEL, fg=theme.FG_TEXT,
                 troughcolor=theme.BG_INPUT, highlightthickness=0).pack(side="left")
        tk.Label(gap_frame, textvariable=self.tts_gap_var, width=4, bg=theme.BG_PANEL,
                 fg=theme.FG_ACCENT, font=theme.FONT_MONO_LARGE).pack(side="left", padx=4)
        tk.Label(gap_frame, text="s", bg=theme.BG_PANEL, fg=theme.FG_DIM, font=theme.FONT_HINT).pack(side="left")
        widgets.hint_label(sec, "Positive = pause between words  |  Negative = trim trailing silence",
                            row=6, column=1, columnspan=2, sticky="w", padx=8, pady=(0, 4))

    def _update_tts_preview(self, *_trace_args):
        rate = self.tts_rate_var.get()
        gap = self.tts_gap_var.get()
        speed = "slow" if rate < 100 else "fast" if rate > 250 else "normal"
        if gap > 0:
            gap_description = f"+{gap:.2f}s pause added"
        elif gap < 0:
            gap_description = f"{gap:.2f}s trimmed from end of each word"
        else:
            gap_description = "no gap (back-to-back)"
        self.tts_preview_var.set(f"Rate: {rate} wpm ({speed})   |   Gap: {gap_description}")

    def _refresh_tts_voices(self):
        self.tts._voices_cache = None  # force a fresh query from the system
        voices = self.tts.get_voices()
        values = ["Default"] + [name for _voice_id, name in voices]
        self.tts_voice_combo["values"] = values
        if not self.tts_voice_var.get():
            self.tts_voice_combo.current(0)

    def _resolve_tts_voice(self):
        """Cache the selected voice ID so synthesis has zero lookup cost."""
        chosen_name = self.tts_voice_var.get()
        if not chosen_name or chosen_name == "Default":
            self.tts.voice_id = None
            return
        for voice_id, voice_name in self.tts.get_voices():
            if voice_name == chosen_name:
                self.tts.voice_id = voice_id
                return
        self.tts.voice_id = None

    def _reset_tts_defaults(self):
        self.tts_rate_var.set(150)
        self.tts_gap_var.set(0.0)

    def _test_tts(self):
        if not HAS_TTS:
            messagebox.showerror("TTS not available", "Run: pip install pyttsx3")
            return
        word = "go"
        if self.tts_filter_var.get() and not self.word_filter.is_clean(word):
            messagebox.showinfo("Filtered", f"'{word}' would be blocked by the word filter.")
            return
        self.playback.enqueue("TTS_Test", [word])

    # ── Audio device / folder ───────────────────────────────────────────
    def _browse_folder(self):
        path = filedialog.askdirectory(title="Select audio files folder")
        if path:
            self.folder_var.set(path)
            self.audio.set_folder(path)

    def _refresh_devices(self):
        devices = self.audio.get_audio_devices()
        values = ["Default"] + [f"[{index}] {name}" for index, name, _channels in devices]
        self.device_combo["values"] = values
        if not self.device_var.get():
            self.device_combo.current(0)

    def _selected_device_index(self):
        """Parse the "[N] Device name" combobox value back into an index."""
        selected = self.device_var.get()
        if not selected or selected == "Default":
            return None
        try:
            return int(selected.split("]")[0].lstrip("["))
        except ValueError:
            return None

    # ── Playback settings snapshot (read by PlaybackService) ───────────
    def _current_playback_settings(self) -> PlaybackSettings:
        use_controller = self.ctrl_enabled_var.get()
        return PlaybackSettings(
            use_controller=use_controller,
            pre_press_delay=self.ctrl_pre_delay_var.get() if use_controller else 0.0,
            hold_before_audio=self.ctrl_hold_before_var.get() if use_controller else 0.0,
            hold_after_audio=self.ctrl_post_hold_var.get() if use_controller else 0.0,
            release_delay=self.ctrl_release_delay_var.get() if use_controller else 0.0,
            device_index=self._selected_device_index(),
            volume=self.volume_var.get(),
            tts_always=self.tts_always_var.get(),
            tts_enabled=self.tts_enabled_var.get(),
            tts_filter_enabled=self.tts_filter_var.get(),
            tts_rate_wpm=self.tts_rate_var.get(),
            word_gap_seconds=self.tts_gap_var.get(),
        )

    def _blocked_trigger_phrases(self):
        """Chat-button trigger words currently enabled — never spoken by TTS."""
        return [
            self._chat_btn_words[key].get().strip().lower()
            for key, enabled_var in self._chat_btn_enabled.items()
            if enabled_var.get() and self._chat_btn_words[key].get().strip()
        ]

    # ── Config load/save ─────────────────────────────────────────────────
    def _apply_config(self):
        cfg = self.cfg
        self.channel_var.set(cfg.get("channel", ""))
        self.oauth_var.set(cfg.get("oauth_token", ""))
        self.folder_var.set(cfg.get("audio_folder", ""))
        self.cooldown_var.set(cfg.get("cooldown", 1.5))
        self.volume_var.set(cfg.get("volume", 1.0))

        if cfg.get("custom_commands"):
            self.custom_text.insert("1.0", "\n".join(cfg["custom_commands"]))
        self._apply_custom_commands()
        self._refresh_devices()

        self._apply_controller_config(cfg)
        self._apply_tts_config(cfg)
        self._apply_chat_button_config(cfg)
        self._select_saved_device(cfg.get("output_device", ""))

    def _apply_controller_config(self, cfg):
        controller_enabled = cfg.get("ctrl_enabled", False)
        self.ctrl_enabled_var.set(controller_enabled)
        self.ctrl_pre_delay_var.set(cfg.get("ctrl_pre_delay", 0.0))
        self.ctrl_hold_before_var.set(cfg.get("ctrl_hold_before", 0.50))
        self.ctrl_post_hold_var.set(cfg.get("ctrl_post_hold", 0.0))
        self.ctrl_release_delay_var.set(cfg.get("ctrl_release_delay", 0.0))
        self.ctrl_full_hold_var.set(cfg.get("ctrl_full_hold", True))
        if controller_enabled:
            self._on_ctrl_toggle()

    def _apply_tts_config(self, cfg):
        self.tts_enabled_var.set(cfg.get("tts_enabled", False))
        self.tts_always_var.set(cfg.get("tts_always", False))
        self.tts_filter_var.set(cfg.get("tts_filter", True))
        self.tts_rate_var.set(cfg.get("tts_rate", 150))
        self.tts_voice_var.set(cfg.get("tts_voice", "Default"))
        self.tts_gap_var.set(cfg.get("tts_gap", 0.0))
        self._refresh_tts_voices()
        self._resolve_tts_voice()

    def _apply_chat_button_config(self, cfg):
        for button_key, data in cfg.get("chat_btns", {}).items():
            if button_key in self._chat_btn_enabled:
                self._chat_btn_enabled[button_key].set(data.get("enabled", False))
                self._chat_btn_words[button_key].set(data.get("word", ""))

    def _select_saved_device(self, saved_device: str):
        if not saved_device:
            return
        for value in self.device_combo["values"]:
            if saved_device in value:
                self.device_var.set(value)
                return

    def _save_config(self):
        self.cfg.update({
            "channel": self.channel_var.get().strip(),
            "oauth_token": self.oauth_var.get().strip(),
            "audio_folder": self.folder_var.get().strip(),
            "output_device": self.device_var.get(),
            "cooldown": self.cooldown_var.get(),
            "volume": self.volume_var.get(),
            "custom_commands": [
                line.strip() for line in self.custom_text.get("1.0", "end").splitlines() if line.strip()
            ],
            "ctrl_enabled": self.ctrl_enabled_var.get(),
            "ctrl_pre_delay": self.ctrl_pre_delay_var.get(),
            "ctrl_hold_before": self.ctrl_hold_before_var.get(),
            "ctrl_post_hold": self.ctrl_post_hold_var.get(),
            "ctrl_release_delay": self.ctrl_release_delay_var.get(),
            "ctrl_full_hold": self.ctrl_full_hold_var.get(),
            "tts_enabled": self.tts_enabled_var.get(),
            "tts_always": self.tts_always_var.get(),
            "tts_filter": self.tts_filter_var.get(),
            "tts_rate": self.tts_rate_var.get(),
            "tts_voice": self.tts_voice_var.get(),
            "tts_gap": self.tts_gap_var.get(),
            "chat_btns": {
                key: {"enabled": enabled_var.get(), "word": self._chat_btn_words[key].get().strip()}
                for key, enabled_var in self._chat_btn_enabled.items()
            },
        })
        config_module.save_config(self.cfg)
        self._resolve_tts_voice()
        self._set_status("Settings saved.")
        messagebox.showinfo("Saved", "Settings saved successfully.")
