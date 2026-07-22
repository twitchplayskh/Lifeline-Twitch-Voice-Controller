"""
Lifeline Twitch Voice Controller
Connects to Twitch chat, listens for Lifeline commands, plays audio through a virtual mic.
"""

import socket
import threading
import time
import os
import sys
import queue
import re
import json
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from pathlib import Path
from datetime import datetime

# Audio playback
try:
    import sounddevice as sd
    import soundfile as sf
    import numpy as np
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False

# Virtual gamepad (requires ViGEmBus driver + vgamepad)
try:
    import vgamepad as vg
    HAS_GAMEPAD = True
except ImportError:
    HAS_GAMEPAD = False

# Text-to-speech
try:
    import pyttsx3
    HAS_TTS = True
except ImportError:
    HAS_TTS = False

# Profanity filter
try:
    from better_profanity import profanity as _profanity_checker
    _profanity_checker.load_censor_words()
    HAS_PROFANITY_FILTER = True
except ImportError:
    HAS_PROFANITY_FILTER = False

# ── Lifeline recognized commands ──────────────────────────────────────────────
# These are the words/phrases Rio recognizes in the PS2 game.
LIFELINE_COMMANDS = {
    # Movement
    "go", "move", "walk", "run", "follow", "come", "here", "back",
    "left", "right", "forward", "ahead", "behind", "north", "south", "east", "west",
    "up", "down", "stop", "wait", "stay", "return", "approach", "enter", "exit",
    # Connectives / prepositions (needed for sentences like "go to the table")
    "to", "the", "a", "an", "and", "then", "next", "after",
    "in", "into", "on", "onto", "over", "under", "through",
    "with", "without", "at", "from", "toward", "towards",
    # Actions
    "get", "take", "grab", "pick", "drop", "use", "open", "close", "push", "pull",
    "hit", "attack", "fight", "kick", "dodge", "hide", "crouch", "stand",
    "look", "examine", "search", "check", "read",
    "give", "throw", "put", "place", "carry", "hold", "release",
    "eat", "drink", "heal", "rest", "sleep", "wake",
    "climb", "jump", "duck", "turn",
    "shoot", "fire", "reload", "aim", "flee", "recover",
    "unlock", "lock", "break", "destroy", "press", "flip",
    # Communication
    "yes", "no", "okay", "ok", "help", "call", "talk", "say", "speak", "answer",
    "thanks", "sorry", "please", "hurry", "careful",
    # Items / context
    "door", "key", "gun", "weapon", "item", "box", "chest", "table",
    "light", "switch", "button", "stairs", "ladder", "window", "wall", "floor",
    "room", "hall", "hallway",
    "knife", "bat", "stick", "bottle", "can", "food", "water",
    "medicine", "bandage", "first", "aid",
    "phone", "radio", "computer", "panel", "machine",
    "bag", "backpack", "cabinet", "drawer", "shelf",
    # Positional / directional
    "there", "that", "this", "front", "side", "corner", "end",
    # Status
    "status", "health", "ammo", "inventory", "map", "where", "what", "how",
    # System
    "save", "cancel", "skip", "repeat", "again",
    # Single-word official keywords from the FAQ
    "consultation", "strafe", "taunt", "jump", "jumpback", "dodge",
    "approach", "flee", "shoot", "reload", "recover", "front", "back",
    "suicide", "walk", "run", "stop", "check",
    # Words extracted from official phrases (auto-generated)
    "about", "alien", "alive", "allen", "am", "announcer", "any", "are",
    "around", "attacked", "auto", "away", "bark", "by", "camera", "captain",
    "category", "cell", "clothes", "coming", "conducting", "cranky", "dead", "detaining",
    "did", "do", "dog", "earlier", "earth", "fake", "far", "for",
    "friends", "fuck", "game", "gino", "girl", "got", "gravity", "great",
    "green", "group", "happened", "hate", "have", "helen", "his", "hotel",
    "humanoid", "i", "if", "is", "isn", "it", "johnson", "joseph",
    "jsl", "kill", "lady", "leave", "like", "ll", "looking", "love",
    "low", "m", "made", "man", "manager", "me", "microphone", "monster",
    "monsters", "naomi", "now", "number", "of", "off", "orb", "paracelsus",
    "people", "philosopher", "pm", "poor", "pose", "power", "powers", "re",
    "reflexes", "relationship", "remnants", "rescue", "research", "researching", "restaurant", "s",
    "safe", "sells", "sex", "sexy", "she", "should", "sign", "sit",
    "so", "spin", "stone", "strong", "structure", "sucks", "t", "tanaka",
    "team", "tell", "they", "things", "think", "time", "ve", "was",
    "wasn", "we", "were", "when", "who", "why", "will", "wonder",
    "words", "you", "your", "yourself", "zero", "zoom",
}

# Multi-word phrases the game officially recognises (from FAQ keyword list).
# These are matched as complete units from chat messages — a phrase match
# takes priority over individual word matching.
LIFELINE_PHRASES = {
    # Normal keywords
    "go back",
    # Scenario keywords
    "why were you in the detaining cell",
    "where am i",
    "who's naomi",
    "what is jsl",
    "what are you looking for",
    "what was that monster",
    "who is helen johnson",
    "why are you so cranky",
    "i wonder if naomi's alive",
    "what is the manager like",
    "what do you think of the pm",
    "do you have any friends",
    "what's the relationship with gino",
    "is a rescue team coming",
    "how are things on earth",
    "naomi isn't around",
    "what are they researching here",
    "what do you think of allen",
    "where is the announcer",
    "tell me about yourself",
    "tell me what you're looking for",
    "powers and alien",
    "what do you think of powers",
    "how far away are you",
    "naomi wasn't there",
    "about this hotel's structure",
    "humanoid alien",
    "i wonder if the pm and his people are ok",
    "what do you think of that captain",
    "that alien earlier",
    "you've got great reflexes",
    "i wonder if naomi is safe",
    "you're looking for a green orb",
    "i wonder if the manager is ok",
    "where is gino",
    "the announcer was dead",
    "that man in the restaurant",
    "when we get to earth",
    "how was earth",
    "is this hotel ok",
    "why did tanaka turn into a monster",
    "the poor manager",
    "what happened to powers",
    "i wonder if gino is ok",
    "what is paracelsus",
    "the remnants of paracelsus",
    "the power of words",
    "are you close to me now",
    "is it zero gravity",
    "what's a philosopher's stone",
    "the first lady was attacked by an alien",
    "that allen",
    "what happened to gino",
    "what was that group",
    "where is naomi",
    "the monsters were made here",
    "allen was conducting research here",
    "you're strong",
    "it's about naomi",
    "what's a fake stone",
    "powers is joseph",
    "what should we do",
    # Special keywords
    "microphone check",
    "zoom in",
    "low kick",
    "category game",
    "spin the gun",
    "sexy pose",
    "auto-fire",
    "she sells",
    "break time",
    "i'll leave it to you",
    "camera check",
    # Battle keywords
    "number 1", "number 2", "number 3",
    "turn right", "turn left",
    # Fun keywords
    "kill yourself",
    "i love you",
    "i hate you",
    "bark like a dog",
    "fuck you",
    "what's your sign",
    "i'm sorry",
    "sit down",
    "will you have sex with me",
    "are you a girl",
    "this game sucks",
    "take off your clothes",
}

# ── Config file ───────────────────────────────────────────────────────────────
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    defaults = {
        "channel": "",
        "oauth_token": "",
        "audio_folder": "",
        "output_device": "",
        "virtual_device": "",
        "cooldown": 1.5,
        "volume": 1.0,
        "custom_commands": [],
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                saved = json.load(f)
            defaults.update(saved)
        except json.JSONDecodeError:
            import shutil
            shutil.copy(CONFIG_FILE, CONFIG_FILE + ".corrupted")
        except Exception:
            pass
    return defaults

def save_config(cfg):
    # Write to temp file first then rename — atomic, avoids corruption on crash
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG_FILE)

# ── Twitch IRC bot ────────────────────────────────────────────────────────────
class TwitchBot(threading.Thread):
    IRC_HOST = "irc.chat.twitch.tv"
    IRC_PORT = 6667

    def __init__(self, channel, oauth_token, on_command, on_status, on_raw):
        super().__init__(daemon=True)
        self.channel = channel.lower().lstrip("#")
        self.oauth_token = oauth_token
        self.on_command = on_command   # callback(username, command, raw_msg)
        self.on_status = on_status     # callback(text)
        self.on_raw = on_raw           # callback(raw_line)
        self._stop_event = threading.Event()
        self.sock = None

    def send_raw(self, msg):
        if self.sock:
            try:
                self.sock.send((msg + "\r\n").encode("utf-8"))
            except Exception:
                pass

    def run(self):
        self.on_status("Connecting to Twitch IRC…")
        try:
            self.sock = socket.socket()
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock.connect((self.IRC_HOST, self.IRC_PORT))
            self.sock.settimeout(300)
            self.send_raw(f"PASS oauth:{self.oauth_token}")
            self.send_raw("NICK lifeline_bot")
            self.send_raw(f"JOIN #{self.channel}")
            self.on_status(f"Connected to #{self.channel}")

            buf = ""
            while not self._stop_event.is_set():
                try:
                    data = self.sock.recv(8192).decode("utf-8", errors="ignore")
                except socket.timeout:
                    self.send_raw("PING :tmi.twitch.tv")
                    continue
                except Exception as e:
                    self.on_status(f"Connection error: {e}")
                    break

                buf += data
                while "\r\n" in buf:
                    line, buf = buf.split("\r\n", 1)
                    self.on_raw(line)
                    self._handle_line(line)

        except Exception as e:
            self.on_status(f"Failed to connect: {e}")
        finally:
            if self.sock:
                self.sock.close()
            self.on_status("Disconnected.")

    def _handle_line(self, line):
        if line.startswith("PING"):
            self.send_raw("PONG :tmi.twitch.tv")
            return
        # :username!user@user.tmi.twitch.tv PRIVMSG #channel :message
        match = re.match(r":(\w+)!\w+@\S+ PRIVMSG #\S+ :(.+)", line)
        if match:
            username = match.group(1)
            message = match.group(2).strip()
            # Fire-and-forget: never block the IRC receive loop
            threading.Thread(
                target=self.on_command,
                args=(username, message),
                daemon=True
            ).start()

    def stop(self):
        self._stop_event.set()
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass

