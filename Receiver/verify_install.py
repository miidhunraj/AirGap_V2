"""
AirGap Connect -- post-install self-test.

Run after `pip install -r requirements.txt` to confirm the environment is
actually usable before trying to launch the real receiver. Exits 0 when
core functionality is confirmed working, 1 on a real failure.

Two kinds of checks:
  - required: a failure here means AirGap will not run correctly.
  - optional: a failure here is reported as a warning -- the feature it
    backs (e.g. Now Playing thumbnails) degrades gracefully at runtime
    instead of crashing anything else.

On non-Windows systems, the Windows-only automation stack (pyautogui,
comtypes, pycaw, and importing app.py itself, which pulls all of it in
transitively) is expected to fail import for platform reasons that have
nothing to do with whether the install itself succeeded -- those are
downgraded to warnings here rather than hard failures.

Usage:
    python verify_install.py
"""

import importlib
import importlib.metadata
import platform
import sys

PASS = "  [OK]  "
WARN = "  [--]  "
FAIL = "  [XX]  "

IS_WINDOWS = platform.system() == "Windows"

failures = []
warnings_ = []


def _dist_version(dist_name):
    """Look up an installed package's version via packaging metadata
    (importlib.metadata) rather than each module's own __version__
    attribute -- more reliable and avoids per-package deprecation
    warnings (e.g. Flask 3.1 dropped __version__)."""
    try:
        return importlib.metadata.version(dist_name)
    except importlib.metadata.PackageNotFoundError:
        return "installed"


def check(label, fn, required=True, platform_gated=False):
    """Run one check. If platform_gated and we're not on Windows, a
    failure is downgraded to a warning instead of a hard failure, since
    it reflects the sandbox/dev platform, not a real install problem."""
    try:
        detail = fn()
        print(f"{PASS}{label}" + (f" ({detail})" if detail else ""))
        return True
    except Exception as e:
        if not required or (platform_gated and not IS_WINDOWS):
            reason = e if not platform_gated else f"not available on {platform.system()} (Windows-only) -- {e}"
            print(f"{WARN}{label} -> {reason}")
            warnings_.append(label)
        else:
            print(f"{FAIL}{label} -> {e}")
            failures.append(label)
        return False


def main():
    print("=" * 62)
    print("  AirGap Connect -- install verification")
    print("=" * 62)

    # 1. Python version ----------------------------------------------------
    check(
        "Python version",
        lambda: platform.python_version()
        if sys.version_info >= (3, 8)
        else (_ for _ in ()).throw(RuntimeError("need Python 3.8+")),
    )

    # 2. Platform -----------------------------------------------------------
    if not IS_WINDOWS:
        print(
            f"{WARN}Running on {platform.system()}, not Windows -- the "
            f"automation controllers (mouse/keyboard/power/media/etc.) "
            f"require Windows and will not function here. The checks below "
            f"still confirm the install itself is sound."
        )
        warnings_.append("Non-Windows platform")

    # 3. Platform-independent required packages ------------------------------
    for import_name, dist_name in [
        ("flask", "flask"),
        ("flask_cors", "Flask-Cors"),
        ("waitress", "waitress"),
        ("PIL", "Pillow"),
        ("qrcode", "qrcode"),
        ("pyperclip", "pyperclip"),
        ("psutil", "psutil"),
    ]:
        check(dist_name, lambda i=import_name, d=dist_name: (
            importlib.import_module(i), _dist_version(d)
        )[1])

    # 4. Windows-automation stack (platform-gated: warning off-Windows) -----
    check(
        "PyAutoGUI",
        lambda: (importlib.import_module("pyautogui"), _dist_version("PyAutoGUI"))[1],
        platform_gated=True,
    )
    check(
        "comtypes",
        lambda: (importlib.import_module("comtypes"), _dist_version("comtypes"))[1],
        platform_gated=True,
    )
    check(
        "pycaw (system volume control)",
        lambda: (importlib.import_module("pycaw.pycaw"), _dist_version("pycaw"))[1],
        platform_gated=True,
    )

    # 5. Optional: Now Playing media metadata (winsdk) -----------------------
    check(
        "winsdk (Now Playing thumbnails)",
        lambda: (importlib.import_module("winsdk"), _dist_version("winsdk"))[1],
        required=False,
    )
    if "winsdk (Now Playing thumbnails)" in warnings_:
        print(
            f"{WARN}    -> expected on non-Windows systems and on Python "
            f"3.13+ (see requirements.txt). Every other feature works "
            f"normally; the Media panel will just show 'Nothing playing' "
            f"instead of live track info."
        )

    # 6. The app itself imports and constructs cleanly -----------------------
    def _import_app():
        sys.path.insert(0, ".")
        import app as airgap_app  # noqa: F401  (import-only check)
        assert airgap_app.app is not None
        return "Flask app object constructed"
    check("AirGap app.py imports cleanly", _import_app, platform_gated=True)

    # 7. Local network detection ----------------------------------------------
    def _network():
        from utils.network import get_local_ip, get_hostname
        return f"{get_hostname()} @ {get_local_ip()}"
    check("Local network detection", _network)

    # ---------------------------------------------------------------------
    print("=" * 62)
    if failures:
        print(f"  RESULT: {len(failures)} failure(s), {len(warnings_)} warning(s)")
        print("  AirGap is NOT ready to run. Fix the failures above, then")
        print("  re-run: python verify_install.py")
        print("=" * 62)
        sys.exit(1)
    elif warnings_:
        print(f"  RESULT: PASS with {len(warnings_)} warning(s) -- AirGap will run,")
        print("  with the noted items expected/degraded as described above.")
        print("=" * 62)
        sys.exit(0)
    else:
        print("  RESULT: PASS -- every checked capability is available.")
        print("=" * 62)
        sys.exit(0)


if __name__ == "__main__":
    main()
