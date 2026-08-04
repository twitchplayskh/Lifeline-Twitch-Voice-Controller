"""
Path resolution that works both when running as a normal Python script and
when frozen into a PyInstaller onefile .exe.

PyInstaller onefile builds extract to a temporary directory at startup
(`sys._MEIPASS`), so anything computed from `__file__` (like the original
`os.path.dirname(__file__)`) would point *inside that temp folder* and be
wiped on every run — silently discarding config.json and the TTS cache
each time the app closes. `app_base_dir()` instead resolves to the folder
containing the .exe (or, when not frozen, the project root next to
main.py), so settings persist across runs either way.
"""

import os
import sys


def app_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # lifeline_bot/paths.py -> project root is one level up.
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
