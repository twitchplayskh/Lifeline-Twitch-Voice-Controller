"""
Turns a recognized command (or sentence of commands) into actual sound and
button presses.

This used to be split across several GUI methods (`_playback_worker`,
`_get_tts_audio`, `_get_audio_for_word`, `_trim_audio_tail`) that reached
directly into Tkinter variables. Here it's a standalone service: the GUI
hands it a settings snapshot per sentence and gets callbacks for logging,
so the sequencing/audio-resolution logic can be read (and tested) without
any Tkinter involved.
"""

import os
import queue
import re
import threading
import time
from dataclasses import dataclass

from .audio_engine import AudioEngine, HAS_AUDIO
from .controller_engine import ControllerEngine
from .tts_engine import TTSEngine, HAS_TTS
from .word_filter import WordFilter

try:
    import soundfile as sf
except Exception:  # noqa: BLE001 - missing package OR missing native lib
    sf = None

_FILENAME_SAFE_RE = re.compile(r"[^a-z0-9_]")
_WORD_RE = re.compile(r"[a-z0-9]+")


@dataclass
class PlaybackSettings:
    """Snapshot of everything needed to play one sentence."""

    # Controller (button-hold) timing
    use_controller: bool = False
    pre_press_delay: float = 0.0
    hold_before_audio: float = 0.5
    hold_after_audio: float = 0.0
    release_delay: float = 0.0

    # Audio output
    device_index: int = None
    volume: float = 1.0

    # TTS behavior
    tts_always: bool = False
    tts_enabled: bool = False
    tts_filter_enabled: bool = True
    tts_rate_wpm: int = 150
    word_gap_seconds: float = 0.0  # negative = trim silence, positive = insert pause

    @property
    def tts_available(self) -> bool:
        return self.tts_always or self.tts_enabled


@dataclass
class PlayableItem:
    """One piece of audio ready to play, with a label for logging."""

    label: str          # the word or sentence text, for log messages
    audio_path: str
    source: str          # "file" or "tts"


