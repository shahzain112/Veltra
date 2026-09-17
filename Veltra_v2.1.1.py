"""
╔══════════════════════════════════════════════════════╗
║   VELTRA  v2.1.1                                     ║
║   Grab Anything. In Max Quality.                     ║
╠══════════════════════════════════════════════════════╣
║  TOOLS:                                              ║
║    📥 Downloader — 1800+ sites + English subtitles   ║
║    🕘 History    — every download remembered         ║
║    📋 Clipboard auto-detection                       ║
║                                                      ║
║  REQUIRED FILES IN FOLDER:                           ║
║    Veltra.py  +  Veltra.png (icon)                   ║
║                                                      ║
║  INSTALL:                                            ║
║    pip install customtkinter yt-dlp imageio-ffmpeg   ║
║    pip install pillow pyinstaller                    ║
║                                                      ║
║  RUN:        python Veltra.py                        ║
║  BUILD EXE:  Click "Create EXE" inside the app       ║
╚══════════════════════════════════════════════════════╝
"""

import os
import sys
import io
import json
import time
import gc
import traceback
import threading
import subprocess
import urllib.request

import tkinter as tk
import customtkinter as ctk
import yt_dlp
from tkinter import filedialog, messagebox
from PIL import Image, ImageDraw, ImageTk

# ------------- Instant-cancel exception (no yt-dlp retries) -------------
try:
    # yt-dlp's own cancellation exception — aborts the whole download
    # IMMEDIATELY without triggering any retry logic.
    CancelDownload = yt_dlp.utils.DownloadCancelled
except AttributeError:
    class CancelDownload(Exception):
        """Fallback for very old yt-dlp versions."""
        pass


class _VeltraYdlLogger:
    """Quiet logger for yt-dlp: subtitle fetch problems (like HTTP 429)
    are handled internally by our retry logic, so they never flood the
    console with scary ERROR lines."""
    def debug(self, msg):
        pass
    def warning(self, msg):
        pass
    def error(self, msg):
        text = str(msg)
        if "subtitle" not in text.lower():
            print(f"[yt-dlp] {text}")


# ================= CONSTANTS =================
VERSION = "2.1.1"
APP_NAME = "Veltra"
FROZEN = getattr(sys, "frozen", False)   # True when running inside the built EXE
WIN_W, WIN_H = 1040, 760                 # default window size (resizable)

