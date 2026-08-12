"""
AirGap Connect - Desktop Receiver
Flask REST API + UDP Discovery Service
All communication is local Wi-Fi only. No internet required.
"""

import json
import socket
import threading
import platform
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from waitress import serve

from controllers import (
    mouse_controller,
    keyboard_controller,
    media_controller,
    system_controller,
    apps_controller,
    presentation_controller,
    clipboard_controller,
    file_controller,
)
from utils.logger import get_logger
from utils.network import get_local_ip, get_hostname
from utils.qr_generator import generate_qr_base64, show_qr_popup

logger = get_logger("AirGapReceiver")

app = Flask(__name__, static_folder="app_build", static_url_path="")
CORS(app)

@app.route("/")
def index():
    return app.send_static_file("index.html")

@app.errorhandler(404)
def not_found(e):
    return app.send_static_file("index.html")

HOST = "0.0.0.0"
PORT = 5005
DISCOVERY_PORT = 5006
DISCOVERY_INTERVAL = 2  # seconds between UDP broadcasts

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def ok(data: dict = None) -> tuple:
    payload = {"success": True}
    if data:
        payload.update(data)
    return jsonify(payload), 200


def err(msg: str, code: int = 400) -> tuple:
    return jsonify({"success": False, "error": msg}), code


# ─────────────────────────────────────────────
# STATUS
# ─────────────────────────────────────────────

@app.route("/api/status", methods=["GET"])
def status():
    info = system_controller.get_system_info()
    return ok({
        "receiver": "AirGapReceiver",
        "version": "1.0.0",
        "ip": get_local_ip(),
        "hostname": get_hostname(),
        **info,
    })


@app.route("/api/qr", methods=["GET"])
def qr_code():
    ip = get_local_ip()
    payload = json.dumps({"ip": ip, "port": PORT})
    img_b64 = generate_qr_base64(payload)
    return ok({"qr_base64": img_b64, "ip": ip, "port": PORT})


@app.route("/api/ping", methods=["GET", "POST"])
def ping():
    return ok({"pong": True, "timestamp": time.time()})


# ─────────────────────────────────────────────
# MOUSE / TOUCHPAD
# ─────────────────────────────────────────────

