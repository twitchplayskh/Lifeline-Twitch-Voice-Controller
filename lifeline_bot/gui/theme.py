"""
Shared color palette and fonts for the GUI.

The original code repeated hex colors like "#1a1a2e" and "#16213e" close to
150 times across widget-construction calls. Centralizing them here means a
color change is a one-line edit instead of a find-and-replace across the
whole file, and the palette's structure (background / accent / text roles)
is visible at a glance.
"""

# Backgrounds
BG_WINDOW = "#1a1a2e"       # root window / tab backgrounds
BG_PANEL = "#16213e"        # LabelFrame / section backgrounds
BG_INPUT = "#0f3460"        # entry/scale trough fill
BG_LOG = "#0d1117"          # chat/command log backgrounds

# Text
FG_TEXT = "#e0e0e0"         # default label text
FG_MUTED = "#aaaaaa"        # secondary / hint text
FG_DIM = "#888888"          # tertiary hint text
FG_ACCENT = "#e94560"       # brand accent (headings, active tab)
FG_ACCENT_ALT = "#f0c27f"   # secondary accent (phrases, commands)
FG_LINK = "#79c0ff"         # informational highlights
FG_SUCCESS = "#90ee90"      # success / connected state
FG_WARNING = "#e8d44d"      # caution labels (filters, timing)
FG_ERROR = "#ff6b6b"        # error state
FG_ERROR_STRONG = "#ff4444" # offline / disconnected indicator

FONT_LABEL = ("Segoe UI", 10)
FONT_LABEL_BOLD = ("Segoe UI", 10, "bold")
FONT_HINT = ("Segoe UI", 8)
FONT_HEADING = ("Segoe UI", 11, "bold")
FONT_MONO = ("Consolas", 9)
FONT_MONO_BOLD = ("Consolas", 9, "bold")
FONT_MONO_LARGE = ("Consolas", 10)
