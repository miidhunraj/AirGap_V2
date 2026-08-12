import os
import subprocess
import psutil
from utils.logger import get_logger

logger = get_logger("AppsController")


def get_running_apps() -> list:
    """Return a list of running user-facing processes."""
    apps = []
    for proc in psutil.process_iter(["pid", "name", "status"]):
        try:
            if proc.info["status"] == psutil.STATUS_RUNNING:
                apps.append({
                    "pid": proc.info["pid"],
                    "name": proc.info["name"],
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return apps


def kill_process(pid: int) -> bool:
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        logger.info(f"Terminated process PID={pid}")
        return True
    except Exception as e:
        logger.error(f"Kill PID={pid} failed: {e}")
        return False


def launch_app(path: str) -> bool:
    try:
        subprocess.Popen([path], shell=True)
        logger.info(f"Launched: {path}")
        return True
    except Exception as e:
        logger.error(f"Launch failed for {path}: {e}")
        return False


def open_explorer(path: str = None) -> None:
    if path:
        os.startfile(path)
    else:
        os.startfile("explorer")


def open_browser(url: str = "about:blank") -> None:
    import webbrowser
    webbrowser.open(url)


def open_terminal() -> None:
    subprocess.Popen(["cmd.exe"])


def switch_window() -> None:
    """Simulate Alt+Tab."""
    import pyautogui
    pyautogui.hotkey("alt", "tab")


def task_view() -> None:
    """Open Windows Task View with Win+Tab."""
    import pyautogui
    pyautogui.hotkey("win", "tab")


def minimize_window() -> None:
    import pyautogui
    pyautogui.hotkey("win", "down")


def maximize_window() -> None:
    import pyautogui
    pyautogui.hotkey("win", "up")


def get_installed_apps() -> list:
    """Return a list of installed apps from the Start Menu."""
    import glob
    shortcuts = []
    start_menu_dirs = [
        os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%AppData%\Microsoft\Windows\Start Menu\Programs"),
    ]
    for directory in start_menu_dirs:
        for lnk in glob.glob(os.path.join(directory, "**", "*.lnk"), recursive=True):
            name = os.path.splitext(os.path.basename(lnk))[0]
            shortcuts.append({"name": name, "path": lnk})
    return shortcuts
