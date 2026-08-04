"""
Virtual DS4 / Xbox360 gamepad control, used to hold a button (normally
Circle) while Lifeline "listens" through the virtual mic.

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

import logging
import threading

logger = logging.getLogger(__name__)

try:
    import vgamepad as vg

    HAS_GAMEPAD = True
except Exception:  # noqa: BLE001 - missing package OR missing ViGEmBus driver
    HAS_GAMEPAD = False

TRIGGER_PRESSED_VALUE = 255
TRIGGER_RELEASED_VALUE = 0

# PS2 label -> (DS4 button attr or None, Xbox360 button attr or None, is_axis_trigger)
BUTTON_MAP = {
    "Circle":   ("DS4_BUTTON_CIRCLE",         "XUSB_GAMEPAD_B",              False),
    "Square":   ("DS4_BUTTON_SQUARE",         "XUSB_GAMEPAD_X",              False),
    "Cross":    ("DS4_BUTTON_CROSS",          "XUSB_GAMEPAD_A",              False),
    "Triangle": ("DS4_BUTTON_TRIANGLE",       "XUSB_GAMEPAD_Y",              False),
    "L1":       ("DS4_BUTTON_SHOULDER_LEFT",  "XUSB_GAMEPAD_LEFT_SHOULDER",  False),
    "R1":       ("DS4_BUTTON_SHOULDER_RIGHT", "XUSB_GAMEPAD_RIGHT_SHOULDER", False),
    "L2":       (None,                        None,                          True),
    "Start":    ("DS4_BUTTON_OPTIONS",        "XUSB_GAMEPAD_START",          False),
    "Select":   ("DS4_BUTTON_SHARE",          "XUSB_GAMEPAD_BACK",           False),
}


class ControllerEngine:
    """Manages a single virtual gamepad and the currently "active" button."""

    def __init__(self):
        self.active_button = "Circle"  # the button held for voice commands
        self._pad = None
        self._pad_type = None  # "ds4" or "x360"
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self._pad is not None

    def init(self, prefer_ds4: bool = True):
        """Create the virtual gamepad. Returns (success, status_message)."""
        if not HAS_GAMEPAD:
            return False, "vgamepad not installed. Run: pip install vgamepad"

        with self._lock:
            if prefer_ds4:
                created, message = self._try_create_pad(vg.VDS4Gamepad, "ds4", "DS4")
                if created:
                    return True, message
                # DS4 failed — fall back to Xbox360 before giving up.
                created, fallback_message = self._try_create_pad(vg.VX360Gamepad, "x360", "Xbox360")
                if created:
                    return True, "Virtual Xbox360 controller created (DS4 unavailable)."
                return False, f"Controller init failed: {fallback_message}"

            created, message = self._try_create_pad(vg.VX360Gamepad, "x360", "Xbox360")
            return (True, message) if created else (False, f"Controller init failed: {message}")

    def _try_create_pad(self, pad_class, pad_type: str, display_name: str):
        try:
            pad = pad_class()
            pad.reset()
            pad.update()
        except Exception as error:  # noqa: BLE001 - vgamepad/driver errors vary
            self._pad = None
            self._pad_type = None
            return False, str(error)
        self._pad = pad
        self._pad_type = pad_type
        return True, f"Virtual {display_name} controller created."

    def destroy(self):
        with self._lock:
            if self._pad:
                try:
                    self._pad.reset()
                    self._pad.update()
                except Exception as error:  # noqa: BLE001 - best-effort cleanup
                    logger.debug("Error resetting gamepad on destroy: %s", error)
            self._pad = None
            self._pad_type = None

    def press_button(self, button_label: str = None):
        """Press (hold down) the given button, or `active_button` if omitted."""
        self._set_button_state("press", button_label or self.active_button)

    def release_button(self, button_label: str = None):
        """Release the given button, or `active_button` if omitted."""
        self._set_button_state("release", button_label or self.active_button)

    def _set_button_state(self, action: str, button_label: str):
        if not self._pad:
            return
        entry = BUTTON_MAP.get(button_label)
        if not entry:
            logger.warning("Unknown controller button label: %s", button_label)
            return

        ds4_attr, x360_attr, is_axis_trigger = entry
        with self._lock:
            try:
                if is_axis_trigger:
                    value = TRIGGER_PRESSED_VALUE if action == "press" else TRIGGER_RELEASED_VALUE
                    self._pad.left_trigger(value=value)
                else:
                    attr = ds4_attr if self._pad_type == "ds4" else x360_attr
                    button = getattr(vg.DS4_BUTTONS if self._pad_type == "ds4" else vg.XUSB_BUTTON, attr)
                    if action == "press":
                        self._pad.press_button(button=button)
                    else:
                        self._pad.release_button(button=button)
                self._pad.update()
            except Exception as error:  # noqa: BLE001 - vgamepad/driver errors vary
                logger.warning("Controller %s of %s failed: %s", action, button_label, error)
