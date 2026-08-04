"""
Lifeline Twitch Voice Controller
================================

Connects to Twitch chat, recognizes commands from the PS2 game *Lifeline*,
and plays them back as audio (file or TTS) — optionally holding a virtual
gamepad button so the game "hears" the player.

Package layout:
    commands.py           Static word/phrase data + CommandMatcher
    config.py             Load/save of config.json
    twitch_bot.py          Twitch IRC client (runs on its own thread)
    audio_engine.py        Audio file lookup + playback (sounddevice/soundfile)
    tts_engine.py           Text-to-speech synthesis (pyttsx3)
    word_filter.py          Profanity / hate-word screening
    controller_engine.py    Virtual gamepad (vgamepad)
    playback_service.py     Turns a recognized command into audio + button
                             presses; the "business logic" that used to live
                             inside the GUI class.
    gui/                    Tkinter presentation layer
"""

__version__ = "2.0.0"
