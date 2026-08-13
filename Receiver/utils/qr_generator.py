import io
import base64
import threading
import qrcode
from PIL import Image


def generate_qr_base64(data: str, box_size: int = 10, border: int = 4) -> str:
    """Generate a QR code from data and return it as a Base64-encoded PNG string."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img: Image.Image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    encoded = base64.b64encode(buffer.read()).decode("utf-8")
    return encoded


def save_qr_file(data: str, path: str = "airgap_qr.png") -> None:
    qr = qrcode.make(data)
    qr.save(path)


def show_qr_popup(url: str) -> None:
    """Show a small branded native window with the connect QR code and the
    raw URL underneath, styled to match the AirGap console. Runs in its own
    daemon thread so it never blocks the Waitress server from starting.
    Silently no-ops if tkinter isn't available in this Python install.
    """
    def _run():
        try:
            import tkinter as tk
            from PIL import ImageTk
        except Exception:
            return

        try:
            BG = "#090C13"
            SURFACE = "#12151F"
            TEXT = "#F3F4F8"
            TEXT_MUTED = "#8B92A5"
            TEXT_FAINT = "#5B6376"
            ACCENT = "#9179FF"

            root = tk.Tk()
            root.title("AirGap Connect")
            root.configure(bg=BG)
            width, height = 420, 620
            root.geometry(f"{width}x{height}")
            root.minsize(width, height)
            root.resizable(False, False)

            # Center on screen
            root.update_idletasks()
            sw = root.winfo_screenwidth()
            sh = root.winfo_screenheight()
            root.geometry(f"{width}x{height}+{(sw - width)//2}+{(sh - height)//2}")

            tk.Label(root, text="AIRGAP  CONNECT", fg=TEXT, bg=BG,
                     font=("Segoe UI", 20, "bold")).pack(pady=(30, 6))
            tk.Label(root, text="Scan with your phone camera", fg=TEXT_MUTED, bg=BG,
                     font=("Segoe UI", 11)).pack(pady=(0, 18))

            qr_img = qrcode.make(url).resize((300, 300))
            photo = ImageTk.PhotoImage(qr_img)
            qr_holder = tk.Frame(root, bg="#FFFFFF", padx=14, pady=14)
            qr_label = tk.Label(qr_holder, image=photo, bd=0, bg="#FFFFFF")
            qr_label.image = photo  # keep a reference alive
            qr_label.pack()
            qr_holder.pack(pady=(0, 20))

            tk.Label(root, text=url, fg=ACCENT, bg=BG,
                     font=("Consolas", 13, "bold")).pack(pady=(0, 6))
            tk.Label(root, text="Make sure your phone is on the same Wi-Fi", fg=TEXT_FAINT, bg=BG,
                     font=("Segoe UI", 9)).pack(pady=(0, 26))

            def _close():
                root.destroy()

            close_btn = tk.Button(
                root, text="Close", command=_close,
                bg=SURFACE, fg=TEXT, activebackground="#1E2430", activeforeground="#FFFFFF",
                relief="flat", bd=0, font=("Segoe UI", 10, "bold"), padx=26, pady=10,
                highlightthickness=1, highlightbackground="#232838", cursor="hand2"
            )
            close_btn.pack()

            root.protocol("WM_DELETE_WINDOW", _close)
            root.attributes("-topmost", True)
            root.after(300, lambda: root.attributes("-topmost", False))
            root.mainloop()
        except Exception:
            # Never let a popup/display issue take down the receiver.
            pass

    threading.Thread(target=_run, daemon=True).start()
