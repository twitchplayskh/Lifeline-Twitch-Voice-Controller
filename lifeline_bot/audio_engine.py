"""Audio file lookup and device playback (via sounddevice/soundfile)."""

import logging
import os
import threading

logger = logging.getLogger(__name__)

try:
    import numpy as np
    import sounddevice as sd
    import soundfile as sf

    HAS_AUDIO = True
except Exception:  # noqa: BLE001 - missing package OR missing native lib (e.g. PortAudio)
    HAS_AUDIO = False

AUDIO_EXTENSIONS = (".wav", ".mp3", ".ogg", ".flac", ".aiff")
DEFAULT_SAMPLE_RATE = 44100


def resample_audio(data, source_rate: int, target_rate: int):
    """Linearly resample `data` from `source_rate` to `target_rate` Hz."""
    if source_rate == target_rate:
        return data

    ratio = target_rate / source_rate
    original_length = data.shape[0]
    new_length = int(original_length * ratio)

    source_positions = np.linspace(0, original_length - 1, new_length)
    lower_indices = np.floor(source_positions).astype(int)
    upper_indices = np.minimum(lower_indices + 1, original_length - 1)
    fractional = source_positions - lower_indices
    if data.ndim > 1:
        fractional = fractional[:, np.newaxis]

    resampled = data[lower_indices] + fractional * (data[upper_indices] - data[lower_indices])
    return resampled.astype(np.float32)


class AudioEngine:
    """Finds command audio files and plays them through a chosen output device."""

    def __init__(self):
        self.audio_folder = ""
        self._file_lookup_cache = {}  # command word -> resolved path (or None)

    def set_folder(self, folder: str) -> None:
        """Point the engine at a new folder of command audio files."""
        self.audio_folder = folder
        self._file_lookup_cache.clear()

    def get_audio_devices(self):
        """Return [(index, name, output_channels), ...] for playback devices."""
        if not HAS_AUDIO:
            return []
        try:
            devices = sd.query_devices()
        except Exception as error:  # noqa: BLE001 - PortAudio raises varied types
            logger.warning("Could not query audio devices: %s", error)
            return []
        return [
            (index, device["name"], device["max_output_channels"])
            for index, device in enumerate(devices)
            if device["max_output_channels"] > 0
        ]

    def find_file(self, command: str):
        """
        Look up the audio file for `command` (e.g. "go" -> ".../go.wav").
        Tries each supported extension, in both original and upper case.
        Result (including misses) is cached until `set_folder` is called.
        """
        if command in self._file_lookup_cache:
            return self._file_lookup_cache[command]

        path = self._search_for_file(command)
        self._file_lookup_cache[command] = path
        return path

    def _search_for_file(self, command: str):
        if not self.audio_folder or not os.path.isdir(self.audio_folder):
            return None
        for candidate_name in (command, command.upper()):
            for extension in AUDIO_EXTENSIONS:
                candidate_path = os.path.join(self.audio_folder, candidate_name + extension)
                if os.path.exists(candidate_path):
                    return candidate_path
        return None

    def _device_sample_rate(self, device_index):
        try:
            info = sd.query_devices(kind="output") if device_index is None else sd.query_devices(device_index)
            return int(info["default_samplerate"])
        except Exception as error:  # noqa: BLE001 - fall back to a sane default
            logger.debug("Could not read sample rate for device %s: %s", device_index, error)
            return DEFAULT_SAMPLE_RATE

    def play(self, filepath, device_index=None, volume=1.0, callback=None):
        """
        Play `filepath` asynchronously on a background thread.
        `callback(success: bool, error_message: str | None)` fires when done.
        """
        if not HAS_AUDIO:
            if callback:
                callback(False, "sounddevice/soundfile not installed")
            return

        threading.Thread(
            target=self._play_blocking,
            args=(filepath, device_index, volume, callback),
            daemon=True,
        ).start()

    def _play_blocking(self, filepath, device_index, volume, callback):
        try:
            data, sample_rate = sf.read(filepath, dtype="float32")
            data = data * volume

            # Resample to the device's native rate — mismatched rates raise
            # "Invalid sample rate" errors on some drivers/devices.
            device_rate = self._device_sample_rate(device_index)
            if sample_rate != device_rate:
                data = resample_audio(data, sample_rate, device_rate)
                sample_rate = device_rate

            sd.play(data, sample_rate, device=device_index, blocking=True)
            if callback:
                callback(True, None)
        except Exception as error:  # noqa: BLE001 - third-party audio libs raise varied types
            logger.warning("Playback failed for %s: %s", filepath, error)
            if callback:
                callback(False, str(error))
