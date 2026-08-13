import threading
import pyautogui
from utils.logger import get_logger

logger = get_logger("PresentationController")

_lock = threading.Lock()
_timer_seconds = 0
_timer_running = False
_timer_thread = None


def next_slide() -> None:
    with _lock:
        pyautogui.press("right")
        logger.debug("Presentation: next slide")


def prev_slide() -> None:
    with _lock:
        pyautogui.press("left")
        logger.debug("Presentation: prev slide")


def black_screen() -> None:
    with _lock:
        pyautogui.press("b")
        logger.debug("Presentation: black screen")


def white_screen() -> None:
    with _lock:
        pyautogui.press("w")
        logger.debug("Presentation: white screen")


def start_presentation() -> None:
    with _lock:
        pyautogui.press("f5")
        logger.debug("Presentation: started (F5)")


def end_presentation() -> None:
    with _lock:
        pyautogui.press("escape")
        logger.debug("Presentation: ended (ESC)")


def start_timer() -> dict:
    global _timer_seconds, _timer_running, _timer_thread
    _timer_seconds = 0
    _timer_running = True

    def _tick():
        global _timer_seconds, _timer_running
        import time
        while _timer_running:
            time.sleep(1)
            _timer_seconds += 1

    _timer_thread = threading.Thread(target=_tick, daemon=True)
    _timer_thread.start()
    logger.debug("Timer started")
    return {"status": "started"}


def stop_timer() -> dict:
    global _timer_running
    _timer_running = False
    elapsed = _timer_seconds
    logger.debug(f"Timer stopped at {elapsed}s")
    return {"elapsed_seconds": elapsed}


def get_timer() -> dict:
    return {"elapsed_seconds": _timer_seconds, "running": _timer_running}


def laser_pointer_move(x: float, y: float) -> None:
    """Move mouse to simulate a laser pointer (absolute screen coordinates)."""
    with _lock:
        screen_w, screen_h = pyautogui.size()
        abs_x = int(x * screen_w)
        abs_y = int(y * screen_h)
        pyautogui.moveTo(abs_x, abs_y, duration=0)