@app.route("/api/command", methods=["POST"])
def command():
    body = request.get_json(force=True, silent=True) or {}
    
    # --- LEGACY REACT NATIVE COMPATIBILITY ROUTER ---
    if "category" in body:
        category = body.get("category")
        legacy_action = body.get("action", "")
        payload = body.get("payload", {})
        
        # Slides compatibility
        if legacy_action == "slide_previous":
            presentation_controller.prev_slide()
            return jsonify({"status": "ok"})
        elif legacy_action == "slide_next":
            presentation_controller.next_slide()
            return jsonify({"status": "ok"})
        elif legacy_action == "presentation_start":
            presentation_controller.start_presentation()
            return jsonify({"status": "ok"})
        elif legacy_action == "presentation_end":
            presentation_controller.end_presentation()
            return jsonify({"status": "ok"})
        elif legacy_action == "black_screen":
            presentation_controller.black_screen()
            return jsonify({"status": "ok"})
        elif legacy_action == "white_screen":
            presentation_controller.white_screen()
            return jsonify({"status": "ok"})
            
        # Media compatibility
        elif legacy_action == "previous_track":
            media_controller.send_media_action("previous")
            return jsonify({"status": "ok"})
        elif legacy_action == "play_pause":
            media_controller.send_media_action("play_pause")
            return jsonify({"status": "ok"})
        elif legacy_action == "next_track":
            media_controller.send_media_action("next")
            return jsonify({"status": "ok"})
        elif legacy_action == "volume_down":
            media_controller.send_media_action("volume_down")
            return jsonify({"status": "ok"})
        elif legacy_action == "mute":
            media_controller.send_media_action("mute")
            return jsonify({"status": "ok"})
        elif legacy_action == "volume_up":
            media_controller.send_media_action("volume_up")
            return jsonify({"status": "ok"})
            
        # Apps/System compatibility
        elif legacy_action == "minimize":
            apps_controller.minimize_window()
            return jsonify({"status": "ok"})
        elif legacy_action == "maximize":
            apps_controller.maximize_window()
            return jsonify({"status": "ok"})
            
        # Touchpad extra features compatibility
        elif legacy_action == "scroll_up":
            mouse_controller.scroll(0, 120)
            return jsonify({"status": "ok"})
        elif legacy_action == "scroll_down":
            mouse_controller.scroll(0, -120)
            return jsonify({"status": "ok"})
        elif legacy_action == "back":
            keyboard_controller.hotkey("alt", "left")
            return jsonify({"status": "ok"})
        elif legacy_action == "drag_start":
            mouse_controller.mouse_down()
            return jsonify({"status": "ok"})
        elif legacy_action == "drag_end":
            mouse_controller.mouse_up()
            return jsonify({"status": "ok"})
            
        # Pass classic mouse moves/clicks through standard flow
        elif legacy_action in ["move", "left_click", "right_click", "double_click", "middle_click"]:
            action = legacy_action
            dx = float(payload.get("dx", 0))
            dy = float(payload.get("dy", 0))
            sensitivity = float(payload.get("sensitivity", 1.0))
        else:
            action = legacy_action
            dx = dy = 0
            sensitivity = 1.0
    else:
        # ------------------------------------------------
        action = body.get("action", "")
        dx = float(body.get("dx", 0))
        dy = float(body.get("dy", 0))
        sensitivity = float(body.get("sensitivity", 1.0))

    if action == "move":
        mouse_controller.move_mouse(dx, dy, sensitivity)
    elif action == "left_click":
        mouse_controller.left_click()
    elif action == "right_click":
        mouse_controller.right_click()
    elif action == "double_click":
        mouse_controller.double_click()
    elif action == "middle_click":
        mouse_controller.middle_click()
    elif action == "scroll":
        mouse_controller.scroll(dx, dy)
    elif action == "mouse_down":
        mouse_controller.mouse_down(body.get("button", "left"))
    elif action == "mouse_up":
        mouse_controller.mouse_up(body.get("button", "left"))
    elif action == "position":
        pos = mouse_controller.get_position()
        return ok(pos)
    else:
        return err(f"Unknown mouse action: {action}")
    return ok()


# ─────────────────────────────────────────────
# KEYBOARD TYPING
# ─────────────────────────────────────────────

@app.route("/api/type", methods=["POST"])
def type_text():
    body = request.get_json(force=True, silent=True) or {}
    text = body.get("text", "")
    fast = body.get("fast", False)
    if not text:
        return err("Missing 'text'")
    if fast:
        keyboard_controller.type_text_fast(text)
    else:
        keyboard_controller.type_text(text)
    return ok()


@app.route("/api/key", methods=["POST"])
def key_press():
    body = request.get_json(force=True, silent=True) or {}
    key = body.get("key", "")
    action = body.get("action", "press")  # press | down | up
    if not key:
        return err("Missing 'key'")
    if action == "down":
        keyboard_controller.key_down(key)
    elif action == "up":
        keyboard_controller.key_up(key)
    else:
        keyboard_controller.press_key(key)
    return ok()


@app.route("/api/hotkey", methods=["POST"])
def hotkey():
    body = request.get_json(force=True, silent=True) or {}
    keys = body.get("keys", [])
    if not keys or not isinstance(keys, list):
        return err("'keys' must be a non-empty list")
    keyboard_controller.hotkey(*keys)
    return ok()


# ─────────────────────────────────────────────
# MEDIA
# ─────────────────────────────────────────────