# ---------------- FFmpeg auto-setup (FIXED) ----------------
def _setup_ffmpeg():
    """imageio's binary is named 'ffmpeg-win-x86_64-vX.exe', but yt-dlp
    looks for 'ffmpeg.exe' inside a folder. So we make a properly
    named copy and hand yt-dlp that folder instead."""
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None
    try:
        import shutil
        import tempfile
        bin_dir = os.path.join(tempfile.gettempdir(), "VeltraFFmpeg")
        os.makedirs(bin_dir, exist_ok=True)
        target = os.path.join(bin_dir, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        # Copy on first run or when the version changes
        if not os.path.exists(target) or os.path.getsize(target) != os.path.getsize(exe):
            shutil.copy2(exe, target)
        print(f"[Veltra] FFmpeg ready: {target}")
        return bin_dir
    except Exception:
        return os.path.dirname(exe)

FFMPEG_PATH = _setup_ffmpeg()

# ---------------- Windows DPI (crisp UI on high-res screens) ----------------
if sys.platform == "win32":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

RESAMPLE = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS

# ---------------- Process priority (smoother downloads) ----------------
if sys.platform == "win32":
    try:
        import ctypes
        _handle = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.kernel32.SetPriorityClass(_handle, 0x00000080)  # HIGH_PRIORITY
    except Exception:
        pass

# Reduce garbage-collection pauses (fewer micro-stutters in the UI)
gc.set_threshold(50000, 15, 15)

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
    """Convert PNG to a Windows .ico (title bar + exe icon)"""
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

# ================= HISTORY STORAGE =================
HISTORY_FILE = os.path.join(base_dir(), "veltra_history.json")


def load_history():
    """Read the download history list (newest first)."""
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def save_history(entries):
    """Persist the download history list to disk."""
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


# ================= THEME (Veltra green — Spotify-inspired) =================
BG        = "#0A0A0C"   # app background
CARD      = "#141417"   # card surface
ENTRY_BG  = "#1B1B20"   # inputs
BORDER    = "#26262C"
ACCENT    = "#1DB954"   # Veltra green
ACCENT_HV = "#1ED760"
TEXT      = "#F2F2F5"
MUTED     = "#8B8B94"
DANGER    = "#FF5F57"
WARNING   = "#FEBC2E"
FONT      = "Segoe UI"

ctk.set_appearance_mode("dark")


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


# ============================================================
#                      PAGE 1: DOWNLOADER
# ============================================================
class DownloadPage(ctk.CTkFrame):
    def __init__(self, master, app=None):
        super().__init__(master, fg_color=BG)
        self.app = app   # reference to the main suite window

        self.last_folder = os.path.join(os.path.expanduser("~"), "Downloads")
        self._last_saved_folder = self.last_folder
        self.cancel_event = threading.Event()
        self.busy = False
        self._thumb_img = None
        self._last_tick = 0

        # Clipboard auto-detection state
        self._last_clip = None
        self._clipboard_job = None

        self._build_url_card()
        self._build_preview_card()
        self._build_options_card()
        self._build_action_buttons()
        self._build_progress_card()

        self._clipboard_watch()   # start clipboard auto-detection loop

    # ================= UI =================
    def _build_url_card(self):
        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=18)
        card.pack(fill="x", padx=28, pady=(14, 0))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=14)

        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text="VIDEO LINK", font=(FONT, 11, "bold"),
                     text_color=MUTED).pack(side="left")
        ctk.CTkLabel(top, text="auto-detects copied links 📋",
                     font=(FONT, 10), text_color=MUTED).pack(side="right")

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
        # FIXED height: when the preview loads, the layout never shifts,
        # so nothing below gets pushed out of the window.
        self.preview = ctk.CTkFrame(self, fg_color=CARD, corner_radius=18, height=150)
        self.preview.pack(fill="x", padx=28, pady=12)
        self.preview.pack_propagate(False)
        self.preview_placeholder = ctk.CTkLabel(
            self.preview,
            text="🔗  Copy any link — it will be detected automatically, or hit 'Fetch ⚡'",
            font=(FONT, 13), text_color=MUTED)
        self.preview_placeholder.pack(expand=True)

    def _build_options_card(self):
        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=18)
        card.pack(fill="x", padx=28)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=14)

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

        self.quality_hint = ctk.CTkLabel(
            inner,
            text="Best = maximum quality (H.264/AAC — plays on every player)",
            font=(FONT, 11), text_color=MUTED, anchor="w")
        self.quality_hint.pack(anchor="w")

        # ---- English subtitles switch ----
        self.subtitle_var = ctk.BooleanVar(value=True)   # ON by default (like YouTube CC)
        sub_row = ctk.CTkFrame(inner, fg_color="transparent")
        sub_row.pack(fill="x", pady=(12, 0))

        self.subtitle_switch = ctk.CTkSwitch(
            sub_row, text="CC  English subtitles — auto-download & translate",
            variable=self.subtitle_var, font=(FONT, 12, "bold"),
            progress_color=ACCENT, text_color=TEXT,
            button_color=TEXT, button_hover_color=ACCENT_HV)
        self.subtitle_switch.pack(side="left")

        self.subtitle_hint = ctk.CTkLabel(
            inner,
            text="Saves a .srt next to the video — any language is auto-translated to English (like YouTube CC)",
            font=(FONT, 10), text_color=MUTED, anchor="w")
        self.subtitle_hint.pack(anchor="w", pady=(4, 0))

    def _build_action_buttons(self):
        """Download and Cancel share the SAME slot — they swap places.
        This way Cancel is always visible while downloading."""
        self.action_holder = ctk.CTkFrame(self, fg_color="transparent")
        self.action_holder.pack(fill="x", padx=28, pady=(14, 0))

        # Download button (green)
        self.download_btn = ctk.CTkButton(
            self.action_holder, text="⬇    D O W N L O A D    N O W",
            height=54, corner_radius=27, font=(FONT, 16, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HV, text_color="#062B12",
            command=self._start_download)
        self.download_btn.pack(fill="x")

        # Cancel button (red) — same size, same slot, currently hidden
        self.cancel_btn = ctk.CTkButton(
            self.action_holder, text="✕    C A N C E L    D O W N L O A D",
            height=54, corner_radius=27, font=(FONT, 16, "bold"),
            fg_color="#2A1518", hover_color="#3B1D22", text_color=DANGER,
            command=self._cancel)

    def _build_progress_card(self):
        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=18)
        card.pack(fill="x", padx=28, pady=(14, 0))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=14)

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
        self.progress.pack(fill="x", pady=(10, 10))

        bottom = ctk.CTkFrame(inner, fg_color="transparent")
        bottom.pack(fill="x")
        bottom.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(bottom, text="Ready — paste or copy a link to start",
                                         font=(FONT, 12), text_color=MUTED, anchor="w")
        self.status_label.grid(row=0, column=0, sticky="w")

        self.open_btn = ctk.CTkButton(bottom, text="📂  Open Folder", width=132, height=32,
                                      corner_radius=9, fg_color=ENTRY_BG, hover_color=BORDER,
                                      text_color=TEXT, font=(FONT, 12, "bold"),
                                      command=lambda: self._open_path(self._last_saved_folder))
        self.open_btn.grid(row=0, column=1, sticky="e", padx=(10, 0))
        self.open_btn.grid_remove()

    # ================= CLIPBOARD AUTO-DETECTION =================
    def _clipboard_watch(self):
        """Polls the clipboard. When a new URL appears, it is filled into
        the entry box and the preview is fetched automatically."""
        try:
            clip = (self.clipboard_get() or "").strip()
        except Exception:
            clip = ""   # clipboard had a non-text item (image etc.)

        if clip:
            already_known = (clip == self._last_clip or clip == self.url_entry.get().strip())
            is_url = clip.startswith("http://") or clip.startswith("https://")
            on_download_page = (self.app is None
                                or getattr(self.app, "_current_page", "download") == "download")

            if is_url and not already_known and not self.busy and on_download_page:
                self._last_clip = clip
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, clip)
                self._status("📋 Link auto-detected from clipboard — fetching preview...", ACCENT)
                self._fetch_info()
            else:
                self._last_clip = clip

        self._clipboard_job = self.after(1500, self._clipboard_watch)

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
            "Best": "Best = maximum quality (H.264/AAC — plays on every player)",
            "MP3": "MP3 = audio only (music, podcasts, lectures)",
        }
        self.quality_hint.configure(
            text=hints.get(value, f"Quality will be capped at {value} (H.264 preferred)"))

    def _fetch_info(self):
        url = self.url_entry.get().strip()
        if not url or self.busy:
            return
        self.fetch_btn.configure(state="disabled", text="...")
        self._status("🔍 Fetching video info...", MUTED)

        def work():
            try:
                opts = {"quiet": True, "no_warnings": True,
                        "skip_download": True, "noplaylist": True}
                if FFMPEG_PATH:
                    opts["ffmpeg_location"] = FFMPEG_PATH
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                self.after(0, lambda: self._show_preview(info))
                self._status("✅ Preview loaded — pick a quality and hit DOWNLOAD", ACCENT)
            except Exception as e:
                self._status("❌ " + str(e).splitlines()[0][:80], DANGER)
            finally:
                self.after(0, lambda: self.fetch_btn.configure(state="normal", text="Fetch ⚡"))

        threading.Thread(target=work, daemon=True).start()

    def _show_preview(self, info):
        self.preview_placeholder.pack_forget()
        for w in self.preview.winfo_children():
            if w is not self.preview_placeholder:
                w.destroy()

        row = ctk.CTkFrame(self.preview, fg_color="transparent")
        row.pack(fill="both", expand=True, padx=16, pady=12)

        self._load_thumb(info.get("thumbnail"), row)

        box = ctk.CTkFrame(row, fg_color="transparent")
        box.pack(side="left", fill="x", expand=True, padx=(16, 4))

        title = info.get("title") or "Unknown Title"
        if len(title) > 72:
            title = title[:69] + "..."
        ctk.CTkLabel(box, text=title, font=(FONT, 15, "bold"), text_color=TEXT,
                     wraplength=500, justify="left", anchor="w").pack(anchor="w")

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
                pass  # keep the placeholder if the thumbnail fails

        threading.Thread(target=work, daemon=True).start()

    # ================= DOWNLOAD =================
    def _start_download(self):
        if self.busy:
            return
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Link Missing", "Paste a video link first!")
            return

        # Ask where to save (every download)
        folder = filedialog.askdirectory(title=f"📁 {APP_NAME} — Choose where to save the video",
                                         initialdir=self.last_folder)
        if not folder:
            return
        self.last_folder = folder
        self._last_saved_folder = folder

        self.busy = True
        self.cancel_event.clear()

        # 🔥 SWAP: green DOWNLOAD disappears, red CANCEL takes its exact place
        self.download_btn.pack_forget()
        self.cancel_btn.pack(fill="x")
        self.fetch_btn.configure(state="disabled")
        self.open_btn.grid_remove()

        self.progress.set(0)
        self.lbl_percent.configure(text="0 %", text_color=ACCENT)
        self._status("🚀 Connecting...", MUTED)

        threading.Thread(target=self._run_download,
                         args=(url, folder, self.quality_seg.get()),
                         daemon=True).start()

    def _run_download(self, url, folder, quality):
        info = None
        try:
            # 🎯 UNIVERSAL COMPATIBILITY:
            # H.264 (avc1) video + AAC (mp4a) audio is the worldwide standard.
            # Fallback chain (separated by /) ensures the download never fails:
            #   1st choice: H.264 + AAC
            #   2nd choice: any video + any audio
            #   3rd choice: single best combined file
            if quality == "MP3":
                fmt = "bestaudio/best"
            elif quality == "Best":
                fmt = ("bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/"
                       "bestvideo+bestaudio/best")
            else:
                h = quality.replace("p", "")
                fmt = (f"bestvideo[vcodec^=avc1][height<={h}]+bestaudio[acodec^=mp4a]/"
                       f"bestvideo[height<={h}]+bestaudio/best[height<={h}]")

            opts = {
                "format": fmt,
                "outtmpl": os.path.join(folder, "%(title)s.%(ext)s"),
                "merge_output_format": "mp4",
                "progress_hooks": [self._hook],
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "logger": _VeltraYdlLogger(),   # 🔇 keep the console clean
                "concurrent_fragment_downloads": 8,   # 4-5x speed (quality is unaffected)
                "retries": 10,
                "continuedl": True,                    # resume partial downloads
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

            # 🎬 ENGLISH SUBTITLES (like YouTube CC):
            #   "en" = native English captions AND YouTube's auto-translated
            #   English. One request keeps us safe from HTTP 429 rate limits.
            subs_enabled = self.subtitle_var.get()
            if subs_enabled:
                opts.update({
                    "writesubtitles": True,
                    "writeautomaticsub": True,
                    "subtitleslangs": ["en"],
                    "subtitlesformat": "srt/best",
                })

            self._status("⬇ Downloading...", MUTED)
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
            except CancelDownload:
                raise   # user pressed cancel — never retry, abort instantly
            except Exception as dl_err:
                # 🛡 SAFETY NET: if the subtitle request itself caused the
                # failure (rate limit, not available), retry once WITHOUT
                # subtitles so the video still downloads. The download must
                # never fail because of CC.
                if subs_enabled and "subtitle" in str(dl_err).lower():
                    self._status("⚠ Subtitles unavailable — retrying without CC...", WARNING)
                    for key in ("writesubtitles", "writeautomaticsub",
                                "subtitleslangs", "subtitlesformat"):
                        opts.pop(key, None)
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                else:
                    raise

            def done():
                self.progress.set(1.0)
                self.lbl_percent.configure(text="100 %", text_color=ACCENT)
                self.lbl_speed.configure(text="Speed: —")
                self.lbl_eta.configure(text="ETA: —")
                self._status(f"✅ Complete! Saved in: {folder}", ACCENT)
                self.open_btn.grid()
                self._record_history(info, folder, quality)
            self.after(0, done)

        except CancelDownload:
            self._status("⏹ Download cancelled", WARNING)
            self.after(0, lambda: self.progress.set(0))
            self.after(0, lambda: self.lbl_percent.configure(text="0 %"))
        except Exception as e:
            traceback.print_exc()   # full error in the terminal
            msg = str(e).splitlines()[0] if str(e) else "Unknown error"
            self._status("❌ " + msg[:90], DANGER)
            # 🔥 ERROR POPUP — failures are never silent!
            self.after(0, lambda m=msg: messagebox.showerror(
                f"{APP_NAME} — Download Failed", m))
        finally:
            self.after(0, self._reset_ui)

    def _record_history(self, info, folder, quality):
        """Save this download into the history (used by the History page)."""
        if not info:
            return
        title = info.get("title") or "Unknown Title"
        url = info.get("webpage_url") or ""
        # Try to locate the actual output file (merged mp4 / extracted mp3)
        file_path = None
        base = os.path.join(folder, title)
        for ext in (".mp4", ".mp3", ".mkv", ".webm"):
            if os.path.exists(base + ext):
                file_path = base + ext
                break

        entries = load_history()
        entries.insert(0, {
            "title": title,
            "url": url,
            "folder": folder,
            "quality": quality,
            "file": file_path,
            "time": time.strftime("%d %b %Y, %H:%M"),
        })
        entries = entries[:50]   # keep the last 50 downloads
        save_history(entries)

        # Refresh the history page if it exists
        if self.app and hasattr(self.app, "pages") and "history" in self.app.pages:
            self.app.pages["history"].refresh()

    def _hook(self, d):
        if self.cancel_event.is_set():
            # yt-dlp's native cancellation — aborts instantly, ZERO retries
            raise CancelDownload()

        if d.get("status") == "finished":
            def merging():
                self.progress.set(1.0)
                self.lbl_percent.configure(text="100 %")
                self._status("🔧 Merging (ffmpeg)... please wait", MUTED)
            self.after(0, merging)
            return

        if d.get("status") != "downloading":
            return

        now = time.time()
        if now - self._last_tick < 0.08:   # UI flood control
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

    # ================= BUILD EXE (built-in builder!) =================
    def _build_exe(self):
        if self.busy:
            return
        ico = ICON_ICO
        png = LOGO_PNG
        if not png:
            ok = messagebox.askyesno(
                "Icon Missing",
                "'Veltra.png' was not found in this folder.\n\n"
                "Build the EXE without an icon? (default icon will be used)")
            if not ok:
                return

        self.busy = True
        self.download_btn.configure(state="disabled")
        self.fetch_btn.configure(state="disabled")
        if self.app and hasattr(self.app, "build_btn"):
            self.app.build_btn.configure(state="disabled", text="Building...")
        self._status("🔨 Building EXE — do not close the window!", WARNING)
        threading.Thread(target=self._build_work, args=(ico, png), daemon=True).start()

    def _build_work(self, ico, png):
        try:
            cf = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            sep = ";" if os.name == "nt" else ":"
            script = os.path.abspath(__file__)

            self._status("⚙ Step 1/2: Preparing PyInstaller...", MUTED)
            r = subprocess.run([sys.executable, "-m", "pip", "install", "-U", "pyinstaller"],
                               capture_output=True, text=True, timeout=600, creationflags=cf)
            if r.returncode != 0:
                self._status("❌ PyInstaller install failed: " + (r.stderr or "")[:70], DANGER)
                return

            self._status("🔨 Step 2/2: Building EXE (3-6 minutes)...", MUTED)
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
                self._status("❌ Build failed: " + (err[-1] if err else "?")[:80], DANGER)
        except Exception as e:
            self._status("❌ " + str(e)[:80], DANGER)
        finally:
            self.after(0, self._reset_ui)

    # ================= UPDATE ENGINE (pip install -U yt-dlp) =================
    def _update_engine(self):
        if self.busy:
            return
        if FROZEN:
            messagebox.showinfo(
                f"{APP_NAME} — Update",
                "This is a portable build.\n\n"
                "When YouTube changes its system, get an updated EXE from the developer, "
                "or rebuild using Veltra.py + the Create EXE button.")
            return
        self._status("⟳ Updating yt-dlp engine... (pip install -U yt-dlp)", MUTED)

        def work():
            try:
                cf = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                r = subprocess.run([sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
                                   capture_output=True, text=True, timeout=300, creationflags=cf)
                if r.returncode == 0:
                    self._status("✅ Engine updated! Restart the app to load it", ACCENT)
                else:
                    self._status("⚠️ Update failed: " + (r.stderr or "unknown")[:70], WARNING)
            except Exception as e:
                self._status("⚠️ " + str(e)[:70], WARNING)

        threading.Thread(target=work, daemon=True).start()

    # ================= MISC =================
    def _cancel(self):
        if self.cancel_event.is_set():
            return
        self.cancel_event.set()
        self.cancel_btn.configure(state="disabled", text="Cancelling...")
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
        """Called after EVERY download (complete / cancelled / failed).
        Restores the UI to its idle state."""
        self.busy = False
        self.cancel_event.clear()
        # 🔥 SWAP BACK: red CANCEL disappears, green DOWNLOAD returns
        self.cancel_btn.pack_forget()
        self.download_btn.pack(fill="x")
        self.download_btn.configure(state="normal", text="⬇    D O W N L O A D    N O W")
        self.fetch_btn.configure(state="normal", text="Fetch ⚡")
        self.cancel_btn.configure(state="normal", text="✕    C A N C E L    D O W N L O A D")
        self.open_btn.grid_remove()
        if self.app and hasattr(self.app, "build_btn"):
            self.app.build_btn.configure(state="normal", text="🔨  Create EXE")

    def _status(self, text, color=MUTED):
        self.after(0, lambda: self.status_label.configure(text=text, text_color=color))


# ============================================================
#                      PAGE 2: HISTORY
# ============================================================
class HistoryPage(ctk.CTkFrame):
    def __init__(self, master, app=None):
        super().__init__(master, fg_color=BG)
        self.app = app
        self._entries = []

        # Header row: title + clear all
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=28, pady=(14, 0))
        ctk.CTkLabel(head, text="🕘  DOWNLOAD HISTORY",
                     font=(FONT, 15, "bold"), text_color=TEXT).pack(side="left")
        self.clear_btn = ctk.CTkButton(head, text="🗑  Clear All", width=100, height=30,
                                       corner_radius=9, fg_color="#2A1518",
                                       hover_color="#3B1D22", text_color=DANGER,
                                       font=(FONT, 11, "bold"), command=self._clear_all)
        self.clear_btn.pack(side="right")

        # Scrollable list of downloads
        self.list_frame = ctk.CTkScrollableFrame(self, fg_color=CARD, corner_radius=18)
        self.list_frame.pack(fill="both", expand=True, padx=28, pady=(10, 8))

        self.refresh()

    def refresh(self):
        """Rebuild the list from the stored history file."""
        for w in self.list_frame.winfo_children():
            w.destroy()

        self._entries = load_history()

        if not self._entries:
            ctk.CTkLabel(self.list_frame,
                         text="No downloads yet — your history will appear here 🕘",
                         font=(FONT, 13), text_color=MUTED).pack(pady=40)
            return

        for i, entry in enumerate(self._entries):
            self._build_row(entry, i)

    def _build_row(self, entry, index):
        row = ctk.CTkFrame(self.list_frame, fg_color=ENTRY_BG, corner_radius=12)
        row.pack(fill="x", padx=12, pady=6)

        # Left: title + meta
        info_box = ctk.CTkFrame(row, fg_color="transparent")
        info_box.pack(side="left", fill="x", expand=True, padx=14, pady=10)

        title = entry.get("title") or "Unknown"
        if len(title) > 60:
            title = title[:57] + "..."
        ctk.CTkLabel(info_box, text=title, font=(FONT, 13, "bold"),
                     text_color=TEXT, anchor="w").pack(anchor="w")

        meta = (entry.get("time", "") + "   •   " + entry.get("quality", "")
                + "   •   " + (entry.get("folder") or ""))
        ctk.CTkLabel(info_box, text=meta, font=(FONT, 10),
                     text_color=MUTED, anchor="w").pack(anchor="w", pady=(3, 0))

        # Right: action buttons
        ctk.CTkButton(row, text="▶  Play", width=76, height=32, corner_radius=9,
                      font=(FONT, 11, "bold"), fg_color=ACCENT, hover_color=ACCENT_HV,
                      text_color="#062B12",
                      command=lambda e=entry: self._play(e)).pack(side="right", padx=(8, 12))

        ctk.CTkButton(row, text="📂", width=40, height=32, corner_radius=9,
                      font=(FONT, 13), fg_color=ENTRY_BG, hover_color=BORDER,
                      text_color=TEXT,
                      command=lambda e=entry: self._open_folder(e)).pack(side="right", padx=4)

        ctk.CTkButton(row, text="✕", width=40, height=32, corner_radius=9,
                      font=(FONT, 12), fg_color="#2A1518", hover_color="#3B1D22",
                      text_color=DANGER,
                      command=lambda idx=index: self._remove(idx)).pack(side="right", padx=4)

    def _play(self, entry):
        """Open this download with the system's default media player."""
        file_path = entry.get("file")
        if file_path and os.path.exists(file_path):
            self._open_path(file_path)
        else:
            # File was moved or renamed — open the folder instead
            self._open_folder(entry)

    def _open_folder(self, entry):
        folder = entry.get("folder")
        if folder and os.path.isdir(folder):
            self._open_path(folder)

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

    def _remove(self, index):
        entries = load_history()
        if 0 <= index < len(entries):
            entries.pop(index)
            save_history(entries)
        self.refresh()

    def _clear_all(self):
        if messagebox.askyesno("Clear History",
                               "Delete the entire download history?\n(Downloaded files are NOT deleted)"):
            save_history([])
            self.refresh()


# ============================================================
#                    MAIN APP WINDOW
# ============================================================
class VeltraApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{VERSION}")
        self.geometry(f"{WIN_W}x{WIN_H}")
        self.resizable(True, True)          # maximize button works
        self.minsize(WIN_W, WIN_H)          # but cannot go smaller than the default
        self.configure(fg_color=BG)

        if ICON_ICO:
            try:
                self.iconbitmap(ICON_ICO)
            except Exception:
                pass

        # Center the window on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - WIN_W) // 2
        y = (self.winfo_screenheight() - WIN_H) // 2
        self.geometry(f"{WIN_W}x{WIN_H}+{x}+{y}")

        self._current_page = None

        # Pack order matters: footer first (bottom), then header (top), then body
        self._build_footer()
        self._build_header()

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(side="top", fill="both", expand=True)

        self._build_sidebar(body)

        self.page_container = ctk.CTkFrame(body, fg_color="transparent")
        self.page_container.pack(side="left", fill="both", expand=True)

        # ---- Create the tool pages ----
        self.pages = {}
        self.download_page = DownloadPage(self.page_container, app=self)
        self.history_page = HistoryPage(self.page_container, app=self)
        self.pages["download"] = self.download_page
        self.pages["history"] = self.history_page

        self._show_page("download")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ================= UI =================
    def _build_footer(self):
        ffmpeg_txt = "OK" if FFMPEG_PATH else "Not Found"
        mode_txt = "Portable" if FROZEN else "Dev Mode"
        self.footer_label = ctk.CTkLabel(
            self,
            text=f"{APP_NAME} v{VERSION} ({mode_txt})  •  Engine: yt-dlp v{yt_dlp.version.__version__}"
                 f"  •  FFmpeg: {ffmpeg_txt}  •  1800+ sites supported",
            font=(FONT, 11), text_color=MUTED)
        self.footer_label.pack(side="bottom", pady=(0, 10))

    def _build_header(self):
        self.header_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.header_bar.pack(side="top", fill="x", padx=28, pady=(18, 6))
        bar = self.header_bar

        # ---- Logo (user's Veltra.png or a fallback square) ----
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
            # EXE builder is only visible in dev mode
            self.build_btn = ctk.CTkButton(bar, text="🔨  Create EXE", width=130, height=34,
                                           corner_radius=10, fg_color="#173B26",
                                           hover_color="#1E4F33", text_color=ACCENT,
                                           font=(FONT, 12, "bold"),
                                           command=self.download_page_builder())
            self.build_btn.pack(side="right", pady=(4, 0), padx=(10, 0))

        self.update_btn = ctk.CTkButton(bar, text="⟳  Update Engine", width=140, height=34,
                                        corner_radius=10, fg_color=ENTRY_BG, hover_color=BORDER,
                                        text_color=TEXT, font=(FONT, 12, "bold"),
                                        command=lambda: self.pages["download"]._update_engine())
        self.update_btn.pack(side="right", pady=(4, 0))

    def download_page_builder(self):
        # Small helper so the header button can reach the download page
        # (pages are created after the header, so this resolves lazily)
        def call():
            if "download" in self.pages:
                self.pages["download"]._build_exe()
        return call

    def _fallback_logo(self, bar):
        logo = ctk.CTkFrame(bar, width=48, height=48, corner_radius=14, fg_color=ACCENT)
        logo.pack(side="left")
        logo.pack_propagate(False)
        ctk.CTkLabel(logo, text="▼", font=(FONT, 20, "bold"),
                     text_color="#062B12").pack(expand=True)

    # ================= SIDEBAR =================
    def _build_sidebar(self, body):
        self.sidebar = ctk.CTkFrame(body, width=200, fg_color=CARD, corner_radius=18)
        sidebar = self.sidebar
        sidebar.pack(side="left", fill="y", padx=(28, 12), pady=(10, 4))
        sidebar.pack_propagate(False)

        ctk.CTkLabel(sidebar, text="TOOLS", font=(FONT, 11, "bold"),
                     text_color=MUTED).pack(anchor="w", padx=20, pady=(20, 10))

        self.nav_btns = {}
        nav_items = {
            "download": ("📥", "Downloader"),
            "history": ("🕘", "History"),
        }
        for key, (icon, label) in nav_items.items():
            btn = ctk.CTkButton(
                sidebar, text=f" {icon}   {label}", anchor="w", height=46,
                corner_radius=12, font=(FONT, 14, "bold"),
                fg_color="transparent", hover_color=ENTRY_BG, text_color=TEXT,
                command=lambda k=key: self._show_page(k))
            btn.pack(fill="x", padx=12, pady=4)
            self.nav_btns[key] = btn

        # Spacer pushes the version note to the bottom of the sidebar
        ctk.CTkLabel(sidebar, text="").pack(expand=True)
        ctk.CTkLabel(sidebar, text=f"v{VERSION}",
                     font=(FONT, 11), text_color=MUTED).pack(pady=(0, 16))

    # ================= PAGE SWITCHING =================
    def _show_page(self, key):
        if self._current_page == key:
            return

        self._current_page = key
        for k, page in self.pages.items():
            if k == key:
                page.pack(fill="both", expand=True)
            else:
                page.pack_forget()

        # Highlight the active sidebar button
        for k, btn in self.nav_btns.items():
            if k == key:
                btn.configure(fg_color=ACCENT, hover_color=ACCENT_HV, text_color="#062B12")
            else:
                btn.configure(fg_color="transparent", hover_color=ENTRY_BG, text_color=TEXT)

    # ================= CLOSE =================
    def _on_close(self):
        self.download_page.cancel_event.set()   # stop any running download
        self.destroy()


if __name__ == "__main__":
    app = VeltraApp()
    app.mainloop()