# ── Audio engine ──────────────────────────────────────────────────────────────


# ── TTS engine ────────────────────────────────────────────────────────────────
class TTSEngine:
    """
    Wraps pyttsx3 to synthesise a word to a temp WAV file, then hand it to
    AudioEngine for playback (so all the device routing / resampling still applies).
    pyttsx3 must be initialised on the same thread it is used on, so we run it
    in a dedicated daemon thread with a job queue.
    """

    def __init__(self):
        self._queue = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        self.rate = 150      # words per minute
        self.volume = 1.0
        self.voice_id = None  # None = system default
        self._voices_cache = None   # cached once on first call

    def _worker(self):
        """
        Process synthesis jobs one at a time.
        A fresh pyttsx3 engine is created and destroyed for EACH job —
        this is intentional. pyttsx3's internal COM/event state becomes
        corrupted after the first runAndWait() call on Windows, causing all
        subsequent save_to_file calls to silently fail. Re-initialising each
        time is the only reliable fix.
        """
        while True:
            job = self._queue.get()
            if job is None:
                break
            text, out_path, event, result = job
            if not HAS_TTS:
                result.append(None)
                event.set()
                continue
            engine = None
            try:
                engine = pyttsx3.init()
                engine.setProperty("rate", self.rate)
                engine.setProperty("volume", self.volume)
                if self.voice_id:
                    engine.setProperty("voice", self.voice_id)
                # Delete stale file so we can detect if save fails
                if os.path.exists(out_path):
                    os.remove(out_path)
                engine.save_to_file(text, out_path)
                engine.runAndWait()
                result.append(out_path if os.path.exists(out_path) else None)
            except Exception as e:
                result.append(None)
            finally:
                # Always stop/destroy the engine to release COM resources
                try:
                    if engine:
                        engine.stop()
                except Exception:
                    pass
                event.set()

    def synthesise(self, text, out_path):
        """Blocking: render text to WAV file, return path or None on failure."""
        if not HAS_TTS:
            return None
        event = threading.Event()
        result = []
        self._queue.put((text, out_path, event, result))
        event.wait(timeout=30)
        return result[0] if result else None

    def get_voices(self):
        """Return list of (id, name) for the settings dropdown (cached)."""
        if self._voices_cache is not None:
            return self._voices_cache
        if not HAS_TTS:
            return []
        try:
            eng = pyttsx3.init()
            voices = eng.getProperty("voices")
            self._voices_cache = [(v.id, v.name) for v in voices]
            eng.stop()
            return self._voices_cache
        except Exception:
            return []

    def stop(self):
        self._queue.put(None)


# ── Profanity / hate-word filter ──────────────────────────────────────────────
class WordFilter:
    """
    Two-layer filter:
      1. better_profanity library (if installed) — catches common profanity
      2. A hard-coded explicit/hate blocklist that is always active regardless
    The filter only acts on words that have already passed the Lifeline command
    whitelist, so it is a safety net rather than a general chat filter.
    """

    # Hard-coded words that must never reach TTS even if somehow whitelisted.
    # Using fragments / leet variants to avoid storing the full strings here.
    _HARD_BLOCK = {
        "nigger", "nigga", "faggot", "fag", "kike", "spic", "chink",
        "cunt", "fuck", "shit", "bitch", "asshole", "bastard", "whore",
        "slut", "piss", "cock", "dick", "pussy", "retard", "tranny",
        "dyke", "wetback", "gook", "cracker", "honky",
    }

    def is_clean(self, word: str) -> bool:
        w = word.lower().strip()
        if w in self._HARD_BLOCK:
            return False
        if HAS_PROFANITY_FILTER:
            if _profanity_checker.contains_profanity(w):
                return False
        return True


# Controller engine
class ControllerEngine:
    """
    Manages a virtual DS4 / Xbox360 gamepad.
    Supports pressing any PS2-mapped button, configurable from the UI.

    PS2 -> DS4 / Xbox360 button mapping:
      Circle   -> DS4_BUTTON_CIRCLE      / XUSB_GAMEPAD_B
      Square   -> DS4_BUTTON_SQUARE      / XUSB_GAMEPAD_X
      Cross    -> DS4_BUTTON_CROSS       / XUSB_GAMEPAD_A
      Triangle -> DS4_BUTTON_TRIANGLE    / XUSB_GAMEPAD_Y
      L1       -> DS4_BUTTON_SHOULDER_LEFT  / XUSB_GAMEPAD_LEFT_SHOULDER
      R1       -> DS4_BUTTON_SHOULDER_RIGHT / XUSB_GAMEPAD_RIGHT_SHOULDER
      L2       -> DS4_TRIGGER_LEFT (axis)   / left trigger (axis)
      Start    -> DS4_BUTTON_OPTIONS     / XUSB_GAMEPAD_START
      Select   -> DS4_BUTTON_SHARE       / XUSB_GAMEPAD_BACK
    """

    # Map: PS2 label -> (DS4 button attr or None, Xbox attr or None, is_trigger)
    BUTTON_MAP = {
        "Circle":   ("DS4_BUTTON_CIRCLE",          "XUSB_GAMEPAD_B",              False),
        "Square":   ("DS4_BUTTON_SQUARE",          "XUSB_GAMEPAD_X",              False),
        "Cross":    ("DS4_BUTTON_CROSS",           "XUSB_GAMEPAD_A",              False),
        "Triangle": ("DS4_BUTTON_TRIANGLE",        "XUSB_GAMEPAD_Y",              False),
        "L1":       ("DS4_BUTTON_SHOULDER_LEFT",   "XUSB_GAMEPAD_LEFT_SHOULDER",  False),
        "R1":       ("DS4_BUTTON_SHOULDER_RIGHT",  "XUSB_GAMEPAD_RIGHT_SHOULDER", False),
        "L2":       (None,                         None,                          True),
        "Start":    ("DS4_BUTTON_OPTIONS",         "XUSB_GAMEPAD_START",          False),
        "Select":   ("DS4_BUTTON_SHARE",           "XUSB_GAMEPAD_BACK",           False),
    }

    def __init__(self):
        self.enabled = False
        self._pad = None
        self._pad_type = None   # "ds4" or "x360"
        self._lock = threading.Lock()
        self.active_button = "Circle"   # always Circle for voice — do not change

    def init(self, prefer_ds4=True):
        """Try to create a virtual gamepad. Returns (ok, message)."""
        if not HAS_GAMEPAD:
            return False, "vgamepad not installed. Run: pip install vgamepad"
        with self._lock:
            try:
                if prefer_ds4:
                    self._pad = vg.VDS4Gamepad()
                    self._pad_type = "ds4"
                else:
                    self._pad = vg.VX360Gamepad()
                    self._pad_type = "x360"
                self._pad.reset()
                self._pad.update()
                return True, "Virtual {} controller created.".format("DS4" if prefer_ds4 else "Xbox360")
            except Exception as e:
                if prefer_ds4:
                    try:
                        self._pad = vg.VX360Gamepad()
                        self._pad_type = "x360"
                        self._pad.reset()
                        self._pad.update()
                        return True, "Virtual Xbox360 controller created (DS4 unavailable)."
                    except Exception as e2:
                        self._pad = None
                        return False, "Controller init failed: {}".format(e2)
                self._pad = None
                return False, "Controller init failed: {}".format(e)

    def destroy(self):
        with self._lock:
            if self._pad:
                try:
                    self._pad.reset()
                    self._pad.update()
                except Exception:
                    pass
            self._pad = None

    def _do_button(self, action, button_label):
        """Press or release a button by its PS2 label. action = 'press' or 'release'."""
        if not self._pad:
            return
        entry = self.BUTTON_MAP.get(button_label)
        if not entry:
            return
        ds4_attr, x360_attr, is_trigger = entry
        with self._lock:
            try:
                if is_trigger:
                    # L2/R2 — use axis value (255 = fully pressed, 0 = released)
                    val = 255 if action == "press" else 0
                    if self._pad_type == "ds4":
                        self._pad.left_trigger(value=val)
                    else:
                        self._pad.left_trigger(value=val)
                else:
                    if self._pad_type == "ds4":
                        btn = getattr(vg.DS4_BUTTONS, ds4_attr)
                    else:
                        btn = getattr(vg.XUSB_BUTTON, x360_attr)
                    if action == "press":
                        self._pad.press_button(button=btn)
                    else:
                        self._pad.release_button(button=btn)
                self._pad.update()
            except Exception:
                pass

    def press_circle(self):
        """Press the currently configured button (named 'press_circle' for compatibility)."""
        self._do_button("press", self.active_button)

    def release_circle(self):
        """Release the currently configured button."""
        self._do_button("release", self.active_button)

    @property
    def ready(self):
        return self._pad is not None

