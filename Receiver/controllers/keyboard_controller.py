import threading
import pyautogui
import pyperclip
from utils.logger import get_logger

logger = get_logger("KeyboardController")

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

_lock = threading.Lock()

# Map of key name strings sent by the mobile app to pyautogui key names
KEY_MAP = {
    "win": "win",
    "ctrl": "ctrl",
    "alt": "alt",
    "shift": "shift",
    "tab": "tab",
    "esc": "escape",
    "escape": "escape",
    "enter": "enter",
    "backspace": "backspace",
    "delete": "delete",
    "insert": "insert",
    "home": "home",
    "end": "end",
    "pageup": "pageup",
    "pagedown": "pagedown",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "capslock": "capslock",
    "f1": "f1", "f2": "f2", "f3": "f3", "f4": "f4",
    "f5": "f5", "f6": "f6", "f7": "f7", "f8": "f8",
    "f9": "f9", "f10": "f10", "f11": "f11", "f12": "f12",
    "printscreen": "printscreen",
    "scrolllock": "scrolllock",
    "pause": "pause",
    "numlock": "numlock",
    "space": "space",
}


def type_text(text: str) -> None:
    """Type a string character by character with native input simulation."""
    with _lock:
        pyautogui.typewrite(text, interval=0.01)


def type_text_fast(text: str) -> None:
    """Use clipboard paste for large text blocks (faster)."""
    with _lock:
        previous = pyperclip.paste()
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        # Restore clipboard after paste
        import time
        time.sleep(0.15)
        pyperclip.copy(previous)


def press_key(key: str) -> None:
    """Press and release a single key."""
    mapped = KEY_MAP.get(key.lower(), key.lower())
    with _lock:
        pyautogui.press(mapped)
        logger.debug(f"Key pressed: {mapped}")


def hotkey(*keys: str) -> None:
    """Press a combination of keys simultaneously."""
    mapped = [KEY_MAP.get(k.lower(), k.lower()) for k in keys]
    with _lock:
        pyautogui.hotkey(*mapped)
        logger.debug(f"Hotkey: {'+'.join(mapped)}")


def key_down(key: str) -> None:
    mapped = KEY_MAP.get(key.lower(), key.lower())
    with _lock:
        pyautogui.keyDown(mapped)


def key_up(key: str) -> None:
    mapped = KEY_MAP.get(key.lower(), key.lower())
    with _lock:
        pyautogui.keyUp(mapped)
