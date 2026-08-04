"""Minimal Twitch IRC client — just enough to read chat messages."""

import logging
import re
import socket
import threading

logger = logging.getLogger(__name__)

_PRIVMSG_RE = re.compile(r":(\w+)!\w+@\S+ PRIVMSG #\S+ :(.+)")


class TwitchBot(threading.Thread):
    """
    Connects to Twitch IRC as a daemon thread and forwards chat messages
    to a callback. Runs until `stop()` is called or the socket errors out.
    """

    IRC_HOST = "irc.chat.twitch.tv"
    IRC_PORT = 6667
    SOCKET_TIMEOUT_SECONDS = 300

    def __init__(self, channel, oauth_token, on_command, on_status, on_raw_line=None):
        """
        on_command(username, message): called for every chat message, on its
            own daemon thread (so a slow handler never blocks the IRC loop).
        on_status(text): called with human-readable connection status updates.
        on_raw_line(line): optional, called with every raw IRC line received.
        """
        super().__init__(daemon=True)
        self.channel = channel.lower().lstrip("#")
        self.oauth_token = oauth_token
        self.on_command = on_command
        self.on_status = on_status
        self.on_raw_line = on_raw_line or (lambda line: None)
        self._stop_event = threading.Event()
        self._socket = None

    def send_raw(self, message: str) -> None:
        """Send a raw IRC line. Silently drops the message if disconnected."""
        if not self._socket:
            return
        try:
            self._socket.send((message + "\r\n").encode("utf-8"))
        except OSError as error:
            logger.debug("Failed to send IRC line %r: %s", message, error)

    def run(self):
        self.on_status("Connecting to Twitch IRC…")
        try:
            self._connect_and_authenticate()
            self.on_status(f"Connected to #{self.channel}")
            self._receive_loop()
        except OSError as error:
            self.on_status(f"Failed to connect: {error}")
        finally:
            if self._socket:
                self._socket.close()
            self.on_status("Disconnected.")

    def _connect_and_authenticate(self):
        self._socket = socket.socket()
        self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._socket.connect((self.IRC_HOST, self.IRC_PORT))
        self._socket.settimeout(self.SOCKET_TIMEOUT_SECONDS)
        self.send_raw(f"PASS oauth:{self.oauth_token}")
        self.send_raw("NICK lifeline_bot")
        self.send_raw(f"JOIN #{self.channel}")

    def _receive_loop(self):
        buffer = ""
        while not self._stop_event.is_set():
            try:
                data = self._socket.recv(8192).decode("utf-8", errors="ignore")
            except socket.timeout:
                # Twitch expects periodic activity or it will drop us.
                self.send_raw("PING :tmi.twitch.tv")
                continue
            except OSError as error:
                self.on_status(f"Connection error: {error}")
                return

            if not data:
                self.on_status("Connection closed by server.")
                return

            buffer += data
            while "\r\n" in buffer:
                line, buffer = buffer.split("\r\n", 1)
                self.on_raw_line(line)
                self._handle_line(line)

    def _handle_line(self, line: str):
        if line.startswith("PING"):
            self.send_raw("PONG :tmi.twitch.tv")
            return

        match = _PRIVMSG_RE.match(line)
        if not match:
            return

        username, message = match.group(1), match.group(2).strip()
        # Fire-and-forget: never block the IRC receive loop on slow handlers.
        threading.Thread(
            target=self.on_command, args=(username, message), daemon=True
        ).start()

    def stop(self):
        self._stop_event.set()
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