class AudioEngine:
    def __init__(self):
        self.audio_folder = ""
        self.output_device = None   # index or None for default
        self.volume = 1.0
        self._lock = threading.Lock()
        self._playing = False
        self._file_cache = {}   # word -> path, invalidated when folder changes

    def set_folder(self, folder):
        self.audio_folder = folder
        self._file_cache.clear()   # invalidate on folder change

    def get_audio_devices(self):
        if not HAS_AUDIO:
            return []
        try:
            devices = sd.query_devices()
            return [(i, d['name'], d['max_output_channels']) for i, d in enumerate(devices) if d['max_output_channels'] > 0]
        except Exception:
            return []

    def find_file(self, command):
        """Look for audio file matching the command word (result is cached)."""
        if not self.audio_folder or not os.path.isdir(self.audio_folder):
            return None
        if command in self._file_cache:
            return self._file_cache[command]
        exts = [".wav", ".mp3", ".ogg", ".flac", ".aiff"]
        for ext in exts:
            path = os.path.join(self.audio_folder, command + ext)
            if os.path.exists(path):
                self._file_cache[command] = path
                return path
            path = os.path.join(self.audio_folder, command.upper() + ext)
            if os.path.exists(path):
                self._file_cache[command] = path
                return path
        self._file_cache[command] = None   # cache miss too
        return None

    def _get_device_samplerate(self, device_index):
        """Get the default sample rate for the given device (or system default)."""
        try:
            if device_index is None:
                info = sd.query_devices(kind='output')
            else:
                info = sd.query_devices(device_index)
            return int(info['default_samplerate'])
        except Exception:
            return 44100

    def _resample(self, data, orig_sr, target_sr):
        """Simple linear resample to match target sample rate."""
        if orig_sr == target_sr:
            return data
        ratio = target_sr / orig_sr
        orig_len = data.shape[0]
        new_len = int(orig_len * ratio)
        old_indices = np.linspace(0, orig_len - 1, new_len)
        new_indices_floor = np.floor(old_indices).astype(int)
        new_indices_ceil = np.minimum(new_indices_floor + 1, orig_len - 1)
        frac = (old_indices - new_indices_floor)[:, np.newaxis] if data.ndim > 1 else (old_indices - new_indices_floor)
        resampled = data[new_indices_floor] + frac * (data[new_indices_ceil] - data[new_indices_floor])
        return resampled.astype(np.float32)

    def play(self, filepath, device_index=None, volume=1.0, callback=None):
        if not HAS_AUDIO:
            if callback:
                callback(False, "sounddevice/soundfile not installed")
            return
        def _play():
            with self._lock:
                self._playing = True
            try:
                data, samplerate = sf.read(filepath, dtype='float32')
                data = data * volume

                # Resample to device's native rate to avoid "Invalid sample rate" errors
                device_sr = self._get_device_samplerate(device_index)
                if samplerate != device_sr:
                    data = self._resample(data, samplerate, device_sr)
                    samplerate = device_sr

                sd.play(data, samplerate, device=device_index, blocking=True)
                if callback:
                    callback(True, None)
            except Exception as e:
                if callback:
                    callback(False, str(e))
            finally:
                with self._lock:
                    self._playing = False
        t = threading.Thread(target=_play, daemon=True)
        t.start()

