import threading
import pyautogui
from utils.logger import get_logger

logger = get_logger("MediaController")

_lock = threading.Lock()

# Map action strings to pyautogui key names
MEDIA_KEYS = {
    "play_pause": "playpause",
    "next": "nexttrack",
    "previous": "prevtrack",
    "stop": "stop",
    "volume_up": "volumeup",
    "volume_down": "volumedown",
    "mute": "volumemute",
    "fullscreen": "f11",
    "brightness_up": None,  # Handled via win+A or OEM key
    "brightness_down": None,
}


def send_media_action(action: str) -> bool:
    key = MEDIA_KEYS.get(action)
    if key:
        with _lock:
            pyautogui.press(key)
            logger.debug(f"Media action: {action} -> {key}")
        return True
    elif action == "brightness_up":
        _brightness_up()
        return True
    elif action == "brightness_down":
        _brightness_down()
        return True
    else:
        logger.warning(f"Unknown media action: {action}")
        return False


def _brightness_up() -> None:
    """Use WMI or nircmd if available; fallback to Fn-key simulation."""
    try:
        import subprocess
        subprocess.Popen([
            "powershell", "-Command",
            "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,"
            + str(min(100, _get_brightness() + 10)) + ")"
        ], shell=True)
    except Exception as e:
        logger.warning(f"Brightness up failed: {e}")


def _brightness_down() -> None:
    try:
        import subprocess
        subprocess.Popen([
            "powershell", "-Command",
            "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,"
            + str(max(0, _get_brightness() - 10)) + ")"
        ], shell=True)
    except Exception as e:
        logger.warning(f"Brightness down failed: {e}")


def _get_brightness() -> int:
    try:
        import subprocess
        result = subprocess.check_output(
            ["powershell", "-Command",
             "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness"],
            shell=True
        )
        return int(result.strip())
    except Exception:
        return 50


def set_volume(level: int) -> None:
    """Set system volume 0-100 using pycaw."""
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        import math
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        scalar = max(0.0, min(1.0, level / 100.0))
        volume.SetMasterVolumeLevelScalar(scalar, None)
        logger.debug(f"Volume set to {level}")
    except Exception as e:
        logger.error(f"Volume set failed: {e}")


def get_volume() -> int:
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        level = volume.GetMasterVolumeLevelScalar()
        return int(level * 100)
    except Exception:
        return -1


def get_now_playing() -> dict:
    """Fetch title/artist/thumbnail for whatever app currently owns the
    system media session (Spotify, browser tab, etc.) via the Windows
    System Media Transport Controls. Returns None if there is no active
    session or the required Windows Runtime bindings aren't available —
    callers must treat that as 'nothing playing', not an error.
    """
    try:
        import asyncio
        import base64
        from winsdk.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as MediaManager,
        )
        from winsdk.windows.storage.streams import Buffer, InputStreamOptions

        async def _fetch():
            manager = await MediaManager.request_async()
            session = manager.get_current_session()
            if session is None:
                return None
            props = await session.try_get_media_properties_async()

            thumbnail_b64 = None
            thumb_ref = props.thumbnail
            if thumb_ref is not None:
                stream = await thumb_ref.open_read_async()
                size = stream.size
                if size > 0:
                    buf = Buffer(size)
                    await stream.read_async(buf, size, InputStreamOptions.READ_AHEAD)
                    raw = bytes(buf)[:size]
                    thumbnail_b64 = base64.b64encode(raw).decode("utf-8")

            return {
                "title": props.title or "",
                "artist": props.artist or "",
                "album": props.album_title or "",
                "thumbnail_base64": thumbnail_b64,
            }

        return asyncio.run(_fetch())
    except Exception as e:
        logger.debug(f"Now-playing fetch unavailable: {e}")
        return None
