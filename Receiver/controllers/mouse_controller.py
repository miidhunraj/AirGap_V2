import time
import threading
import pyautogui
from utils.logger import get_logger

logger = get_logger("MouseController")

# Prevent PyAutoGUI fail-safe from triggering during rapid movement
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

_lock = threading.Lock()


def move_mouse(dx: float, dy: float, sensitivity: float = 1.0) -> None:
    """Relative mouse movement from touchpad delta."""
    with _lock:
        scaled_dx = dx * sensitivity
        scaled_dy = dy * sensitivity
        pyautogui.moveRel(scaled_dx, scaled_dy, duration=0)


def left_click() -> None:
    with _lock:
        pyautogui.click(button="left")


def right_click() -> None:
    with _lock:
        pyautogui.click(button="right")


def double_click() -> None:
    with _lock:
        pyautogui.doubleClick(button="left")


def middle_click() -> None:
    with _lock:
        pyautogui.click(button="middle")


def scroll(dx: float, dy: float) -> None:
    """Scroll vertically (dy) and horizontally (dx)."""
    with _lock:
        if dy != 0:
            pyautogui.scroll(int(dy))
        if dx != 0:
            pyautogui.hscroll(int(dx))


def mouse_down(button: str = "left") -> None:
    with _lock:
        pyautogui.mouseDown(button=button)


def mouse_up(button: str = "left") -> None:
    with _lock:
        pyautogui.mouseUp(button=button)


def get_position() -> dict:
    pos = pyautogui.position()
    return {"x": pos.x, "y": pos.y}
