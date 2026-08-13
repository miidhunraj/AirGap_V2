import os
import threading
from pathlib import Path
from utils.logger import get_logger

logger = get_logger("FileController")

UPLOAD_DIR = Path(os.path.expanduser("~")) / "AirGapReceiver_Uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_transfers: dict = {}  # track_id -> progress info
_lock = threading.Lock()


def save_file(filename: str, data: bytes, track_id: str = None) -> dict:
    safe_name = Path(filename).name  # Prevent path traversal
    target = UPLOAD_DIR / safe_name
    with _lock:
        with open(target, "wb") as f:
            f.write(data)
        size = len(data)
        if track_id:
            _transfers[track_id] = {"filename": safe_name, "size": size, "status": "complete"}
        logger.info(f"File saved: {target} ({size} bytes)")
    return {"saved_to": str(target), "size": size}


def get_transfer_status(track_id: str) -> dict:
    with _lock:
        return _transfers.get(track_id, {"status": "not_found"})


def list_downloads() -> list:
    files = []
    for f in UPLOAD_DIR.iterdir():
        if f.is_file():
            files.append({"name": f.name, "size": f.stat().st_size})
    return files