@app.route("/api/media", methods=["POST"])
def media():
    body = request.get_json(force=True, silent=True) or {}
    action = body.get("action", "")
    if action == "set_volume":
        level = body.get("level")
        if level is None:
            return err("Missing 'level'")
        media_controller.set_volume(int(level))
        return ok()
    elif action == "get_volume":
        vol = media_controller.get_volume()
        return ok({"volume": vol})
    elif action == "now_playing":
        info = media_controller.get_now_playing()
        if info:
            return ok({"active": True, **info})
        return ok({"active": False})
    elif action:
        success = media_controller.send_media_action(action)
        if not success:
            return err(f"Unknown media action: {action}")
        return ok()
    return err("Missing 'action'")


# ─────────────────────────────────────────────
# PRESENTATION
# ─────────────────────────────────────────────

@app.route("/api/presentation", methods=["POST"])
def presentation():
    body = request.get_json(force=True, silent=True) or {}
    action = body.get("action", "")
    handlers = {
        "next": presentation_controller.next_slide,
        "prev": presentation_controller.prev_slide,
        "black": presentation_controller.black_screen,
        "white": presentation_controller.white_screen,
        "start": presentation_controller.start_presentation,
        "end": presentation_controller.end_presentation,
        "timer_start": presentation_controller.start_timer,
        "timer_stop": presentation_controller.stop_timer,
        "timer_get": presentation_controller.get_timer,
    }
    if action == "laser":
        x = float(body.get("x", 0))
        y = float(body.get("y", 0))
        presentation_controller.laser_pointer_move(x, y)
        return ok()
    if action in handlers:
        result = handlers[action]()
        return ok(result if isinstance(result, dict) else {})
    return err(f"Unknown presentation action: {action}")


# ─────────────────────────────────────────────
# SCREENSHOT
  # ---------------------------------------------
@app.route('/api/screenshot', methods=['POST'])
def screenshot_route():
    try:
        import pyautogui
        import io
        import base64
        img = pyautogui.screenshot()
        buffer = io.BytesIO()
        img.thumbnail((900, 600))
        img.save(buffer, format='JPEG', quality=75)
        b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return ok({'screenshot_base64': b64})
    except Exception as e:
        logger.error(f'Screenshot error: {e}')
        return err(str(e))

  # SYSTEM / POWER
# ─────────────────────────────────────────────

@app.route("/api/system", methods=["POST"])
def system_route():
    body = request.get_json(force=True, silent=True) or {}
    action = body.get("action", "")
    delay = int(body.get("delay", 0))

    if action == "shutdown":
        system_controller.shutdown(delay)
    elif action == "restart":
        system_controller.restart(delay)
    elif action == "sleep":
        system_controller.sleep()
    elif action == "hibernate":
        system_controller.hibernate()
    elif action == "lock":
        system_controller.lock()
    elif action == "privacy":
        system_controller.privacy_mode()
    elif action == "logoff":
        system_controller.log_off()
    elif action == "abort":
        system_controller.abort_shutdown()
    elif action == "wake":
        system_controller.wake_screen()
    elif action == "info":
        info = system_controller.get_system_info()
        return ok(info)
    elif action == "run_command":
        cmd = body.get("command", "")
        shell = body.get("shell", "cmd")
        if not cmd:
            return err("Missing 'command'")
        result = system_controller.run_command(cmd, shell)
        return ok(result)
    else:
        return err(f"Unknown system action: {action}")
    return ok()


# ─────────────────────────────────────────────
# APPS
# ─────────────────────────────────────────────

@app.route("/api/apps", methods=["GET", "POST"])
def apps():
    if request.method == "GET":
        query = request.args.get("type", "running")
        if query == "installed":
            return ok({"apps": apps_controller.get_installed_apps()})
        return ok({"apps": apps_controller.get_running_apps()})

    body = request.get_json(force=True, silent=True) or {}
    action = body.get("action", "")

    if action == "launch":
        path = body.get("path", "")
        if not path:
            return err("Missing 'path'")
        success = apps_controller.launch_app(path)
        return ok() if success else err("Failed to launch app")
    elif action == "kill":
        pid = body.get("pid")
        if pid is None:
            return err("Missing 'pid'")
        success = apps_controller.kill_process(int(pid))
        return ok() if success else err("Failed to kill process")
    elif action == "switch_window":
        apps_controller.switch_window()
    elif action == "task_view":
        apps_controller.task_view()
    elif action == "minimize":
        apps_controller.minimize_window()
    elif action == "maximize":
        apps_controller.maximize_window()
    elif action == "open_explorer":
        apps_controller.open_explorer(body.get("path"))
    elif action == "open_browser":
        apps_controller.open_browser(body.get("url", "about:blank"))
    elif action == "open_terminal":
        apps_controller.open_terminal()
    else:
        return err(f"Unknown apps action: {action}")
    return ok()


