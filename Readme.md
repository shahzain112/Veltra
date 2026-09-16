<div align="center">


<div align="center">

---

## 📸 Screenshot

<div align="center">

---

## ✨ Features

- 🎯 **1800+ Supported Sites** — YouTube, Dailymotion, Facebook, TikTok, Instagram, Twitter/X, Vimeo, Reddit & many more
- 🖼 **Live Video Preview** — paste a link and instantly see the thumbnail, title, channel & views before downloading
- 🏆 **Highest Quality Engine** — up to 4K (2160p) with automatic video + audio merging via FFmpeg
- 🎵 **MP3 Extraction** — convert any video to audio with one click
- 🚀 **8x Parallel Downloads** — fragmented downloading for 4-5x faster speeds
- 📊 **Real-Time Progress** — live speed, ETA, downloaded size & percentage
- 📁 **Directory Picker** — choose your save location on every download
- 🌓 **Premium Dark UI** — Spotify-inspired interface built with CustomTkinter
- 🔄 **Self-Updating Engine** — one-click yt-dlp engine update from inside the app
- 📦 **Portable EXE** — single `.exe` file, no Python installation required
- ❌ **Cancel Anytime** — stop downloads mid-way with a single click

---

## 🛠 Tech Stack

| Component        | Technology                  |
| ---------------- | --------------------------- |
| Language         | Python 3.9+                 |
| Download Engine  | yt-dlp                      |
| GUI Framework    | CustomTkinter               |
| Media Processing | FFmpeg (via imageio-ffmpeg) |
| Image Handling   | Pillow                      |
| Packaging        | PyInstaller                 |

---

## 📥 Installation

### Option 1 — Ready-Made EXE (Recommended for users)

1. Download `Veltra.exe` from the [Releases](../../releases) page
2. Double-click and run — no installation needed!

> ⚠️ If Windows SmartScreen shows a warning, click **"More info" → "Run anyway"** (this happens because the app is not code-signed yet).

### Option 2 — Run from Source (Developers)

```bash
# 1. Clone the repository
git clone https://github.com/shahzain112/Veltra
cd Veltra

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
python Veltra.py
```

---

## 🚀 Usage

1. Paste any video link (or click the 📋 button to auto-paste from clipboard)
2. Click **Fetch ⚡** — see the live preview of the video
3. Select quality — Best / 2160p / 1080p / 720p / 480p / MP3
4. Hit **DOWNLOAD** — choose your folder and watch the magic happen!

<div align="center">

---

## 📦 Building the EXE

Want to build your own portable `.exe`?

1. Run the app from source: `python Veltra.py`
2. Click the **🔨 Create EXE** button inside the app
3. Wait 3-6 minutes — your `dist/Veltra.exe` will be ready!

Or manually via CLI:

```bash
pyinstaller --noconfirm --clean --onefile --noconsole --name Veltra --icon Veltra_icon.ico --collect-all customtkinter --collect-all yt_dlp --collect-all imageio_ffmpeg Veltra.py
```

---

## 🤝 Contributing

Contributions are welcome and appreciated! 🎉
Whether it's a bug fix, a new feature, UI improvement, or documentation — every contribution counts.

**How to Contribute:**

1. Fork the repository
2. Create your feature branch
   ```bash
   git checkout -b feature/AmazingFeature
   ```
3. Commit your changes
   ```bash
   git commit -m "Add some AmazingFeature"
   ```
4. Push to the branch
   ```bash
   git push origin feature/AmazingFeature
   ```
5. Open a Pull Request ✅

**Ideas You Can Work On:**

- [ ] Playlist / batch downloads
- [ ] Download history panel
- [ ] Clipboard auto-detection
- [ ] Light theme
- [ ] Multi-language support (Urdu, Arabic...)
- [ ] Subtitles downloading
- [ ] Built-in update checker for releases

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](./LICENSE) file for details.

```
MIT License

Copyright (c) 2025 Shahzain Ahmed

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
