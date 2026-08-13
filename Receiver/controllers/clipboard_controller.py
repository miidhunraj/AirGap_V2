import os
import threading
import pyperclip
from utils.logger import get_logger

logger = get_logger("ClipboardController")

_lock = threading.Lock()


def get_clipboard() -> str:
    with _lock:
        try:
            return pyperclip.paste()
        except Exception as e:
            logger.error(f"Clipboard get failed: {e}")
            return ""


def set_clipboard(text: str) -> bool:
    with _lock:
        try:
            pyperclip.copy(text)
            logger.debug(f"Clipboard set: {text[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Clipboard set failed: {e}")
            return False
