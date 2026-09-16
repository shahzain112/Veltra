import os
import sys
import io
import time
import threading
import subprocess
import urllib.request

import customtkinter as ctk
import yt_dlp
from tkinter import filedialog, messagebox
from PIL import Image, ImageDraw, ImageTk

# ================= CONSTANTS =================
VERSION = "2.0.0"
APP_NAME = "Veltra"
FROZEN = getattr(sys, "frozen", False)   # exe ke andar chal raha hai?

# ---------------- FFmpeg auto-detect ----------------
try:
    import imageio_ffmpeg
    FFMPEG_PATH = os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())
except Exception:
    FFMPEG_PATH = None

# ---------------- Windows DPI (crisp UI) ----------------
if sys.platform == "win32":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

RESAMPLE = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS

# ================= PATH HELPERS =================
def resource_path(rel):
    """Dev mode: script folder | EXE mode: _MEIPASS temp folder"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def base_dir():
    return os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))


def find_logo():
    for n in ("Veltra.png", "Veltra.jpg", "Veltra.jpeg"):
        p = resource_path(n)
        if os.path.exists(p):
            return p
    return None


def make_ico(png_path):
    """PNG ko Windows .ico mein convert karo (title bar + exe icon ke liye)"""
    if not png_path:
        return None
    try:
        img = Image.open(png_path).convert("RGBA")
        w, h = img.size
        s = min(w, h)
        img = img.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
        img = img.resize((256, 256), RESAMPLE)
        ico = os.path.join(base_dir(), "Veltra_icon.ico")
        img.save(ico, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
        return ico
    except Exception:
        return None


LOGO_PNG = find_logo()
ICON_ICO = make_ico(LOGO_PNG)

# ================= THEME (Spotify-inspired) =================
BG        = "#0A0A0C"
CARD      = "#141417"
ENTRY_BG  = "#1B1B20"
BORDER    = "#26262C"
ACCENT    = "#1DB954"
ACCENT_HV = "#1ED760"
TEXT      = "#F2F2F5"
MUTED     = "#8B8B94"
DANGER    = "#FF5F57"
WARNING   = "#FEBC2E"
FONT      = "Segoe UI"

ctk.set_appearance_mode("dark")


class DownloadCancelled(Exception):
    pass


# ================= SMALL HELPERS =================
def human_size(n):
    if not n:
        return "—"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def human_eta(s):
    if s is None:
        return "—"
    s = int(s)
    if s >= 3600:
        return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d} hr"
    if s >= 60:
        return f"{s // 60}:{s % 60:02d} min"
    return f"{s} sec"


def rounded_img(img, size, radius):
    img = img.convert("RGBA").resize(size, RESAMPLE)
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255)
    img.putalpha(mask)
    return img


# ================= MAIN APP =================
class VeltraApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{VERSION}")
        self.geometry("820x740")
        self.resizable(False, False)
        self.configure(fg_color=BG)

        if ICON_ICO:
            try:
                self.iconbitmap(ICON_ICO)
            except Exception:
                pass

        self.update_idletasks()
        x = (self.winfo_screenwidth() - 820) // 2
        y = (self.winfo_screenheight() - 740) // 2
        self.geometry(f"820x740+{x}+{y}")

        self.last_folder = os.path.join(os.path.expanduser("~"), "Downloads")
        self._last_saved_folder = self.last_folder
        self.cancel_event = threading.Event()
        self.busy = False
        self._thumb_img = None
        self._last_tick = 0

        self._build_footer()
        self._build_header()
        self._build_url_card()
        self._build_preview_card()
        self._build_options_card()
        self._build_download_button()
        self._build_progress_card()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ================= UI =================
    def _build_footer(self):
        ffmpeg_txt = "OK" if FFMPEG_PATH else "Not Found"
        mode_txt = "Portable" if FROZEN else "Dev Mode"
        ctk.CTkLabel(
            self,
            text=f"{APP_NAME} v{VERSION} ({mode_txt})  •  Engine: yt-dlp v{yt_dlp.version.__version__}"
                 f"  •  FFmpeg: {ffmpeg_txt}  •  1800+ sites supported",
            font=(FONT, 11), text_color=MUTED).pack(side="bottom", pady=(0, 12))

    def _build_header(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=28, pady=(22, 4))

        # ---- Logo (tumhari Veltra.png ya fallback) ----
        if LOGO_PNG:
            try:
                img = rounded_img(Image.open(LOGO_PNG), (48, 48), 14)
                self._logo_img = ctk.CTkImage(light_image=img, dark_image=img, size=(48, 48))
                ctk.CTkLabel(bar, image=self._logo_img, text="").pack(side="left")
            except Exception:
                self._fallback_logo(bar)
        else:
            self._fallback_logo(bar)

        title_box = ctk.CTkFrame(bar, fg_color="transparent")
        title_box.pack(side="left", padx=13)
        ctk.CTkLabel(title_box, text=APP_NAME,
                     font=(FONT, 24, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(title_box, text="Grab Anything. In Max Quality.",
                     font=(FONT, 11), text_color=MUTED).pack(anchor="w")

        if not FROZEN:
            # Dev mode mein hi EXE builder dikhega (exe ke andar iski zaroorat nahi)
            self.build_btn = ctk.CTkButton(bar, text="🔨  Create EXE", width=130, height=34,
                                           corner_radius=10, fg_color="#173B26",
                                           hover_color="#1E4F33", text_color=ACCENT,
                                           font=(FONT, 12, "bold"), command=self._build_exe)
            self.build_btn.pack(side="right", pady=(4, 0), padx=(10, 0))

        self.update_btn = ctk.CTkButton(bar, text="⟳  Update Engine", width=138, height=34,
                                        corner_radius=10, fg_color=ENTRY_BG, hover_color=BORDER,
                                        text_color=TEXT, font=(FONT, 12, "bold"),
                                        command=self._update_engine)
        self.update_btn.pack(side="right", pady=(4, 0))

    def _fallback_logo(self, bar):
        logo = ctk.CTkFrame(bar, width=48, height=48, corner_radius=14, fg_color=ACCENT)
        logo.pack(side="left")
        logo.pack_propagate(False)
        ctk.CTkLabel(logo, text="▼", font=(FONT, 20, "bold"),
                     text_color="#062B12").pack(expand=True)

    def _build_url_card(self):
        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=18)
        card.pack(fill="x", padx=28, pady=(12, 0))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=16)

        ctk.CTkLabel(inner, text="VIDEO LINK", font=(FONT, 11, "bold"),
                     text_color=MUTED).pack(anchor="w")

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=(8, 0))

        self.url_entry = ctk.CTkEntry(
            row, placeholder_text="https://...  (YouTube, Dailymotion, Facebook, TikTok, Instagram...)",
            height=46, corner_radius=12, font=(FONT, 13),
            fg_color=ENTRY_BG, border_color=BORDER, border_width=1)
        self.url_entry.pack(side="left", fill="x", expand=True)
        self.url_entry.bind("<Return>", lambda e: self._fetch_info())

        ctk.CTkButton(row, text="📋", width=46, height=46, corner_radius=12,
                      fg_color=ENTRY_BG, hover_color=BORDER,
                      font=(FONT, 16), command=self._paste).pack(side="left", padx=(8, 0))

        self.fetch_btn = ctk.CTkButton(row, text="Fetch ⚡", width=100, height=46, corner_radius=12,
                                       fg_color=ENTRY_BG, hover_color=BORDER, text_color=TEXT,
                                       font=(FONT, 13, "bold"), command=self._fetch_info)
        self.fetch_btn.pack(side="left", padx=(8, 0))

    def _build_preview_card(self):
        self.preview = ctk.CTkFrame(self, fg_color=CARD, corner_radius=18)
        self.preview.pack(fill="x", padx=28, pady=14)
        ctk.CTkLabel(self.preview,
                     text="🔗  Link paste karo aur 'Fetch ⚡' dabao — video ki preview yahan dikhegi",
                     font=(FONT, 13), text_color=MUTED).pack(pady=36)

    def _build_options_card(self):
        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=18)
        card.pack(fill="x", padx=28)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=16)

        ctk.CTkLabel(inner, text="QUALITY", font=(FONT, 11, "bold"),
                     text_color=MUTED).pack(anchor="w")

        self.quality_seg = ctk.CTkSegmentedButton(
            inner, values=["Best", "2160p", "1080p", "720p", "480p", "MP3"],
            height=40, corner_radius=10, font=(FONT, 12, "bold"), text_color=TEXT,
            fg_color=ENTRY_BG, selected_color=ACCENT, selected_hover_color=ACCENT_HV,
            unselected_color=ENTRY_BG, unselected_hover_color=BORDER,
            command=self._quality_changed)
        self.quality_seg.set("Best")
        self.quality_seg.pack(fill="x", pady=(8, 6))

        self.quality_hint = ctk.CTkLabel(inner, text="Best = sabse highest quality (video + audio merge)",
                                         font=(FONT, 11), text_color=MUTED, anchor="w")
        self.quality_hint.pack(anchor="w")

    def _build_download_button(self):
        self.download_btn = ctk.CTkButton(
            self, text="⬇    D O W N L O A D    N O W",
            height=54, corner_radius=27, font=(FONT, 16, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HV, text_color="#062B12",
            command=self._start_download)
        self.download_btn.pack(fill="x", padx=28, pady=(18, 0))

    def _build_progress_card(self):
        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=18)
        card.pack(fill="x", padx=28, pady=(18, 0))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=16)

        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x")
        self.lbl_percent = ctk.CTkLabel(top, text="0 %", font=(FONT, 26, "bold"), text_color=ACCENT)
        self.lbl_percent.pack(side="left")

        stats = ctk.CTkFrame(top, fg_color="transparent")
        stats.pack(side="right")
        self.lbl_size = ctk.CTkLabel(stats, text="— / —", font=(FONT, 11), text_color=MUTED)
        self.lbl_size.pack(side="left", padx=(0, 16))
        self.lbl_speed = ctk.CTkLabel(stats, text="Speed: —", font=(FONT, 11), text_color=MUTED)
        self.lbl_speed.pack(side="left", padx=(0, 16))
        self.lbl_eta = ctk.CTkLabel(stats, text="ETA: —", font=(FONT, 11), text_color=MUTED)
        self.lbl_eta.pack(side="left")

        self.progress = ctk.CTkProgressBar(inner, progress_color=ACCENT, fg_color=ENTRY_BG,
                                           height=12, corner_radius=6)
        self.progress.set(0)
        self.progress.pack(fill="x", pady=(12, 12))

        bottom = ctk.CTkFrame(inner, fg_color="transparent")
        bottom.pack(fill="x")
        bottom.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(bottom, text="Ready — link paste karo",
                                         font=(FONT, 12), text_color=MUTED, anchor="w")
        self.status_label.grid(row=0, column=0, sticky="w")

        self.cancel_btn = ctk.CTkButton(bottom, text="✕  Cancel", width=96, height=32,
                                        corner_radius=9, fg_color="#2A1518", hover_color="#3B1D22",
                                        text_color=DANGER, font=(FONT, 12, "bold"),
                                        command=self._cancel)
        self.cancel_btn.grid(row=0, column=1, sticky="e", padx=(10, 0))
        self.cancel_btn.grid_remove()

        self.open_btn = ctk.CTkButton(bottom, text="📂  Open Folder", width=132, height=32,
                                      corner_radius=9, fg_color=ENTRY_BG, hover_color=BORDER,
                                      text_color=TEXT, font=(FONT, 12, "bold"),
                                      command=lambda: self._open_path(self._last_saved_folder))
        self.open_btn.grid(row=0, column=1, sticky="e", padx=(10, 0))
        self.open_btn.grid_remove()

    # ================= ACTIONS =================
    def _paste(self):
        try:
            clip = self.clipboard_get().strip()
            if clip:
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, clip)
                self._fetch_info()
        except Exception:
            pass

    def _quality_changed(self, value):
        hints = {
            "Best": "Best = sabse highest quality (video + audio merge)",
            "MP3": "MP3 = sirf awaz niklegi (music, podcast, lecture)",
        }
        self.quality_hint.configure(
            text=hints.get(value, f"{value} pe locked rahegi quality"))

    def _fetch_info(self):
        url = self.url_entry.get().strip()
        if not url or self.busy:
            return
        self.fetch_btn.configure(state="disabled", text="...")
        self._status("🔍 Video ki info nikal rahe hain...", MUTED)

        def work():
            try:
                opts = {"quiet": True, "no_warnings": True,
                        "skip_download": True, "noplaylist": True}
                if FFMPEG_PATH:
                    opts["ffmpeg_location"] = FFMPEG_PATH
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                self.after(0, lambda: self._show_preview(info))
                self._status("✅ Preview loaded — quality chuno aur DOWNLOAD dabao", ACCENT)
            except Exception as e:
                self._status("❌ " + str(e).splitlines()[0][:80], DANGER)
            finally:
                self.after(0, lambda: self.fetch_btn.configure(state="normal", text="Fetch ⚡"))

        threading.Thread(target=work, daemon=True).start()

    def _show_preview(self, info):
        for w in self.preview.winfo_children():
            w.destroy()
        row = ctk.CTkFrame(self.preview, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=14)

        self._load_thumb(info.get("thumbnail"), row)

        box = ctk.CTkFrame(row, fg_color="transparent")
        box.pack(side="left", fill="x", expand=True, padx=(16, 4))

        title = info.get("title") or "Unknown Title"
        if len(title) > 72:
            title = title[:69] + "..."
        ctk.CTkLabel(box, text=title, font=(FONT, 15, "bold"), text_color=TEXT,
                     wraplength=440, justify="left", anchor="w").pack(anchor="w")

        dur = info.get("duration_string")
        if not dur and info.get("duration"):
            d = info["duration"]
            dur = f"{d // 60}:{d % 60:02d}"
        parts = []
        if info.get("uploader") or info.get("channel"):
            parts.append("👤 " + (info.get("uploader") or info.get("channel")))
        if dur:
            parts.append("⏱ " + dur)
        if info.get("view_count"):
            parts.append(f"👁 {info['view_count']:,}")
        ctk.CTkLabel(box, text="   •   ".join(parts) if parts else " ",
                     font=(FONT, 12), text_color=MUTED, anchor="w").pack(anchor="w", pady=(8, 0))

    def _load_thumb(self, url, parent):
        holder = ctk.CTkFrame(parent, width=190, height=110, corner_radius=14, fg_color=ENTRY_BG)
        holder.pack(side="left")
        holder.pack_propagate(False)
        ph = ctk.CTkLabel(holder, text="🎞", font=(FONT, 30), text_color=MUTED)
        ph.place(relx=0.5, rely=0.5, anchor="center")
        if not url:
            return

        def work():
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                raw = urllib.request.urlopen(req, timeout=15).read()
                img = Image.open(io.BytesIO(raw)).convert("RGB")
                w, h = img.size
                t = 16 / 9
                if w / h > t:
                    nw = int(h * t); x = (w - nw) // 2
                    img = img.crop((x, 0, x + nw, h))
                else:
                    nh = int(w / t); y = (h - nh) // 2
                    img = img.crop((0, y, w, y + nh))
                img = rounded_img(img, (190, 110), 14)

                def apply():
                    try:
                        self._thumb_img = ctk.CTkImage(light_image=img, dark_image=img,
                                                       size=(190, 110))
                        ph.destroy()
                        ctk.CTkLabel(holder, image=self._thumb_img, text="").place(
                            relx=0.5, rely=0.5, anchor="center")
                    except Exception:
                        pass
                self.after(0, apply)
            except Exception:
                pass

        threading.Thread(target=work, daemon=True).start()

    # ================= DOWNLOAD =================
    def _start_download(self):
        if self.busy:
            return
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Link Missing", "Pehle video ka link paste karo!")
            return

        # Directory popup download karte waqt
        folder = filedialog.askdirectory(title=f"📁 {APP_NAME} — Video kahan save karna hai?",
                                         initialdir=self.last_folder)
        if not folder:
            return
        self.last_folder = folder
        self._last_saved_folder = folder

        self.busy = True
        self.cancel_event.clear()
        self.download_btn.configure(state="disabled", text="D O W N L O A D I N G ...")
        self.fetch_btn.configure(state="disabled")
        self.open_btn.grid_remove()
        self.cancel_btn.grid()
        self.progress.set(0)
        self.lbl_percent.configure(text="0 %", text_color=ACCENT)
        self._status("🚀 Connecting...", MUTED)

        threading.Thread(target=self._run_download,
                         args=(url, folder, self.quality_seg.get()),
                         daemon=True).start()

    def _run_download(self, url, folder, quality):
        try:
            if quality == "MP3":
                fmt = "bestaudio/best"
            elif quality == "Best":
                fmt = "bestvideo+bestaudio/best"
            else:
                h = quality.replace("p", "")
                fmt = f"bestvideo[height<={h}]+bestaudio/best[height<={h}]"

            opts = {
                "format": fmt,
                "outtmpl": os.path.join(folder, "%(title)s.%(ext)s"),
                "merge_output_format": "mp4",
                "progress_hooks": [self._hook],
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "concurrent_fragment_downloads": 8,   # 4-5x speed (quality same rehti hai)
                "retries": 10,
                "windowsfilenames": True,
            }
            if FFMPEG_PATH:
                opts["ffmpeg_location"] = FFMPEG_PATH
            if quality == "MP3":
                opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }]

            self._status("⬇ Downloading...", MUTED)
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.extract_info(url, download=True)

            def done():
                self.progress.set(1.0)
                self.lbl_percent.configure(text="100 %", text_color=ACCENT)
                self.lbl_speed.configure(text="Speed: —")
                self.lbl_eta.configure(text="ETA: —")
                self._status(f"✅ Complete! Saved in: {folder}", ACCENT)
                self.open_btn.grid()
            self.after(0, done)

        except DownloadCancelled:
            self._status("⏹ Download cancel ho gaya", WARNING)
            self.after(0, lambda: self.progress.set(0))
            self.after(0, lambda: self.lbl_percent.configure(text="0 %"))
        except Exception as e:
            msg = str(e).splitlines()[0] if str(e) else "Unknown error"
            self._status("❌ " + msg[:90], DANGER)
        finally:
            self.after(0, self._reset_ui)

    def _hook(self, d):
        if self.cancel_event.is_set():
            raise DownloadCancelled()

        if d.get("status") == "finished":
            def merging():
                self.progress.set(1.0)
                self.lbl_percent.configure(text="100 %")
                self._status("🔧 Merging (ffmpeg)... thora sabar", MUTED)
            self.after(0, merging)
            return

        if d.get("status") != "downloading":
            return

        now = time.time()
        if now - self._last_tick < 0.12:
            return
        self._last_tick = now

        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        done = d.get("downloaded_bytes", 0)
        speed = d.get("speed")
        eta = d.get("eta")
        fc = d.get("fragment_count")

        if not total and fc:
            fi = d.get("fragment_index", 0)
            pct = (fi + 1) / fc if fc else 0
            size_txt = f"chunk {fi + 1}/{fc}"
        else:
            pct = (done / total) if total else 0.0
            size_txt = f"{human_size(done)} / {human_size(total) if total else '?'}"

        def up():
            self.progress.set(pct)
            self.lbl_percent.configure(text=f"{int(pct * 100)} %")
            self.lbl_size.configure(text=size_txt)
            self.lbl_speed.configure(
                text=f"Speed: {human_size(speed)}/s" if speed else "Speed: —")
            self.lbl_eta.configure(text=f"ETA: {human_eta(eta)}")
        self.after(0, up)

    # ================= BUILD EXE (andar hi builder!) =================
    def _build_exe(self):
        if self.busy:
            return
        ico = ICON_ICO
        png = LOGO_PNG
        if not png:
            ok = messagebox.askyesno(
                "Icon Missing",
                "Isi folder mein 'Veltra.png' nahi mili.\n\n"
                "Icon ke bina EXE banau? (default icon lagega)")
            if not ok:
                return

        self.busy = True
        self.download_btn.configure(state="disabled")
        self.fetch_btn.configure(state="disabled")
        if hasattr(self, "build_btn"):
            self.build_btn.configure(state="disabled", text="Building...")
        self._status("🔨 EXE build ho rahi hai — window band mat karna!", WARNING)
        threading.Thread(target=self._build_work, args=(ico, png), daemon=True).start()

    def _build_work(self, ico, png):
        try:
            cf = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            sep = ";" if os.name == "nt" else ":"
            script = os.path.abspath(__file__)

            self._status("⚙ Step 1/2: PyInstaller ready ho raha hai...", MUTED)
            r = subprocess.run([sys.executable, "-m", "pip", "install", "-U", "pyinstaller"],
                               capture_output=True, text=True, timeout=600, creationflags=cf)
            if r.returncode != 0:
                self._status("❌ PyInstaller install fail: " + (r.stderr or "")[:70], DANGER)
                return

            self._status("🔨 Step 2/2: EXE ban rahi hai (3-6 minute)...", MUTED)
            cmd = [sys.executable, "-m", "PyInstaller",
                   "--noconfirm", "--clean", "--onefile", "--noconsole",
                   "--name", APP_NAME]
            if ico:
                cmd += ["--icon", ico, "--add-data", f"{ico}{sep}."]
            if png:
                cmd += ["--add-data", f"{png}{sep}."]
            cmd += ["--collect-all", "customtkinter",
                    "--collect-all", "yt_dlp",
                    "--collect-all", "imageio_ffmpeg",
                    script]

            r = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=1800, creationflags=cf)
            exe = os.path.join(base_dir(), "dist", f"{APP_NAME}.exe")

            if r.returncode == 0 and os.path.exists(exe):
                self._status(f"✅ DONE!  {exe}", ACCENT)
                self._open_path(os.path.join(base_dir(), "dist"))
            else:
                err = (r.stderr or r.stdout or "unknown error").strip().splitlines()
                self._status("❌ Build fail: " + (err[-1] if err else "?")[:80], DANGER)
        except Exception as e:
            self._status("❌ " + str(e)[:80], DANGER)
        finally:
            self.after(0, self._reset_ui)

    # ================= UPDATE ENGINE =================
    def _update_engine(self):
        if self.busy:
            return
        if FROZEN:
            messagebox.showinfo(
                f"{APP_NAME} — Update",
                "Ye portable build hai.\n\n"
                "YouTube naya system laaye to developer se updated EXE leni hogi, "
                "ya Veltra.py + Create EXE se nayi build banwani hogi.")
            return
        self._status("⟳ yt-dlp engine update ho raha hai... (1-2 min)", MUTED)

        def work():
            try:
                cf = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                r = subprocess.run([sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
                                   capture_output=True, text=True, timeout=300, creationflags=cf)
                if r.returncode == 0:
                    self._status("✅ Engine updated! App restart karo", ACCENT)
                else:
                    self._status("⚠️ Update fail: " + (r.stderr or "unknown")[:70], WARNING)
            except Exception as e:
                self._status("⚠️ " + str(e)[:70], WARNING)

        threading.Thread(target=work, daemon=True).start()

    # ================= MISC =================
    def _cancel(self):
        self.cancel_event.set()
        self._status("⏹ Cancelling...", WARNING)

    def _open_path(self, path):
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass

    def _reset_ui(self):
        self.busy = False
        self.cancel_event.clear()
        self.download_btn.configure(state="normal", text="⬇    D O W N L O A D    N O W")
        self.fetch_btn.configure(state="normal", text="Fetch ⚡")
        self.cancel_btn.grid_remove()
        if hasattr(self, "build_btn"):
            self.build_btn.configure(state="normal", text="🔨  Create EXE")

    def _status(self, text, color=MUTED):
        self.after(0, lambda: self.status_label.configure(text=text, text_color=color))

    def _on_close(self):
        self.cancel_event.set()
        self.destroy()


if __name__ == "__main__":
    app = VeltraApp()
    app.mainloop()