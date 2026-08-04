"""
Main ("Live Feed") tab: connect/disconnect, chat message handling, and the
two live log panes.
"""

import re
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, scrolledtext, ttk

from ..twitch_bot import TwitchBot
from . import theme


class MainTabMixin:
    """Provides `_build_main_tab` plus connection/chat/log handling."""

    def _build_main_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="  \U0001F3AE Live Feed  ")

        self._build_connection_bar(frame)
        self._build_log_panes(frame)

    def _build_connection_bar(self, frame):
        controls = ttk.Frame(frame)
        controls.pack(fill="x", padx=10, pady=8)

        self.connect_btn = ttk.Button(
            controls, text="\u25b6 Connect", style="Green.TButton",
            command=self._toggle_connect, width=14,
        )
        self.connect_btn.pack(side="left", padx=4)

        self.conn_indicator = tk.Label(
            controls, text="\u2b24 Offline", bg=theme.BG_WINDOW,
            fg=theme.FG_ERROR_STRONG, font=("Segoe UI", 11, "bold"),
        )
        self.conn_indicator.pack(side="left", padx=8)

        tk.Label(controls, text="Commands played:", bg=theme.BG_WINDOW, fg=theme.FG_MUTED,
                 font=theme.FONT_LABEL).pack(side="left", padx=(20, 4))
        self.count_var = tk.StringVar(value="0")
        tk.Label(controls, textvariable=self.count_var, bg=theme.BG_WINDOW, fg=theme.FG_ACCENT,
                 font=("Segoe UI", 12, "bold")).pack(side="left")

        ttk.Button(controls, text="\U0001F5D1 Clear Log", command=self._clear_log).pack(side="right", padx=4)

    def _build_log_panes(self, frame):
        paned = tk.PanedWindow(frame, orient="horizontal", bg=theme.BG_WINDOW,
                                sashwidth=4, sashrelief="flat")
        paned.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        chat_pane = ttk.Frame(paned)
        tk.Label(chat_pane, text="\U0001F4AC Chat", bg=theme.BG_WINDOW, fg=theme.FG_MUTED,
                 font=theme.FONT_LABEL_BOLD).pack(anchor="w")
        self.chat_box = scrolledtext.ScrolledText(
            chat_pane, bg=theme.BG_LOG, fg="#c9d1d9", font=theme.FONT_MONO,
            insertbackground="white", borderwidth=0, relief="flat",
            state="disabled", wrap="word",
        )
        self.chat_box.pack(fill="both", expand=True)
        self.chat_box.tag_config("cmd", foreground=theme.FG_ACCENT_ALT, font=theme.FONT_MONO_BOLD)
        self.chat_box.tag_config("user", foreground=theme.FG_LINK)
        paned.add(chat_pane, minsize=300)

        cmd_pane = ttk.Frame(paned)
        tk.Label(cmd_pane, text="\U0001F50A Triggered Commands", bg=theme.BG_WINDOW, fg=theme.FG_MUTED,
                 font=theme.FONT_LABEL_BOLD).pack(anchor="w")
        self.cmd_box = scrolledtext.ScrolledText(
            cmd_pane, bg=theme.BG_LOG, fg=theme.FG_SUCCESS, font=theme.FONT_MONO_LARGE,
            insertbackground="white", borderwidth=0, relief="flat",
            state="disabled", wrap="word",
        )
        self.cmd_box.pack(fill="both", expand=True)
        paned.add(cmd_pane, minsize=240)

    # ── Connection ───────────────────────────────────────────────────────
    def _toggle_connect(self):
        if self.bot and self.bot.is_alive():
            self._disconnect()
        else:
            self._connect()

    def _disconnect(self):
        self.bot.stop()
        self.bot = None
        self.connect_btn.configure(text="\u25b6 Connect", style="Green.TButton")
        self.conn_indicator.configure(text="\u2b24 Offline", fg=theme.FG_ERROR_STRONG)

    def _connect(self):
        channel = self.channel_var.get().strip()
        token = self.oauth_var.get().strip()
        if not channel or not token:
            messagebox.showerror("Missing", "Please enter Twitch channel and OAuth token.")
            return

        self.audio.set_folder(self.folder_var.get().strip())
        self.bot = TwitchBot(
            channel=channel,
            oauth_token=token,
            on_command=self._on_chat_message,
            on_status=lambda status: self.log_queue.put(("status", status)),
        )
        self.bot.start()
        self.connect_btn.configure(text="\u25a0 Disconnect", style="Red.TButton")
        self.conn_indicator.configure(text="\u2b24 Connecting\u2026", fg="#ffa500")

    # ── Chat handling ────────────────────────────────────────────────────
    def _on_chat_message(self, username: str, message: str):
        """
        Called (on its own thread) for every chat message. Scans for
        chat-button triggers and voice commands independently, then queues
        whichever ones apply.
        """
        self._check_chat_button_triggers(message)

        matched_commands = self.command_matcher.find_matches(message)
        self.chat_queue.put((username, message, matched_commands))
        if not matched_commands:
            return

        if not self._cooldown_allows(matched_commands):
            return

        self.playback.enqueue(username, matched_commands)
        self._fire_chat_button_presses_for(matched_commands)

    def _cooldown_allows(self, matched_commands) -> bool:
        """
        Each unique command is cooldown-checked once; if at least one
        command in the batch is off cooldown, the whole batch plays (a
        repeated word like "hello hello hello" is not deduped — spam
        control is this cooldown, not deduplication).
        """
        now = time.time()
        cooldown = self.cooldown_var.get()
        unique_commands = dict.fromkeys(matched_commands)  # preserves order

        if not any(now - self.last_played.get(cmd, 0) >= cooldown for cmd in unique_commands):
            return False

        for cmd in unique_commands:
            self.last_played[cmd] = now
        return True

    def _check_chat_button_triggers(self, message: str):
        """
        Chat-button triggers run independently of voice commands and don't
        need to be in the Lifeline vocabulary.
        """
        message_words = set(self._extract_words(message))
        for button_key, enabled_var in self._chat_btn_enabled.items():
            if not enabled_var.get():
                continue
            trigger = self._chat_btn_words[button_key].get().strip().lower()
            if trigger and set(trigger.split()).issubset(message_words):
                self._fire_chat_button_press(button_key)

    def _fire_chat_button_presses_for(self, matched_commands):
        lowered_matches = [cmd.lower() for cmd in matched_commands]
        for button_key, enabled_var in self._chat_btn_enabled.items():
            if not enabled_var.get():
                continue
            trigger = self._chat_btn_words[button_key].get().strip().lower()
            if trigger and trigger in lowered_matches:
                self._fire_chat_button_press(button_key)

    def _fire_chat_button_press(self, button_key: str):
        if not (self.ctrl_enabled_var.get() and self.controller.ready):
            self.log_queue.put(("command", f"  ! {button_key} triggered but controller not enabled"))
            return
        threading.Thread(target=self._press_chat_button, args=(button_key,), daemon=True).start()

    def _press_chat_button(self, button_key: str):
        """Press and release a non-Circle button (no sustained hold)."""
        self.controller.press_button(button_key)
        self.log_queue.put(("command", f"  \u25ba Chat button: {button_key} pressed"))
        time.sleep(0.1)
        self.controller.release_button(button_key)
        self.log_queue.put(("command", f"  \u25ba Chat button: {button_key} released"))

    @staticmethod
    def _extract_words(text: str):
        return re.findall(r"[a-z0-9]+", text.lower())

    # ── Queue polling / log rendering ───────────────────────────────────
    def _poll_queues(self):
        self._drain_log_queue()
        self._drain_chat_queue()
        self.after(80, self._poll_queues)

    def _drain_log_queue(self):
        while not self.log_queue.empty():
            kind, message = self.log_queue.get_nowait()
            if kind == "status":
                self._handle_status_message(message)
            elif kind == "command":
                self._append_cmd(message)
                self.count_var.set(str(self.play_count))
            elif kind == "error":
                self._append_cmd(f"\u26a0 {message}", color=theme.FG_ERROR)

    def _handle_status_message(self, message: str):
        self._set_status(message)
        if "Connected" in message:
            self.conn_indicator.configure(text="\u2b24 Live", fg=theme.FG_SUCCESS)
        elif "Disconnected" in message or "Failed" in message:
            self.conn_indicator.configure(text="\u2b24 Offline", fg=theme.FG_ERROR_STRONG)
            self.connect_btn.configure(text="\u25b6 Connect", style="Green.TButton")

    def _drain_chat_queue(self):
        while not self.chat_queue.empty():
            username, message, matched_commands = self.chat_queue.get_nowait()
            self._render_chat_line(username, message, matched_commands)

    def _render_chat_line(self, username, message, matched_commands):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", f"[{timestamp}] ")
        self.chat_box.insert("end", username, "user")
        self.chat_box.insert("end", ": ")

        if matched_commands:
            self._insert_message_with_highlights(message, matched_commands)
        else:
            self.chat_box.insert("end", message + "\n")

        self.chat_box.configure(state="disabled")
        self.chat_box.see("end")

    def _insert_message_with_highlights(self, message, matched_commands):
        """Insert `message`, highlighting each matched command/phrase in place."""
        remaining = message
        for command in matched_commands:
            index = remaining.lower().find(command)
            if index < 0:
                continue
            self.chat_box.insert("end", remaining[:index])
            self.chat_box.insert("end", remaining[index:index + len(command)], "cmd")
            remaining = remaining[index + len(command):]
        self.chat_box.insert("end", remaining + "\n")

    def _append_cmd(self, text, color=theme.FG_SUCCESS):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.cmd_box.configure(state="normal")
        self.cmd_box.insert("end", f"[{timestamp}] {text}\n")
        self.cmd_box.configure(state="disabled")
        self.cmd_box.see("end")

    def _clear_log(self):
        for box in (self.chat_box, self.cmd_box):
            box.configure(state="normal")
            box.delete("1.0", "end")
            box.configure(state="disabled")

    def _set_status(self, text):
        self.status_var.set(text)