class PlaybackService:
    """
    Owns a queue + worker thread that plays recognized commands one sentence
    at a time (serialized, so multi-word sentences play in order and a
    controller button is only pressed once per sentence, not once per word).
    """

    def __init__(
        self,
        audio_engine: AudioEngine,
        tts_engine: TTSEngine,
        controller_engine: ControllerEngine,
        word_filter: WordFilter,
        tts_cache_dir: str,
        log_callback,
        get_settings,
        get_blocked_trigger_phrases=lambda: (),
        on_word_played=lambda: None,
    ):
        """
        log_callback(kind, message): kind is "command" or "error".
        get_settings(): called fresh for every sentence, returns PlaybackSettings.
        get_blocked_trigger_phrases(): returns trigger phrases (chat-button
            words) that must never be spoken, since they're controller
            inputs rather than voice commands.
        on_word_played(): called once for every word/sentence actually sent
            to playback (lets the GUI keep a running play counter).
        """
        self.audio = audio_engine
        self.tts = tts_engine
        self.controller = controller_engine
        self.word_filter = word_filter
        self._tts_cache_dir = tts_cache_dir
        self._log = log_callback
        self._get_settings = get_settings
        self._get_blocked_trigger_phrases = get_blocked_trigger_phrases
        self._on_word_played = on_word_played

        os.makedirs(tts_cache_dir, exist_ok=True)
        self._queue = queue.Queue()
        self._thread = threading.Thread(target=self._run_worker, daemon=True)
        self._thread.start()

    def enqueue(self, username: str, words: list) -> None:
        """Queue a recognized word or ordered list of words for playback."""
        self._queue.put((username, words))

    def stop(self) -> None:
        self._queue.put(None)

    # ── Worker loop ──────────────────────────────────────────────────────
    def _run_worker(self):
        while True:
            item = self._queue.get()
            if item is None:
                return
            username, words = item
            try:
                self._play_sentence(username, words)
            except Exception as error:  # noqa: BLE001 - never let one bad sentence kill the worker
                self._log("error", f"Playback failed for [{username}] {words}: {error}")

    def _play_sentence(self, username: str, words: list):
        settings = self._get_settings()

        if len(words) > 1:
            self._log("command", f"[{username}] Sentence: {' '.join(words)}")

        playable_items = self._resolve_playable_items(username, words, settings)
        if not playable_items:
            return

        self._run_playback_sequence(username, playable_items, settings)

    # ── Resolving words/sentences to actual audio ───────────────────────
    def _resolve_playable_items(self, username, words, settings):
        """
        Strategy:
          Single word  -> file lookup, else TTS for that word.
          Multi word   -> try a file per word; if ANY word needs TTS, the
                          WHOLE sentence is synthesized as one natural
                          phrase instead (sounds far more human than
                          concatenated single-word TTS clips).
        """
        if len(words) == 1:
            return self._resolve_single_word(username, words[0], settings)
        return self._resolve_sentence(username, words, settings)

    def _resolve_single_word(self, username, word, settings):
        audio_path, source = self._get_audio_for_word(word, settings)
        if audio_path is None:
            self._log("command", f"[{username}] ! {word}  ({source})")
            return []
        return [PlayableItem(word, audio_path, source)]

    def _resolve_sentence(self, username, words, settings):
        file_items, all_words_have_files = self._resolve_words_from_files(words, settings)
        if all_words_have_files:
            return file_items

        if settings.tts_available:
            return self._resolve_sentence_as_tts(username, words, settings)

        return self._resolve_partial_from_files(username, words)

    def _resolve_words_from_files(self, words, settings):
        """Try to resolve every word to an audio file. Stops early (and
        reports failure) if `tts_always` is set or a word has no file."""
        if settings.tts_always:
            return [], False

        items = []
        for word in words:
            path = self.audio.find_file(word)
            if not path:
                return [], False
            items.append(PlayableItem(word, path, "file"))
        return items, True

    def _resolve_sentence_as_tts(self, username, words, settings):
        sentence = " ".join(words)
        self._log("command", f'[{username}] TTS sentence: "{sentence}"')
        audio_path, source = self._get_tts_audio(sentence, settings)
        if audio_path is None:
            self._log("command", f"[{username}] ! sentence TTS failed ({source})")
            return []
        return [PlayableItem(sentence, audio_path, source)]

    def _resolve_partial_from_files(self, username, words):
        """No TTS available — play whatever words do have audio files."""
        items = []
        for word in words:
            path = self.audio.find_file(word)
            if path:
                items.append(PlayableItem(word, path, "file"))
            else:
                self._log("command", f"[{username}] ! {word}  (no_file)")
        return items

    def _get_audio_for_word(self, word: str, settings: PlaybackSettings):
        """Priority: 1) audio folder file  2) TTS synthesis  3) nothing."""
        if not settings.tts_always:
            path = self.audio.find_file(word)
            if path:
                return path, "file"

        if settings.tts_available:
            return self._get_tts_audio(word, settings)

        return None, "no_file"

    def _get_tts_audio(self, text: str, settings: PlaybackSettings):
        """Synthesize `text` (a word or full sentence) to a cached WAV file."""
        if not HAS_TTS:
            return None, "no_tts"

        blocked_reason = self._blocked_reason(text, settings)
        if blocked_reason:
            return None, blocked_reason

        cache_path = self._tts_cache_path(text)
        self.tts.rate = settings.tts_rate_wpm
        result_path = self.tts.synthesise(text, cache_path)
        return (result_path, "tts") if result_path else (None, "tts_failed")

    def _blocked_reason(self, text: str, settings: PlaybackSettings):
        """Return a reason string if `text` must not be spoken, else None."""
        text_words = set(_WORD_RE.findall(text.lower()))

        for trigger_phrase in self._get_blocked_trigger_phrases():
            trigger_words = set(trigger_phrase.split())
            if trigger_words and trigger_words.issubset(text_words):
                self._log(
                    "command",
                    f"  \u26d4 '{text}' blocked \u2014 matches chat button trigger '{trigger_phrase}'",
                )
                return "chat_btn_trigger"

        if settings.tts_filter_enabled:
            for word in text.split():
                if not self.word_filter.is_clean(word):
                    self._log("command", f"  \u26d4 '{word}' blocked by word filter")
                    return "filtered"

        return None

    def _tts_cache_path(self, text: str) -> str:
        safe_name = _FILENAME_SAFE_RE.sub("_", text.lower().strip())[:60]
        return os.path.join(self._tts_cache_dir, f"tts_{safe_name}.wav")

    def trim_audio_tail(self, audio_path: str, trim_seconds: float) -> str:
        """
        Return a path to a copy of `audio_path` with `trim_seconds` removed
        from the end (used for negative word-gap settings). Falls back to
        the original path if trimming isn't possible.
        """
        if not HAS_AUDIO or trim_seconds <= 0:
            return audio_path
        try:
            data, sample_rate = sf.read(audio_path, dtype="float32")
            samples_to_trim = int(trim_seconds * sample_rate)
            if samples_to_trim <= 0 or samples_to_trim >= len(data):
                return audio_path

            trimmed_data = data[:-samples_to_trim]
            base_name = os.path.splitext(os.path.basename(audio_path))[0]
            output_path = os.path.join(
                self._tts_cache_dir, f"{base_name}_trim{int(trim_seconds * 1000)}ms.wav"
            )
            sf.write(output_path, trimmed_data, sample_rate)
            return output_path
        except Exception:  # noqa: BLE001 - fall back to untrimmed audio on any failure
            return audio_path

    # ── Sequencing: press -> play words -> release ──────────────────────
    def _run_playback_sequence(self, username, playable_items, settings):
        use_controller = settings.use_controller and self.controller.ready

        if settings.pre_press_delay > 0:
            time.sleep(settings.pre_press_delay)

        if use_controller:
            self.controller.press_button()
            self._log("command", f"  \u25cf Circle HELD  ({len(playable_items)} word(s))")

        if settings.hold_before_audio > 0:
            time.sleep(settings.hold_before_audio)

        self._play_words_back_to_back(username, playable_items, settings)

        if settings.hold_after_audio > 0:
            time.sleep(settings.hold_after_audio)

        if use_controller:
            self.controller.release_button()
            self._log("command", "  \u25cb Circle released")

        if settings.release_delay > 0:
            time.sleep(settings.release_delay)

    def _play_words_back_to_back(self, username, playable_items, settings):
        word_gap = settings.word_gap_seconds
        last_index = len(playable_items) - 1

        for index, item in enumerate(playable_items):
            source_label = "TTS" if item.source == "tts" else os.path.basename(item.audio_path)
            self._log("command", f"[{username}] \u25b6 {item.label}  ({source_label})")
            self._on_word_played()

            audio_path = item.audio_path
            if word_gap < 0:
                audio_path = self.trim_audio_tail(item.audio_path, -word_gap)

            self._play_and_wait(audio_path, settings)

            if word_gap > 0 and index < last_index:
                time.sleep(word_gap)

    def _play_and_wait(self, audio_path, settings):
        done_event = threading.Event()

        def on_finished(success, error_message):
            if not success:
                self._log("error", f"Audio error for '{audio_path}': {error_message}")
            done_event.set()

        self.audio.play(
            audio_path, device_index=settings.device_index, volume=settings.volume, callback=on_finished
        )
        done_event.wait()