# ── Main GUI App ──────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🎮 Lifeline Twitch Voice Controller")
        self.geometry("900x680")
        self.configure(bg="#1a1a2e")
        self.resizable(True, True)

        self.cfg = load_config()
        self.bot = None
        self.audio = AudioEngine()
        self.controller = ControllerEngine()
        self.tts = TTSEngine()
        self.word_filter = WordFilter()
        self.tts_gap_var = tk.DoubleVar(value=0.0)
        self.tts_rate_var = tk.IntVar(value=150)
        self._tts_tmp_dir = os.path.join(os.path.dirname(__file__), '_tts_cache')
        os.makedirs(self._tts_tmp_dir, exist_ok=True)
        # Serialises multi-word sentence playback so words play in order
        self._playback_queue = queue.Queue()
        self._playback_thread = threading.Thread(target=self._playback_worker, daemon=True)
        self._playback_thread.start()
        self.log_queue = queue.Queue()
        self.chat_queue = queue.Queue()

        # Cooldown tracking
        self.last_played = {}
        self.play_count = 0

        # Custom commands set (merged with built-in)
        self.active_commands = set(LIFELINE_COMMANDS)
        self.active_phrases = set(LIFELINE_PHRASES)

        self._build_ui()
        self._apply_config()
        self._poll_queues()

    # ── UI Construction ───────────────────────────────────────────────────────
    def _build_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook", background="#1a1a2e", borderwidth=0)
        style.configure("TNotebook.Tab", background="#16213e", foreground="#e0e0e0",
                        padding=[12, 6], font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", "#0f3460")],
                  foreground=[("selected", "#e94560")])
        style.configure("TFrame", background="#1a1a2e")
        style.configure("TLabel", background="#1a1a2e", foreground="#e0e0e0", font=("Segoe UI", 10))
        style.configure("TEntry", fieldbackground="#16213e", foreground="#e0e0e0",
                        insertcolor="white", borderwidth=1)
        style.configure("TButton", background="#0f3460", foreground="#e0e0e0",
                        font=("Segoe UI", 10, "bold"), borderwidth=0, padding=6)
        style.map("TButton", background=[("active", "#e94560")])
        style.configure("Green.TButton", background="#1a472a", foreground="#90ee90")
        style.map("Green.TButton", background=[("active", "#2d6a4f")])
        style.configure("Red.TButton", background="#6b1a1a", foreground="#ff9999")
        style.map("Red.TButton", background=[("active", "#9b2335")])

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        self._build_main_tab(nb)
        self._build_config_tab(nb)
        self._build_commands_tab(nb)

        # Status bar
        self.status_var = tk.StringVar(value="Ready. Configure settings and connect.")
        status_bar = tk.Label(self, textvariable=self.status_var, bg="#0f3460",
                              fg="#90ee90", anchor="w", padx=10, font=("Segoe UI", 9))
        status_bar.pack(fill="x", side="bottom")

    def _build_main_tab(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  🎮 Live Feed  ")

        # Top controls
        ctrl = ttk.Frame(frame)
        ctrl.pack(fill="x", padx=10, pady=8)

        self.connect_btn = ttk.Button(ctrl, text="▶ Connect", style="Green.TButton",
                                      command=self._toggle_connect, width=14)
        self.connect_btn.pack(side="left", padx=4)

        self.conn_indicator = tk.Label(ctrl, text="⬤ Offline", bg="#1a1a2e",
                                       fg="#ff4444", font=("Segoe UI", 11, "bold"))
        self.conn_indicator.pack(side="left", padx=8)

        tk.Label(ctrl, text="Commands played:", bg="#1a1a2e", fg="#aaa",
                 font=("Segoe UI", 10)).pack(side="left", padx=(20, 4))
        self.count_var = tk.StringVar(value="0")
        tk.Label(ctrl, textvariable=self.count_var, bg="#1a1a2e", fg="#e94560",
                 font=("Segoe UI", 12, "bold")).pack(side="left")

        ttk.Button(ctrl, text="🗑 Clear Log", command=self._clear_log).pack(side="right", padx=4)

        # Split panes
        paned = tk.PanedWindow(frame, orient="horizontal", bg="#1a1a2e",
                               sashwidth=4, sashrelief="flat")
        paned.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        # Chat log (left)
        left = ttk.Frame(paned)
        tk.Label(left, text="💬 Chat", bg="#1a1a2e", fg="#aaaaaa",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.chat_box = scrolledtext.ScrolledText(
            left, bg="#0d1117", fg="#c9d1d9", font=("Consolas", 9),
            insertbackground="white", borderwidth=0, relief="flat",
            state="disabled", wrap="word")
        self.chat_box.pack(fill="both", expand=True)
        self.chat_box.tag_config("cmd", foreground="#f0c27f", font=("Consolas", 9, "bold"))
        self.chat_box.tag_config("user", foreground="#79c0ff")
        paned.add(left, minsize=300)

        # Command log (right)
        right = ttk.Frame(paned)
        tk.Label(right, text="🔊 Triggered Commands", bg="#1a1a2e", fg="#aaaaaa",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.cmd_box = scrolledtext.ScrolledText(
            right, bg="#0d1117", fg="#90ee90", font=("Consolas", 10),
            insertbackground="white", borderwidth=0, relief="flat",
            state="disabled", wrap="word")
        self.cmd_box.pack(fill="both", expand=True)
        paned.add(right, minsize=240)

    def _build_config_tab(self, nb):
        outer = ttk.Frame(nb)
        nb.add(outer, text="  ⚙️ Settings  ")

        # Scrollable canvas so nothing gets cut off
        canvas = tk.Canvas(outer, bg="#1a1a2e", highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        frame = tk.Frame(canvas, bg="#1a1a2e")
        frame_window = canvas.create_window((0, 0), window=frame, anchor="nw")

        def _on_canvas_resize(event):
            canvas.itemconfig(frame_window, width=event.width)
        canvas.bind("<Configure>", _on_canvas_resize)

        def _on_frame_resize(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        frame.bind("<Configure>", _on_frame_resize)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        # Scroll only when mouse is over this canvas — no cross-tab interference
        def _enter(e):  canvas.bind_all("<MouseWheel>", _on_mousewheel)
        def _leave(e):  canvas.unbind_all("<MouseWheel>")
        canvas.bind("<Enter>", _enter)
        canvas.bind("<Leave>", _leave)
        frame.bind("<Configure>", _on_frame_resize)

        pad = {"padx": 12, "pady": 5}

        # Twitch section
        sec = tk.LabelFrame(frame, text=" Twitch IRC ", bg="#16213e", fg="#e94560",
                            font=("Segoe UI", 10, "bold"), bd=1, relief="groove")
        sec.pack(fill="x", padx=12, pady=8)

        tk.Label(sec, text="Channel name:", bg="#16213e", fg="#e0e0e0",
                 font=("Segoe UI", 10)).grid(row=0, column=0, sticky="e", **pad)
        self.channel_var = tk.StringVar()
        ttk.Entry(sec, textvariable=self.channel_var, width=32).grid(row=0, column=1, sticky="w", **pad)

        tk.Label(sec, text="OAuth token:", bg="#16213e", fg="#e0e0e0",
                 font=("Segoe UI", 10)).grid(row=1, column=0, sticky="e", **pad)
        self.oauth_var = tk.StringVar()
        oauth_entry = ttk.Entry(sec, textvariable=self.oauth_var, width=40, show="*")
        oauth_entry.grid(row=1, column=1, sticky="w", **pad)
        tk.Label(sec, text="Get token: https://twitchapps.com/tmi/",
                 bg="#16213e", fg="#888", font=("Segoe UI", 8)).grid(row=2, column=1, sticky="w", padx=12)

        # Audio section
        sec2 = tk.LabelFrame(frame, text=" Audio ", bg="#16213e", fg="#e94560",
                             font=("Segoe UI", 10, "bold"), bd=1, relief="groove")
        sec2.pack(fill="x", padx=12, pady=8)

        tk.Label(sec2, text="Audio files folder:", bg="#16213e", fg="#e0e0e0",
                 font=("Segoe UI", 10)).grid(row=0, column=0, sticky="e", **pad)
        self.folder_var = tk.StringVar()
        folder_frame = ttk.Frame(sec2)
        folder_frame.grid(row=0, column=1, sticky="w", **pad)
        ttk.Entry(folder_frame, textvariable=self.folder_var, width=32).pack(side="left")
        ttk.Button(folder_frame, text="Browse…", command=self._browse_folder).pack(side="left", padx=4)

        tk.Label(sec2, text="Output device:", bg="#16213e", fg="#e0e0e0",
                 font=("Segoe UI", 10)).grid(row=1, column=0, sticky="e", **pad)
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(sec2, textvariable=self.device_var, width=38, state="readonly")
        self.device_combo.grid(row=1, column=1, sticky="w", **pad)
        ttk.Button(sec2, text="↻ Refresh devices", command=self._refresh_devices).grid(
            row=2, column=1, sticky="w", padx=12, pady=2)

        tk.Label(sec2,
                 text="💡 Tip: Install VB-Cable or VoiceMeeter and select it as output device.\n"
                      "   Then set the same virtual device as your mic input in the PS2 emulator / capture card.",
                 bg="#16213e", fg="#999", font=("Segoe UI", 8),
                 justify="left").grid(row=3, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 6))

        # Playback settings
        sec3 = tk.LabelFrame(frame, text=" Playback ", bg="#16213e", fg="#e94560",
                             font=("Segoe UI", 10, "bold"), bd=1, relief="groove")
        sec3.pack(fill="x", padx=12, pady=8)

        tk.Label(sec3, text="Command cooldown (s):", bg="#16213e", fg="#e0e0e0",
                 font=("Segoe UI", 10)).grid(row=0, column=0, sticky="e", **pad)
        self.cooldown_var = tk.DoubleVar(value=1.5)
        ttk.Spinbox(sec3, from_=0, to=30, increment=0.5, textvariable=self.cooldown_var,
                    width=8).grid(row=0, column=1, sticky="w", **pad)

        tk.Label(sec3, text="Volume:", bg="#16213e", fg="#e0e0e0",
                 font=("Segoe UI", 10)).grid(row=1, column=0, sticky="e", **pad)
        self.volume_var = tk.DoubleVar(value=1.0)
        vol_frame = ttk.Frame(sec3)
        vol_frame.grid(row=1, column=1, sticky="w", **pad)
        tk.Scale(vol_frame, from_=0.0, to=2.0, resolution=0.1,
                 orient="horizontal", variable=self.volume_var,
                 bg="#16213e", fg="#e0e0e0", troughcolor="#0f3460",
                 highlightthickness=0, length=160).pack(side="left")
        tk.Label(vol_frame, textvariable=self.volume_var, bg="#16213e", fg="#e94560",
                 font=("Consolas", 10)).pack(side="left", padx=6)

        # Save button

        # Controller section
        sec4 = tk.LabelFrame(frame, text=" Virtual Controller ", bg="#16213e", fg="#e94560",
                             font=("Segoe UI", 10, "bold"), bd=1, relief="groove")
        sec4.pack(fill="x", padx=12, pady=8)

        # ── Enable + type ─────────────────────────────────────────────────────
        self.ctrl_enabled_var = tk.BooleanVar(value=False)
        tk.Checkbutton(sec4, text="Enable virtual controller",
                       variable=self.ctrl_enabled_var,
                       bg="#16213e", fg="#e0e0e0", selectcolor="#0f3460",
                       activebackground="#16213e", activeforeground="#e0e0e0",
                       font=("Segoe UI", 10), command=self._on_ctrl_toggle).grid(
                       row=0, column=0, columnspan=3, sticky="w", padx=12, pady=6)

        self.ctrl_type_var = tk.StringVar(value="DS4")
        tk.Label(sec4, text="Controller type:", bg="#16213e", fg="#e0e0e0",
                 font=("Segoe UI", 10)).grid(row=1, column=0, sticky="e", padx=12, pady=4)
        ctrl_type_frame = ttk.Frame(sec4)
        ctrl_type_frame.grid(row=1, column=1, columnspan=2, sticky="w", padx=12)
        tk.Radiobutton(ctrl_type_frame, text="DS4 (PlayStation)", variable=self.ctrl_type_var, value="DS4",
                       bg="#16213e", fg="#e0e0e0", selectcolor="#0f3460",
                       activebackground="#16213e", font=("Segoe UI", 10)).pack(side="left", padx=4)
        tk.Radiobutton(ctrl_type_frame, text="Xbox 360", variable=self.ctrl_type_var, value="X360",
                       bg="#16213e", fg="#e0e0e0", selectcolor="#0f3460",
                       activebackground="#16213e", font=("Segoe UI", 10)).pack(side="left", padx=4)

        # ── Voice mic button (always Circle, locked) ──────────────────────────
        tk.Label(sec4,
                 text="Mic input button:  Circle ○  (fixed — this is how Lifeline works)",
                 bg="#16213e", fg="#79c0ff", font=("Segoe UI", 9, "bold")).grid(
                 row=2, column=0, columnspan=3, sticky="w", padx=12, pady=(6, 2))
        tk.Label(sec4,
                 text="Circle is held for the duration of every voice command automatically.",
                 bg="#16213e", fg="#888", font=("Segoe UI", 8)).grid(
                 row=3, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 6))

        # ── Voice timing ──────────────────────────────────────────────────────
        timing_lf = tk.LabelFrame(sec4, text=" Voice Timing ", bg="#16213e", fg="#aaa",
                                  font=("Segoe UI", 8), bd=1, relief="groove")
        timing_lf.grid(row=4, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 6))

        self.ctrl_full_hold_var = tk.BooleanVar(value=True)
        tk.Checkbutton(timing_lf,
                       text="Hold Circle for full audio duration  (recommended for long words)",
                       variable=self.ctrl_full_hold_var,
                       bg="#16213e", fg="#e8d44d", selectcolor="#0f3460",
                       activebackground="#16213e", activeforeground="#e8d44d",
                       font=("Segoe UI", 10, "bold"),
                       command=self._on_full_hold_toggle).grid(
                       row=0, column=0, columnspan=3, sticky="w", padx=8, pady=4)

        tk.Label(timing_lf,
                 text="[PRESS Circle]  →  pause  →  [AUDIO plays fully]  →  [RELEASE]  ← recommended",
                 bg="#16213e", fg="#888", font=("Segoe UI", 8)).grid(
                 row=1, column=0, columnspan=3, sticky="w", padx=20, pady=(0, 4))

        def _spin(parent, var, label, row, from_, to, inc, tip):
            tk.Label(parent, text=label, bg="#16213e", fg="#e0e0e0",
                     font=("Segoe UI", 10)).grid(row=row, column=0, sticky="e", padx=8, pady=3)
            f = ttk.Frame(parent)
            f.grid(row=row, column=1, sticky="w", padx=8, pady=3)
            ttk.Spinbox(f, from_=from_, to=to, increment=inc, textvariable=var,
                        width=7, format="%.2f").pack(side="left")
            tk.Label(f, text=tip, bg="#16213e", fg="#888",
                     font=("Segoe UI", 8)).pack(side="left", padx=6)

        self.ctrl_pre_delay_var = tk.DoubleVar(value=0.0)
        _spin(timing_lf, self.ctrl_pre_delay_var,
              "1. Delay before press (s):", 2, 0.0, 5.0, 0.05, "Extra wait before pressing  (usually 0.00)")

        self.ctrl_hold_before_var = tk.DoubleVar(value=0.50)
        _spin(timing_lf, self.ctrl_hold_before_var,
              "2. Pause after press (s):", 3, 0.0, 5.0, 0.05, "Hold before speaking  (recommended: 0.50)")

        self.ctrl_post_hold_var = tk.DoubleVar(value=0.0)
        _spin(timing_lf, self.ctrl_post_hold_var,
              "3. Hold after audio (s):", 4, 0.0, 5.0, 0.05, "Keep held after speaking ends  (usually 0.00)")

        self.ctrl_release_delay_var = tk.DoubleVar(value=0.0)
        _spin(timing_lf, self.ctrl_release_delay_var,
              "4. Pause after release (s):", 5, 0.0, 5.0, 0.05, "Dead-time before next command  (usually 0.00)")

        self.ctrl_timeline_var = tk.StringVar()
        tk.Label(timing_lf, textvariable=self.ctrl_timeline_var,
                 bg="#16213e", fg="#79c0ff", font=("Consolas", 8)).grid(
                 row=6, column=0, columnspan=3, sticky="w", padx=10, pady=(2, 4))

        def _update_timeline(*_):
            pre  = self.ctrl_pre_delay_var.get()
            hb   = self.ctrl_hold_before_var.get()
            ha   = self.ctrl_post_hold_var.get()
            rd   = self.ctrl_release_delay_var.get()
            full = self.ctrl_full_hold_var.get()
            audio_part = "[AUDIO...full length]" if full else "[AUDIO starts]"
            parts = []
            if pre > 0: parts.append(f"wait {pre:.2f}s")
            parts.append("[PRESS Circle]")
            if hb  > 0: parts.append(f"pause {hb:.2f}s")
            parts.append(audio_part)
            if ha  > 0: parts.append(f"hold {ha:.2f}s")
            parts.append("[RELEASE Circle]")
            if rd  > 0: parts.append(f"pause {rd:.2f}s")
            self.ctrl_timeline_var.set("  →  ".join(parts))

        for v in (self.ctrl_pre_delay_var, self.ctrl_hold_before_var,
                  self.ctrl_post_hold_var, self.ctrl_release_delay_var):
            v.trace_add("write", _update_timeline)
        self.ctrl_full_hold_var.trace_add("write", _update_timeline)
        _update_timeline()

        # ── Chat-triggered button commands ────────────────────────────────────
        chat_lf = tk.LabelFrame(sec4, text=" Chat-Triggered Button Commands ",
                                bg="#16213e", fg="#aaa", font=("Segoe UI", 8), bd=1, relief="groove")
        chat_lf.grid(row=5, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 6))

        tk.Label(chat_lf,
                 text="When someone types a trigger word in chat, the mapped button is pressed and released.",
                 bg="#16213e", fg="#888", font=("Segoe UI", 8)).grid(
                 row=0, column=0, columnspan=4, sticky="w", padx=8, pady=(4, 6))

        # PS2 buttons with Lifeline function, chat trigger word, enable toggle
        # (button_label, ps2_function, default_chat_word, default_enabled)
        CHAT_BTN_DEFS = [
            ("Square □",   "Confirm",              "confirm",  False),
            ("Cross ×",    "Cancel",               "cancel",   False),
            ("Triangle △", "Analysis/Weak spots",  "analysis", False),
            ("L1",         "Open map",              "map",      False),
            ("R1",         "Item list",             "items",    False),
            ("L2",         "Skip event",            "skip",     False),
            ("Start",      "Pause",                 "pause",    False),
            ("Select",     "Skip (menu)",           "select",   False),
        ]

        self._chat_btn_enabled = {}
        self._chat_btn_words   = {}

        tk.Label(chat_lf, text="Button", bg="#16213e", fg="#aaa",
                 font=("Segoe UI", 8, "bold"), width=12).grid(row=1, column=0, padx=4, sticky="w")
        tk.Label(chat_lf, text="Function", bg="#16213e", fg="#aaa",
                 font=("Segoe UI", 8, "bold"), width=18).grid(row=1, column=1, padx=4, sticky="w")
        tk.Label(chat_lf, text="Chat trigger word", bg="#16213e", fg="#aaa",
                 font=("Segoe UI", 8, "bold"), width=18).grid(row=1, column=2, padx=4, sticky="w")
        tk.Label(chat_lf, text="On", bg="#16213e", fg="#aaa",
                 font=("Segoe UI", 8, "bold")).grid(row=1, column=3, padx=4)

        for i, (btn_lbl, func, default_word, default_on) in enumerate(CHAT_BTN_DEFS):
            row = i + 2
            btn_key = btn_lbl.split()[0]   # "Square", "Cross", etc.

            en_var = tk.BooleanVar(value=default_on)
            wd_var = tk.StringVar(value=default_word)
            self._chat_btn_enabled[btn_key] = en_var
            self._chat_btn_words[btn_key]   = wd_var

            tk.Label(chat_lf, text=btn_lbl, bg="#16213e", fg="#f0c27f",
                     font=("Consolas", 9), width=12, anchor="w").grid(row=row, column=0, padx=8, sticky="w")
            tk.Label(chat_lf, text=func, bg="#16213e", fg="#aaaaaa",
                     font=("Segoe UI", 8), width=18, anchor="w").grid(row=row, column=1, padx=4, sticky="w")
            ttk.Entry(chat_lf, textvariable=wd_var, width=16).grid(row=row, column=2, padx=4, pady=2, sticky="w")
            tk.Checkbutton(chat_lf, variable=en_var, bg="#16213e",
                           selectcolor="#0f3460", activebackground="#16213e").grid(row=row, column=3, padx=4)

        tk.Label(chat_lf,
                 text="Trigger words are in addition to voice commands and do not hold Circle.",
                 bg="#16213e", fg="#888", font=("Segoe UI", 8)).grid(
                 row=len(CHAT_BTN_DEFS)+2, column=0, columnspan=4, sticky="w", padx=8, pady=(4, 6))

        # ── Status + test ─────────────────────────────────────────────────────
        self.ctrl_status_lbl = tk.Label(sec4, text="Status: not initialised",
                                        bg="#16213e", fg="#aaaaaa", font=("Segoe UI", 9))
        self.ctrl_status_lbl.grid(row=6, column=0, columnspan=3, sticky="w", padx=12, pady=(4, 2))

        test_btn_frame = ttk.Frame(sec4)
        test_btn_frame.grid(row=7, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 4))
        ttk.Button(test_btn_frame, text="Test Circle timing",
                   command=self._test_circle).pack(side="left", padx=(0, 6))
        ttk.Button(test_btn_frame, text="Reset to defaults",
                   command=self._reset_ctrl_timing).pack(side="left")

        tk.Label(sec4,
                 text="Requires: pip install vgamepad  +  ViGEmBus driver (https://github.com/nefarius/ViGEmBus/releases)\n"
                      "In PCSX2: assign the virtual controller to Player 1 in Settings > Controllers.",
                 bg="#16213e", fg="#999", font=("Segoe UI", 8),
                 justify="left").grid(row=8, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 6))


        # TTS section
        sec5 = tk.LabelFrame(frame, text=" Text-to-Speech (TTS) ", bg="#16213e", fg="#e94560",
                             font=("Segoe UI", 10, "bold"), bd=1, relief="groove")
        sec5.pack(fill="x", padx=12, pady=8)

        self.tts_enabled_var = tk.BooleanVar(value=False)
        tk.Checkbutton(sec5, text="Enable TTS  (synthesise words that have no audio file)",
                       variable=self.tts_enabled_var,
                       bg="#16213e", fg="#e0e0e0", selectcolor="#0f3460",
                       activebackground="#16213e", activeforeground="#e0e0e0",
                       font=("Segoe UI", 10)).grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=6)

        self.tts_always_var = tk.BooleanVar(value=False)
        tk.Checkbutton(sec5, text="Always use TTS  (ignore audio files, synthesise everything)",
                       variable=self.tts_always_var,
                       bg="#16213e", fg="#e0e0e0", selectcolor="#0f3460",
                       activebackground="#16213e", activeforeground="#e0e0e0",
                       font=("Segoe UI", 10)).grid(row=1, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 6))

        self.tts_filter_var = tk.BooleanVar(value=True)
        tk.Checkbutton(sec5, text="Filter hateful / explicit words  (blocks word from being spoken)",
                       variable=self.tts_filter_var,
                       bg="#16213e", fg="#e8d44d", selectcolor="#0f3460",
                       activebackground="#16213e", activeforeground="#e8d44d",
                       font=("Segoe UI", 10, "bold")).grid(row=2, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 6))

        tk.Label(sec5, text="TTS voice:", bg="#16213e", fg="#e0e0e0",
                 font=("Segoe UI", 10)).grid(row=3, column=0, sticky="e", padx=12, pady=4)
        self.tts_voice_var = tk.StringVar(value="Default")
        self.tts_voice_combo = ttk.Combobox(sec5, textvariable=self.tts_voice_var, width=36, state="readonly")
        self.tts_voice_combo.grid(row=3, column=1, sticky="w", padx=8, pady=4)
        ttk.Button(sec5, text="↻", width=3,
                   command=self._refresh_tts_voices).grid(row=3, column=2, padx=4)

        # Speech rate
        tk.Label(sec5, text="Speech rate (wpm):", bg="#16213e", fg="#e0e0e0",
                 font=("Segoe UI", 10)).grid(row=4, column=0, sticky="e", padx=12, pady=4)
        rate_frame = ttk.Frame(sec5)
        rate_frame.grid(row=4, column=1, columnspan=2, sticky="w", padx=8, pady=4)
        tk.Scale(rate_frame, from_=50, to=400, resolution=5, orient="horizontal",
                 variable=self.tts_rate_var, length=180,
                 bg="#16213e", fg="#e0e0e0", troughcolor="#0f3460",
                 highlightthickness=0).pack(side="left")
        tk.Label(rate_frame, textvariable=self.tts_rate_var, width=4,
                 bg="#16213e", fg="#e94560", font=("Consolas", 10)).pack(side="left", padx=4)
        tk.Label(rate_frame, text="wpm", bg="#16213e", fg="#888",
                 font=("Segoe UI", 8)).pack(side="left")

        # Gap between words
        tk.Label(sec5, text="Gap between words (s):", bg="#16213e", fg="#e0e0e0",
                 font=("Segoe UI", 10)).grid(row=5, column=0, sticky="e", padx=12, pady=4)
        gap_frame = ttk.Frame(sec5)
        gap_frame.grid(row=5, column=1, columnspan=2, sticky="w", padx=8, pady=4)
        tk.Scale(gap_frame, from_=-1.0, to=2.0, resolution=0.05, orient="horizontal",
                 variable=self.tts_gap_var, length=220,
                 bg="#16213e", fg="#e0e0e0", troughcolor="#0f3460",
                 highlightthickness=0).pack(side="left")
        tk.Label(gap_frame, textvariable=self.tts_gap_var, width=4,
                 bg="#16213e", fg="#e94560", font=("Consolas", 10)).pack(side="left", padx=4)
        tk.Label(gap_frame, text="s", bg="#16213e", fg="#888",
                 font=("Segoe UI", 8)).pack(side="left")
        tk.Label(sec5, text="Positive = pause between words  |  Negative = trim trailing silence",
                 bg="#16213e", fg="#888", font=("Segoe UI", 8)).grid(
                 row=6, column=1, columnspan=2, sticky="w", padx=8, pady=(0, 4))

        # Preview label — updates live
        self.tts_preview_var = tk.StringVar()
        tk.Label(sec5, textvariable=self.tts_preview_var,
                 bg="#16213e", fg="#79c0ff", font=("Consolas", 8)).grid(
                 row=7, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 4))

        def _update_tts_preview(*_):
            r = self.tts_rate_var.get()
            g = self.tts_gap_var.get()
            speed = "slow" if r < 100 else "fast" if r > 250 else "normal"
            if g > 0:
                gap_desc = f"+{g:.2f}s pause added"
            elif g < 0:
                gap_desc = f"{g:.2f}s trimmed from end of each word"
            else:
                gap_desc = "no gap (back-to-back)"
            self.tts_preview_var.set(
                f"Rate: {r} wpm ({speed})   |   Gap: {gap_desc}"
            )
        self.tts_rate_var.trace_add("write", _update_tts_preview)
        self.tts_gap_var.trace_add("write", _update_tts_preview)
        _update_tts_preview()

        # Test + reset row
        btn_frame = ttk.Frame(sec5)
        btn_frame.grid(row=8, column=0, columnspan=3, sticky="w", padx=12, pady=(2, 6))
        ttk.Button(btn_frame, text="Test TTS",
                   command=self._test_tts).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Reset TTS defaults",
                   command=self._reset_tts_defaults).pack(side="left")

        tk.Label(sec5,
                 text="Requires: pip install pyttsx3  |  Filter: pip install better-profanity",
                 bg="#16213e", fg="#999", font=("Segoe UI", 8)).grid(
                 row=9, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 6))

        ttk.Button(frame, text="💾 Save Settings", command=self._save_config).pack(pady=10)

        self._refresh_devices()

    def _build_commands_tab(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  📋 Commands  ")

        # ── Scrollable canvas wrapping all content ────────────────────────────
        canvas = tk.Canvas(frame, bg="#1a1a2e", highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Inner frame that holds everything
        inner = tk.Frame(canvas, bg="#1a1a2e")
        inner_window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_resize(event):
            canvas.itemconfig(inner_window, width=event.width)
        canvas.bind("<Configure>", _on_resize)

        def _on_inner_resize(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>", _on_inner_resize)

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        # Scroll only when mouse is over this canvas — no cross-tab interference
        def _enter(e):  canvas.bind_all("<MouseWheel>", _on_mousewheel)
        def _leave(e):  canvas.unbind_all("<MouseWheel>")
        canvas.bind("<Enter>", _enter)
        canvas.bind("<Leave>", _leave)

        # ── Single words ──────────────────────────────────────────────────────
        tk.Label(inner, text="Single-word commands:",
                 bg="#1a1a2e", fg="#aaa", font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(8, 2))

        cmd_frame = tk.Frame(inner, bg="#0d1117", bd=1, relief="sunken")
        cmd_frame.pack(fill="x", padx=12, pady=4)
        words = sorted(LIFELINE_COMMANDS)
        cols = 8
        for i, w in enumerate(words):
            lbl = tk.Label(cmd_frame, text=w, bg="#0d1117", fg="#79c0ff",
                           font=("Consolas", 9), width=12, anchor="w")
            lbl.grid(row=i // cols, column=i % cols, padx=2, pady=1, sticky="w")

        # ── Multi-word phrases ────────────────────────────────────────────────
        tk.Label(inner, text=f"Official multi-word phrases ({len(LIFELINE_PHRASES)})  — say the full phrase in chat to trigger:",
                 bg="#1a1a2e", fg="#aaa", font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(8, 2))

        phrase_frame = tk.Frame(inner, bg="#0d1117", bd=1, relief="sunken")
        phrase_frame.pack(fill="x", padx=12, pady=4)
        phrases = sorted(LIFELINE_PHRASES)
        pcols = 3
        for i, p in enumerate(phrases):
            lbl = tk.Label(phrase_frame, text=p, bg="#0d1117", fg="#f0c27f",
                           font=("Consolas", 9), width=36, anchor="w")
            lbl.grid(row=i // pcols, column=i % pcols, padx=4, pady=1, sticky="w")

        # ── Custom commands ───────────────────────────────────────────────────
        sec = tk.LabelFrame(inner, text=" Custom Commands ", bg="#16213e", fg="#e94560",
                            font=("Segoe UI", 10, "bold"), bd=1, relief="groove")
        sec.pack(fill="x", padx=12, pady=8)

        tk.Label(sec, text="Add extra trigger words or phrases (one per line):",
                 bg="#16213e", fg="#e0e0e0", font=("Segoe UI", 9)).pack(anchor="w", padx=6, pady=4)

        self.custom_text = scrolledtext.ScrolledText(
            sec, bg="#0d1117", fg="#90ee90", font=("Consolas", 10),
            height=6, borderwidth=0, relief="flat")
        self.custom_text.pack(fill="both", expand=True, padx=6, pady=4)

        ttk.Button(sec, text="✅ Apply Custom Commands",
                   command=self._apply_custom).pack(padx=6, pady=4)

        tk.Label(inner,
                 text="ℹ  Place audio files named exactly after the command (e.g. yes.wav, go.wav) in your audio folder.",
                 bg="#1a1a2e", fg="#888", font=("Segoe UI", 8)).pack(anchor="w", padx=12, pady=(0, 10))

    # ── Config helpers ────────────────────────────────────────────────────────
    def _apply_config(self):
        self.channel_var.set(self.cfg.get("channel", ""))
        self.oauth_var.set(self.cfg.get("oauth_token", ""))
        self.folder_var.set(self.cfg.get("audio_folder", ""))
        self.cooldown_var.set(self.cfg.get("cooldown", 1.5))
        self.volume_var.set(self.cfg.get("volume", 1.0))
        if self.cfg.get("custom_commands"):
            self.custom_text.insert("1.0", "\n".join(self.cfg["custom_commands"]))
        self._apply_custom()
        self._refresh_devices()
        # Restore controller state
        ctrl_en = self.cfg.get('ctrl_enabled', False)
        self.ctrl_enabled_var.set(ctrl_en)
        self.ctrl_pre_delay_var.set(self.cfg.get('ctrl_pre_delay', 0.0))
        self.ctrl_hold_before_var.set(self.cfg.get('ctrl_hold_before', 0.50))
        self.ctrl_post_hold_var.set(self.cfg.get('ctrl_post_hold', 0.0))
        self.ctrl_release_delay_var.set(self.cfg.get('ctrl_release_delay', 0.0))
        self.ctrl_full_hold_var.set(self.cfg.get('ctrl_full_hold', True))
        self.tts_enabled_var.set(self.cfg.get('tts_enabled', False))
        self.tts_always_var.set(self.cfg.get('tts_always', False))
        self.tts_filter_var.set(self.cfg.get('tts_filter', True))
        self.tts_rate_var.set(self.cfg.get('tts_rate', 150))
        self.tts_voice_var.set(self.cfg.get('tts_voice', 'Default'))
        self.tts_gap_var.set(self.cfg.get('tts_gap', 0.0))
        self._refresh_tts_voices()
        self._resolve_tts_voice()
        if ctrl_en:
            self._on_ctrl_toggle()
        # Restore chat button trigger words and enabled state
        saved_btns = self.cfg.get("chat_btns", {})
        for btn_key, data in saved_btns.items():
            if btn_key in self._chat_btn_enabled:
                self._chat_btn_enabled[btn_key].set(data.get("enabled", False))
                self._chat_btn_words[btn_key].set(data.get("word", ""))
        # Re-select saved device
        saved_dev = self.cfg.get("output_device", "")
        if saved_dev:
            vals = self.device_combo["values"]
            for v in vals:
                if saved_dev in v:
                    self.device_var.set(v)
                    break

    def _save_config(self):
        self.cfg.update({
            "channel": self.channel_var.get().strip(),
            "oauth_token": self.oauth_var.get().strip(),
            "audio_folder": self.folder_var.get().strip(),
            "output_device": self.device_var.get(),
            "cooldown": self.cooldown_var.get(),
            "volume": self.volume_var.get(),
            "custom_commands": [
                l.strip() for l in self.custom_text.get("1.0", "end").splitlines() if l.strip()
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
                k: {"enabled": v.get(), "word": self._chat_btn_words[k].get().strip()}
                for k, v in self._chat_btn_enabled.items()
            },
        })
        save_config(self.cfg)
        self._resolve_tts_voice()
        self._set_status("Settings saved.")
        messagebox.showinfo("Saved", "Settings saved successfully.")


    def _on_ctrl_toggle(self):
        if self.ctrl_enabled_var.get():
            prefer_ds4 = self.ctrl_type_var.get() == "DS4"
            ok, msg = self.controller.init(prefer_ds4=prefer_ds4)
            color = "#90ee90" if ok else "#ff6b6b"
            self.ctrl_status_lbl.configure(text=f"Status: {msg}", fg=color)
            if not ok:
                self.ctrl_enabled_var.set(False)
        else:
            self.controller.destroy()
            self.ctrl_status_lbl.configure(text="Status: disabled", fg="#aaaaaa")

    def _test_circle(self):
        if not self.controller.ready:
            messagebox.showwarning("Not ready", "Enable the virtual controller first.")
            return
        def _do():
            pre  = self.ctrl_pre_delay_var.get()
            hb   = self.ctrl_hold_before_var.get()
            ha   = self.ctrl_post_hold_var.get()
            rd   = self.ctrl_release_delay_var.get()
            self.log_queue.put(("command", f"Test: pre={pre:.2f}s hb={hb:.2f}s ha={ha:.2f}s rd={rd:.2f}s"))
            if pre  > 0: time.sleep(pre)
            self.controller.press_circle()
            self.log_queue.put(("command", "Test: ● Circle HELD"))
            if hb   > 0: time.sleep(hb)
            self.log_queue.put(("command", "Test: [audio would play here]"))
            time.sleep(0.4)   # simulate audio duration
            if ha   > 0: time.sleep(ha)
            self.controller.release_circle()
            self.log_queue.put(("command", "Test: ○ Circle released"))
            if rd   > 0: time.sleep(rd)
            self.log_queue.put(("command", "Test: done"))
        threading.Thread(target=_do, daemon=True).start()

    def _on_full_hold_toggle(self):
        # Just triggers timeline refresh; actual logic is in _trigger_command
        pass

    def _reset_ctrl_timing(self):
        """Reset to the community-recommended Lifeline sequence."""
        self.ctrl_pre_delay_var.set(0.0)
        self.ctrl_hold_before_var.set(0.50)   # the half-second pause
        self.ctrl_post_hold_var.set(0.0)
        self.ctrl_release_delay_var.set(0.0)
        self.ctrl_full_hold_var.set(True)

    def _refresh_tts_voices(self):
        self.tts._voices_cache = None   # force fresh query from system
        voices = self.tts.get_voices()
        vals = ["Default"] + [name for _, name in voices]
        self.tts_voice_combo["values"] = vals
        if not self.tts_voice_var.get():
            self.tts_voice_combo.current(0)

    def _trim_audio_tail(self, audio_path, trim_secs):
        """
        Return a path to a version of the audio file with `trim_secs` seconds
        removed from the end. Uses a temp file so the original is untouched.
        If trim_secs >= audio length, returns the original path unchanged.
        """
        if not HAS_AUDIO or trim_secs <= 0:
            return audio_path
        try:
            data, sr = sf.read(audio_path, dtype="float32")
            samples_to_trim = int(trim_secs * sr)
            if samples_to_trim <= 0 or samples_to_trim >= len(data):
                return audio_path
            trimmed = data[:-samples_to_trim]
            # Cache trimmed version alongside the TTS cache
            base = os.path.splitext(os.path.basename(audio_path))[0]
            out = os.path.join(self._tts_tmp_dir,
                               f"{base}_trim{int(trim_secs*1000)}ms.wav")
            sf.write(out, trimmed, sr)
            return out
        except Exception:
            return audio_path

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
        self._playback_queue.put(("TTS_Test", [word]))

    def _resolve_tts_voice(self):
        """Cache the selected voice ID so synthesis has zero lookup cost."""
        chosen = self.tts_voice_var.get()
        if not chosen or chosen == "Default":
            self.tts.voice_id = None
        else:
            for vid, vname in self.tts.get_voices():
                if vname == chosen:
                    self.tts.voice_id = vid
                    return
            self.tts.voice_id = None

    def _press_chat_button(self, btn_key):
        """Press and release a non-Circle button triggered from chat (no Circle hold)."""
        self.controller._do_button("press", btn_key)
        self.log_queue.put(("command", f"  ► Chat button: {btn_key} pressed"))
        time.sleep(0.1)
        self.controller._do_button("release", btn_key)
        self.log_queue.put(("command", f"  ► Chat button: {btn_key} released"))

    def _browse_folder(self):
        path = filedialog.askdirectory(title="Select audio files folder")
        if path:
            self.folder_var.set(path)
            self.audio.set_folder(path)

    def _refresh_devices(self):
        devices = self.audio.get_audio_devices()
        vals = ["Default"] + [f"[{i}] {name}" for i, name, ch in devices]
        self.device_combo["values"] = vals
        if not self.device_var.get():
            self.device_combo.current(0)

    def _apply_custom(self):
        custom = [
            l.strip().lower()
            for l in self.custom_text.get("1.0", "end").splitlines()
            if l.strip()
        ]
        custom_words = [w for w in custom if ' ' not in w]
        custom_phrases = [w for w in custom if ' ' in w]
        self.active_commands = set(LIFELINE_COMMANDS) | set(custom_words)
        self.active_phrases = set(LIFELINE_PHRASES) | set(custom_phrases)
        total = len(self.active_commands) + len(self.active_phrases)
        self._set_status(f"Commands active: {len(self.active_commands)} words, {len(self.active_phrases)} phrases")

    # ── Connection ────────────────────────────────────────────────────────────
    def _toggle_connect(self):
        if self.bot and self.bot.is_alive():
            self.bot.stop()
            self.bot = None
            self.connect_btn.configure(text="▶ Connect", style="Green.TButton")
            self.conn_indicator.configure(text="⬤ Offline", fg="#ff4444")
        else:
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
                on_status=lambda s: self.log_queue.put(("status", s)),
                on_raw=lambda r: None,
            )
            self.bot.start()
            self.connect_btn.configure(text="■ Disconnect", style="Red.TButton")
            self.conn_indicator.configure(text="⬤ Connecting…", fg="#ffa500")

    def _on_chat_message(self, username, message):
        """
        Extract commands from a chat message using two-pass matching:
          Pass 1 — scan for known multi-word phrases (longest match, left to right)
          Pass 2 — scan remaining text for individual command words
        A phrase like "go back" is treated as one unit; the words inside it are
        not double-counted as separate commands.
        """
        text = message.strip().lower()

        # ── Chat button scan ────────────────────────────────────────────────
        # Runs on the raw message completely independently of voice commands.
        # The trigger word does NOT need to be in LIFELINE_COMMANDS.
        _msg_words = set(re.findall(r"[a-z0-9]+", text))
        for _btn_key, _en_var in self._chat_btn_enabled.items():
            if _en_var.get():
                _trigger = self._chat_btn_words[_btn_key].get().strip().lower()
                if _trigger and all(w in _msg_words for w in _trigger.split()):
                    if self.ctrl_enabled_var.get() and self.controller.ready:
                        threading.Thread(
                            target=self._press_chat_button,
                            args=(_btn_key,),
                            daemon=True).start()
                    else:
                        self.log_queue.put(("command",
                            f"  ! {_btn_key} triggered but controller not enabled"))

        # Normalise: keep letters, digits, apostrophes and spaces
        clean = re.sub(r"[^a-z0-9' ]", " ", text)

        found = []          # list of strings (words or phrases) in order
        consumed_spans = [] # character spans already claimed by a phrase match

        # ── Pass 1: phrase matching ──────────────────────────────────────────
        # Sort phrases longest-first so "go back" beats "back" at same position
        sorted_phrases = sorted(self.active_phrases, key=len, reverse=True)
        for phrase in sorted_phrases:
            start = 0
            while True:
                # Only match whole-word boundaries
                pattern = r"(?<![a-z])" + re.escape(phrase) + r"(?![a-z])"
                m = re.search(pattern, clean[start:])
                if not m:
                    break
                abs_start = start + m.start()
                abs_end   = start + m.end()
                # Skip if this span overlaps an already-claimed phrase
                overlap = any(abs_start < e and abs_end > s
                              for s, e in consumed_spans)
                if not overlap:
                    consumed_spans.append((abs_start, abs_end))
                    found.append((abs_start, phrase))
                start = abs_end

        # ── Pass 2: individual word matching on unclaimed text ───────────────
        for m in re.finditer(r"[a-z]+", clean):
            # Skip if this character span is inside a phrase match
            if any(m.start() >= s and m.end() <= e for s, e in consumed_spans):
                continue
            w = m.group()
            if w in self.active_commands:
                found.append((m.start(), w))

        if not found:
            self.chat_queue.put((username, message, []))
            return

        # Sort by position so commands fire in the order they appeared in chat
        found.sort(key=lambda x: x[0])
        ordered = [cmd for _, cmd in found]

        # No deduplication — "hello,hello,hello" should say hello 3 times.
        # Spam protection is handled by the cooldown setting instead.
        self.chat_queue.put((username, message, ordered))

        # Cooldown check — each UNIQUE command is checked once.
        # But we allow the same word to appear multiple times in ordered.
        now = time.time()
        cooldown = self.cooldown_var.get()
        unique_cmds = dict.fromkeys(ordered)  # preserves order, dedupes for cooldown check
        if not any(now - self.last_played.get(cmd, 0) >= cooldown for cmd in unique_cmds):
            return
        for cmd in unique_cmds:
            self.last_played[cmd] = now
        # Pass the full ordered list (with repeats) to the playback queue
        eligible = ordered

        self._playback_queue.put((username, eligible))

        # Chat-triggered button presses (separate from voice — no Circle hold)
        if self.ctrl_enabled_var.get() and self.controller.ready:
            for btn_key, en_var in self._chat_btn_enabled.items():
                if en_var.get():
                    trigger = self._chat_btn_words[btn_key].get().strip().lower()
                    if trigger and trigger in [c.lower() for c in eligible]:
                        threading.Thread(
                            target=self._press_chat_button,
                            args=(btn_key,),
                            daemon=True).start()

    def _playback_worker(self):
        """
        Serialised sentence player. Circle is pressed ONCE before the first word
        and released ONCE after the last word — never between words:

            [PRESS] -> pause -> word1 -> word2 -> word3 -> [RELEASE]
        """
        while True:
            item = self._playback_queue.get()
            if item is None:
                break
            username, words = item

            if len(words) > 1:
                self.log_queue.put(("command", f"[{username}] Sentence: {' '.join(words)}"))

            # ── Resolve audio ──────────────────────────────────────────────────
            # Strategy:
            #   Single word  → file lookup then per-word TTS
            #   Multi-word   → try file per word, but any word that needs TTS
            #                  causes the WHOLE sentence to be synthesised as
            #                  one natural phrase (sounds far more human)

            always_tts = self.tts_always_var.get()
            tts_enabled = self.tts_enabled_var.get()
            use_tts = always_tts or tts_enabled

            if len(words) == 1:
                # Single word — original per-word path
                word = words[0]
                audio_path, source = self._get_audio_for_word(word)
                if audio_path is None:
                    self.log_queue.put(("command", f"[{username}] ! {word}  ({source})"))
                    continue
                playable = [(word, audio_path, source)]
            else:
                # Multi-word sentence
                # First try to resolve every word from audio files
                file_resolved = []
                needs_tts = False
                for word in words:
                    if always_tts:
                        needs_tts = True
                        break
                    path = self.audio.find_file(word)
                    if path:
                        file_resolved.append((word, path, "file"))
                    else:
                        needs_tts = True
                        break

                if not needs_tts:
                    # All words have audio files — play them individually
                    playable = file_resolved
                elif use_tts:
                    # Synthesise the entire sentence as ONE natural phrase
                    sentence = " ".join(words)
                    self.log_queue.put(("command", f"[{username}] TTS sentence: \"{sentence}\""))
                    audio_path, source = self._get_tts_audio(sentence)
                    if audio_path is None:
                        self.log_queue.put(("command", f"[{username}] ! sentence TTS failed ({source})"))
                        continue
                    # Treat the whole sentence as one playable item
                    playable = [(sentence, audio_path, source)]
                else:
                    # No TTS, some words missing files — play what we have
                    playable = []
                    for word in words:
                        path = self.audio.find_file(word)
                        if path:
                            playable.append((word, path, "file"))
                        else:
                            self.log_queue.put(("command", f"[{username}] ! {word}  (no_file)"))
                    if not playable:
                        continue

            if not playable:
                continue

            # Grab settings once for the whole sentence
            use_ctrl  = self.ctrl_enabled_var.get() and self.controller.ready
            pre       = self.ctrl_pre_delay_var.get()  if use_ctrl else 0.0
            hb        = self.ctrl_hold_before_var.get() if use_ctrl else 0.0
            ha        = self.ctrl_post_hold_var.get()   if use_ctrl else 0.0
            rd        = self.ctrl_release_delay_var.get() if use_ctrl else 0.0
            full_hold = self.ctrl_full_hold_var.get()   if use_ctrl else False

            dev_str   = self.device_var.get()
            dev_index = None
            if dev_str and dev_str != "Default":
                try:
                    dev_index = int(dev_str.split("]")[0].lstrip("["))
                except Exception:
                    dev_index = None
            vol = self.volume_var.get()

            # 1. Pre-press delay
            if pre > 0:
                time.sleep(pre)

            # 2. Press Circle ONCE for the whole sentence
            if use_ctrl:
                self.controller.press_circle()
                self.log_queue.put(("command", f"  ● Circle HELD  ({len(playable)} word(s))"))

            # 3. Pause before first word
            if hb > 0:
                time.sleep(hb)

            # 4. Play every word back-to-back, Circle stays held throughout
            word_gap = self.tts_gap_var.get()
            for i, (word, audio_path, source) in enumerate(playable):
                src_label = "TTS" if source == "tts" else os.path.basename(audio_path)
                self.log_queue.put(("command", f"[{username}] ▶ {word}  ({src_label})"))
                self.play_count += 1

                done_event = threading.Event()

                def _done(ok, err, _w=word):
                    if not ok:
                        self.log_queue.put(("error", f"Audio error for '{_w}': {err}"))
                    done_event.set()

                # Negative gap = trim silence from end of audio before playing
                trimmed_path = audio_path
                if word_gap < 0:
                    trimmed_path = self._trim_audio_tail(audio_path, -word_gap)

                self.audio.play(trimmed_path, device_index=dev_index, volume=vol, callback=_done)
                done_event.wait()  # block until this word finishes before next

                # Positive gap = insert silence between words (not after the last)
                if word_gap > 0 and i < len(playable) - 1:
                    time.sleep(word_gap)

            # 5. Post-audio hold (Circle still held)
            if ha > 0:
                time.sleep(ha)

            # 6. Release Circle ONCE after all words are done
            if use_ctrl:
                self.controller.release_circle()
                self.log_queue.put(("command", f"  ○ Circle released"))

            # 7. Post-release pause before next sentence
            if rd > 0:
                time.sleep(rd)

    def _get_tts_audio(self, text):
        """
        Synthesise `text` (one word OR a full sentence) to a WAV file via TTS.
        Returns (path, "tts") or (None, reason).
        Applies voice filter to every word in text before synthesising.
        """
        if not HAS_TTS:
            return None, "no_tts"

        # Block words assigned as chat button triggers — they are controller
        # inputs, not voice commands, and must never be spoken.
        for _btn_key, _en_var in self._chat_btn_enabled.items():
            if _en_var.get():
                _trigger = self._chat_btn_words[_btn_key].get().strip().lower()
                if _trigger:
                    # Block if the text IS the trigger or CONTAINS the trigger
                    text_words = set(re.findall(r"[a-z0-9]+", text.lower()))
                    trigger_words = set(_trigger.split())
                    if trigger_words and trigger_words.issubset(text_words):
                        self.log_queue.put(("command",
                            f"  ⛔ '{text}' blocked — matches chat button trigger '{_trigger}'"))
                        return None, "chat_btn_trigger"

        # Filter check — block if any word in the text is dirty
        if self.tts_filter_var.get():
            for w in text.split():
                if not self.word_filter.is_clean(w):
                    self.log_queue.put(("command", f"  ⛔ '{w}' blocked by word filter"))
                    return None, "filtered"

        # Use the full text as the cache key (spaces -> underscores for filename)
        safe_name = re.sub(r"[^a-z0-9_]", "_", text.lower().strip())[:60]
        tmp = os.path.join(self._tts_tmp_dir, f"tts_{safe_name}.wav")

        # Set voice properties (rate is cheap; voice_id already resolved at save time)
        self.tts.rate = self.tts_rate_var.get()

        path = self.tts.synthesise(text, tmp)
        if path:
            return path, "tts"
        return None, "tts_failed"

    def _get_audio_for_word(self, word):
        """
        Return a path to an audio file for this word.
        Priority: 1) audio folder file  2) TTS synthesis  3) None
        """
        always_tts = self.tts_always_var.get()
        tts_enabled = self.tts_enabled_var.get()

        if not always_tts:
            path = self.audio.find_file(word)
            if path:
                return path, "file"

        if always_tts or tts_enabled:
            return self._get_tts_audio(word)

        return None, "no_file"

    def _play_one_word(self, username, word):
        """Delegates to the worker queue so single words use the same sentence path."""
        self._playback_queue.put((username, [word]))

    # Legacy single-command entry point (kept for test button etc.)
    def _trigger_command(self, username, command):
        self._playback_queue.put((username, [command]))

    # ── Queue polling / UI updates ────────────────────────────────────────────
    def _poll_queues(self):
        # Process log queue
        while not self.log_queue.empty():
            kind, msg = self.log_queue.get_nowait()
            if kind == "status":
                self._set_status(msg)
                if "Connected" in msg:
                    self.conn_indicator.configure(text="⬤ Live", fg="#00ff88")
                elif "Disconnected" in msg or "Failed" in msg:
                    self.conn_indicator.configure(text="⬤ Offline", fg="#ff4444")
                    self.connect_btn.configure(text="▶ Connect", style="Green.TButton")
            elif kind == "command":
                self._append_cmd(msg)
                self.count_var.set(str(self.play_count))
            elif kind == "error":
                self._append_cmd(f"⚠ {msg}", color="#ff6b6b")

        # Process chat queue
        while not self.chat_queue.empty():
            username, message, cmds = self.chat_queue.get_nowait()
            ts = datetime.now().strftime("%H:%M:%S")
            self.chat_box.configure(state="normal")
            self.chat_box.insert("end", f"[{ts}] ", "")
            self.chat_box.insert("end", f"{username}", "user")
            self.chat_box.insert("end", ": ")
            # Highlight command words
            if cmds:
                remaining = message
                for cmd in cmds:
                    idx = remaining.lower().find(cmd)
                    if idx >= 0:
                        self.chat_box.insert("end", remaining[:idx])
                        self.chat_box.insert("end", remaining[idx:idx+len(cmd)], "cmd")
                        remaining = remaining[idx+len(cmd):]
                self.chat_box.insert("end", remaining + "\n")
            else:
                self.chat_box.insert("end", message + "\n")
            self.chat_box.configure(state="disabled")
            self.chat_box.see("end")

        self.after(80, self._poll_queues)

    def _append_cmd(self, text, color="#90ee90"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.cmd_box.configure(state="normal")
        self.cmd_box.insert("end", f"[{ts}] {text}\n")
        self.cmd_box.configure(state="disabled")
        self.cmd_box.see("end")

    def _clear_log(self):
        self.chat_box.configure(state="normal")
        self.chat_box.delete("1.0", "end")
        self.chat_box.configure(state="disabled")
        self.cmd_box.configure(state="normal")
        self.cmd_box.delete("1.0", "end")
        self.cmd_box.configure(state="disabled")

    def _set_status(self, text):
        self.status_var.set(text)

    def on_closing(self):
        if self.bot:
            self.bot.stop()
        self.controller.destroy()
        self._playback_queue.put(None)  # stop worker
        self.tts.stop()
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
