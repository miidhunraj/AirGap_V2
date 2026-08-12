import subprocess
import os
import ctypes
import threading
from utils.logger import get_logger

logger = get_logger("SystemController")

_lock = threading.Lock()


def shutdown(delay: int = 0) -> None:
    logger.info(f"Shutdown requested (delay={delay}s)")
    os.system(f"shutdown /s /t {delay}")


def restart(delay: int = 0) -> None:
    logger.info(f"Restart requested (delay={delay}s)")
    os.system(f"shutdown /r /t {delay}")


def sleep() -> None:
    logger.info("Sleep requested")
    # Using PowerShell to cleanly suspend without triggering Hibernation
    ps_command = "Add-Type -Assembly System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)"
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_command], capture_output=True)


def hibernate() -> None:
    logger.info("Hibernate requested")
    os.system("shutdown /h")


def lock() -> None:
    logger.info("Lock requested")
    ctypes.windll.user32.LockWorkStation()


def log_off() -> None:
    logger.info("Logoff requested")
    os.system("shutdown /l")


def abort_shutdown() -> None:
    os.system("shutdown /a")


def wake_screen() -> None:
    """Force the display on and nudge the idle timer — does not bypass the
    Windows lock screen password (that would require storing credentials,
    which this receiver deliberately never does)."""
    logger.info("Wake screen requested")
    try:
        # SC_MONITORPOWER with -1 forces the display on immediately.
        ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, -1)
        # A 1px cursor nudge resets the idle timer so the display doesn't
        # immediately re-blank if a screensaver/timeout was about to fire.
        ctypes.windll.user32.mouse_event(0x0001, 1, 0, 0, 0)
        ctypes.windll.user32.mouse_event(0x0001, -1, 0, 0, 0)
    except Exception as e:
        logger.error(f"Wake screen failed: {e}")


def run_command(command: str, shell: str = "cmd") -> dict:
    """Execute a command in CMD or PowerShell and return output."""
    logger.info(f"Running [{shell}]: {command}")
    try:
        if shell == "powershell":
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True, text=True, timeout=30
            )
        else:
            proc = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=30
            )
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "stdout": "", "stderr": "Command timed out"}
    except Exception as e:
        return {"returncode": -1, "stdout": "", "stderr": str(e)}


def get_system_info() -> dict:
    import platform
    import psutil
    battery = psutil.sensors_battery()
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.1)
    return {
        "hostname": platform.node(),
        "os": platform.system(),
        "os_version": platform.version(),
        "cpu_percent": cpu,
        "ram_total_mb": round(mem.total / 1024 / 1024),
        "ram_used_mb": round(mem.used / 1024 / 1024),
        "ram_percent": mem.percent,
        "battery_percent": battery.percent if battery else None,
        "battery_plugged": battery.power_plugged if battery else None,
    }

def privacy_mode() -> None:
    logger.info("Privacy mode requested (Monitor Off)")
    try:
        # 0x0112 = WM_SYSCOMMAND, 0xF170 = SC_MONITORPOWER, 2 = Turn Off
        ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
    except Exception as e:
        logger.error(f"Privacy mode failed: {e}")

