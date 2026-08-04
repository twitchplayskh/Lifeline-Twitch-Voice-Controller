"""Text-to-speech synthesis, run on a dedicated worker thread."""

import logging
import os
import queue
import threading

logger = logging.getLogger(__name__)

try:
    import pyttsx3

    HAS_TTS = True
except Exception:  # noqa: BLE001 - missing package OR missing native TTS backend
    HAS_TTS = False

DEFAULT_RATE_WPM = 150
SYNTHESIS_TIMEOUT_SECONDS = 30


class TTSEngine:
    """
    Wraps pyttsx3 to synthesize text to a WAV file (playback is then handled
    by AudioEngine, so device routing/resampling still applies uniformly).

    pyttsx3 must run on the same thread it was initialized on, so all
    synthesis jobs are funneled through one dedicated worker thread via a
    queue, rather than being called directly from arbitrary caller threads.
    """

    def __init__(self):
        self.rate = DEFAULT_RATE_WPM
        self.volume = 1.0
        self.voice_id = None  # None = system default voice
        self._job_queue = queue.Queue()
        self._voices_cache = None
        self._worker_thread = threading.Thread(target=self._run_worker, daemon=True)
        self._worker_thread.start()

    def synthesise(self, text: str, out_path: str):
        """Blocking: render `text` to `out_path` as a WAV file. Returns the
        path on success, or None on failure/timeout."""
        if not HAS_TTS:
            return None

        done_event = threading.Event()
        result_holder = []
        self._job_queue.put((text, out_path, done_event, result_holder))
        done_event.wait(timeout=SYNTHESIS_TIMEOUT_SECONDS)
        return result_holder[0] if result_holder else None

    def get_voices(self):
        """Return [(voice_id, voice_name), ...] for the settings dropdown."""
        if self._voices_cache is not None:
            return self._voices_cache
        if not HAS_TTS:
            return []
        try:
            engine = pyttsx3.init()
            try:
                self._voices_cache = [(v.id, v.name) for v in engine.getProperty("voices")]
            finally:
                engine.stop()
            return self._voices_cache
        except Exception as error:  # noqa: BLE001 - pyttsx3 backends vary by OS
            logger.warning("Could not list TTS voices: %s", error)
            return []

    def stop(self):
        """Shut down the worker thread."""
        self._job_queue.put(None)

    def _run_worker(self):
        """
        Process synthesis jobs one at a time. A fresh pyttsx3 engine is
        created and destroyed for EACH job — this is intentional. pyttsx3's
        internal COM/event state becomes corrupted after the first
        runAndWait() call on Windows, causing subsequent save_to_file calls
        to silently fail. Re-initializing every job is the only reliable fix.
        """
        while True:
            job = self._job_queue.get()
            if job is None:
                return
            text, out_path, done_event, result_holder = job
            result_holder.append(self._synthesise_one(text, out_path))
            done_event.set()

    def _synthesise_one(self, text: str, out_path: str):
        if not HAS_TTS:
            return None

        engine = None
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", self.rate)
            engine.setProperty("volume", self.volume)
            if self.voice_id:
                engine.setProperty("voice", self.voice_id)

            # Delete any stale file so we can detect whether save actually happened.
            if os.path.exists(out_path):
                os.remove(out_path)

            engine.save_to_file(text, out_path)
            engine.runAndWait()
            return out_path if os.path.exists(out_path) else None
        except Exception as error:  # noqa: BLE001 - pyttsx3 backends vary by OS
            logger.warning("TTS synthesis failed for %r: %s", text, error)
            return None
        finally:
            if engine is not None:
                try:
                    engine.stop()
                except Exception:  # noqa: BLE001 - best-effort cleanup
                    pass