# ─────────────────────────────────────────────
# CLIPBOARD
# ─────────────────────────────────────────────

@app.route("/api/clipboard", methods=["GET", "POST"])
def clipboard():
    if request.method == "GET":
        text = clipboard_controller.get_clipboard()
        return ok({"text": text})
    body = request.get_json(force=True, silent=True) or {}
    text = body.get("text", "")
    success = clipboard_controller.set_clipboard(text)
    return ok() if success else err("Clipboard set failed")


# ─────────────────────────────────────────────
# FILE TRANSFER
# ─────────────────────────────────────────────

@app.route("/api/file", methods=["POST"])
def file_upload():
    if "file" in request.files:
        f = request.files["file"]
        track_id = request.form.get("track_id")
        data = f.read()
        result = file_controller.save_file(f.filename, data, track_id)
        return ok(result)
    elif request.content_type and "application/json" in request.content_type:
        body = request.get_json(force=True, silent=True) or {}
        action = body.get("action", "")
        if action == "status":
            tid = body.get("track_id", "")
            return ok(file_controller.get_transfer_status(tid))
        elif action == "list":
            return ok({"files": file_controller.list_downloads()})
    return err("Invalid request")


# ─────────────────────────────────────────────
# UDP DISCOVERY BROADCAST
# ─────────────────────────────────────────────

def _udp_discovery_broadcast():
    """Broadcast receiver info via UDP so the Android app can auto-discover."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    payload = json.dumps({
        "service": "AirGapReceiver",
        "version": "1.0.0",
        "ip": get_local_ip(),
        "port": PORT,
        "hostname": get_hostname(),
    }).encode("utf-8")
    logger.info(f"UDP Discovery broadcasting on port {DISCOVERY_PORT}")
    while True:
        try:
            sock.sendto(payload, ("<broadcast>", DISCOVERY_PORT))
        except Exception as e:
            logger.warning(f"UDP broadcast error: {e}")
        time.sleep(DISCOVERY_INTERVAL)


def start_discovery_service():
    t = threading.Thread(target=_udp_discovery_broadcast, daemon=True)
    t.start()
    logger.info("UDP Discovery service started")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import os
    from utils.qr_generator import save_qr_file
    
    ip = get_local_ip()
    url = f"http://{ip}:{PORT}"
    
    logger.info("=" * 50)
    logger.info("  AirGap Connect - Desktop Receiver v2.0.0")
    logger.info(f"  Listening on {url}")
    logger.info(f"  Hostname: {get_hostname()}")
    logger.info("=" * 50)

    # 1. Generate & pop up the branded QR window natively
    qr_path = "airgap_qr.png"
    try:
        logger.info(f"Generating QR Code for {url} to {qr_path}")
        save_qr_file(url, qr_path)
    except Exception as e:
        logger.warning(f"Failed to generate QR file: {e}")

    try:
        show_qr_popup(url)
    except Exception as e:
        logger.warning(f"Failed to show styled QR popup, falling back to image viewer: {e}")
        try:
            if os.name == "nt":
                os.startfile(qr_path)
        except Exception as e2:
            logger.warning(f"Failed to open QR image fallback: {e2}")

    # 2. Start Services
    start_discovery_service()

    # Use Waitress for production WSGI serving (thread-safe, battle-tested)
    serve(app, host=HOST, port=PORT, threads=8)





