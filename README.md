# Lifeline Twitch Voice Controller

Run with:

```
pip install -r requirements.txt   # all optional, see comments in the file
python main.py
```

## Layout

```
main.py                              entry point
lifeline_bot/
    commands.py                      vocabulary data + CommandMatcher
    config.py                        config.json load/save
    twitch_bot.py                    Twitch IRC client
    audio_engine.py                  audio file lookup + device playback
    tts_engine.py                    pyttsx3-based text-to-speech
    word_filter.py                   profanity / hate-word screening
    controller_engine.py             virtual DS4/Xbox360 gamepad
    playback_service.py              turns a command into audio + button presses
    gui/
        theme.py                     shared colors/fonts
        widgets.py                   reusable widget-building helpers
        main_tab.py                  Live Feed tab (connect, chat, logs)
        settings_tab.py              Settings tab
        commands_tab.py              Commands reference tab
        app.py                       top-level Tk App class
```

Settings are still stored in `config.json` next to `main.py`, in the same
format as before.
