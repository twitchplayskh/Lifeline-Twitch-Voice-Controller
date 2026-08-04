#!/usr/bin/env python3
"""
Lifeline Twitch Voice Controller — entry point.

Connects to Twitch chat, listens for Lifeline commands, and plays them back
through a virtual mic (with an optional virtual-gamepad button hold).
"""

from lifeline_bot.gui import App


def main():
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
