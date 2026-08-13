# AirGap V2 — System Requirements & Prerequisites

Everything you need in place *before* running `easy_start.bat`, in one place.

---

## 1. On the PC (the Receiver)

| Requirement | Details |
|---|---|
| **Operating System** | Windows 10 or Windows 11 (64-bit). The automation layer uses Windows-only APIs (`ctypes.windll`, COM, SMTC) — it will not run on macOS or Linux. |
| **Python** | **3.8 – 3.13**, with **3.10–3.12 recommended**. Must be added to PATH (the official installer's "Add python.exe to PATH" checkbox). `easy_start.bat` will detect this automatically and send you to the download page if it's missing. |
| **Administrator rights** | Needed once, to add the Windows Firewall rule for port `5005`. `easy_start.bat` will prompt for elevation automatically. |
| **Disk space** | ~150 MB for the virtual environment and dependencies. |
| **Internet access (one-time only)** | Needed the first time you run `easy_start.bat`, to download Python packages via pip. After that, AirGap runs fully offline / local-network-only. |

### Optional Windows software (for specific features only)
AirGap works fully without these — they only affect the specific buttons listed:

| App | Used by | If missing |
|---|---|---|
| Google Chrome | "Chrome" quick-launch button | Button shows a toast saying it couldn't launch |
| Microsoft PowerPoint | "PowerPoint" quick-launch button | Same — graceful failure, no crash |
| Spotify (desktop app) | "Open Spotify" button in Media panel | Same |
| Any SMTC-reporting media app (Spotify, browser tab, etc.) | "Now Playing" thumbnail/title in Media panel | Shows "Nothing playing" instead |

### Python packages
All handled automatically by `easy_start.bat` (or `pip install -r Receiver/requirements.txt` manually). Full list, versions, and *why* each version was picked: see [`Receiver/requirements.txt`](Receiver/requirements.txt) and the **Compatibility** section of the main [README](README.md).

---

## 2. On the phone (the Controller)

| Requirement | Details |
|---|---|
| **Any modern browser** | Chrome, Safari, Firefox, Edge, Samsung Internet — anything with support for the Fullscreen API and Service Workers (basically anything from the last ~5 years). No app install required. |
| **Same Wi-Fi network as the PC** | AirGap is local-network-only by design — it does not work over mobile data or a different network. |
| **Camera** (optional) | Only needed to scan the pairing QR code; you can also type the printed `http://<ip>:5005` URL manually. |

---

## 3. Network requirements

| Item | Details |
|---|---|
| Port `5005` (TCP) | The Flask receiver's web server. Must be reachable from your phone — `easy_start.bat` opens this in Windows Firewall automatically. |
| Port `5006` (UDP) | Used for local discovery broadcast. |
| Router configuration | No port forwarding, no internet-facing exposure — everything stays on your LAN. If you're on a "Guest" or "Public" Wi-Fi profile in Windows, device-to-device traffic may be blocked by the router itself, not by AirGap. |

---

## 4. Quick self-check

Run this any time to get a live report of exactly what's available in your environment:

```bash
cd Receiver
python verify_install.py
```

It checks Python version, every required package, the Windows-only automation stack, and the optional Now Playing capability — and tells you plainly what will and won't work.
