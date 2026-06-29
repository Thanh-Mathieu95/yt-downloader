# YT Downloader

A local YouTube video downloader for Windows — no bloatware, no ads, no data sent to external servers.

Runs as a web interface in your browser with quality selection, video trimming, and download management.

---

## Features

- Download videos from **144p up to 1080p**
- **Trim video** before downloading — pick start/end with a slider
- Auto-installs **ffmpeg** from within the app (required for 720p+)
- Cookie authentication via **cookies.txt** or directly from your browser
- **One-click yt-dlp update**
- View and manage downloaded files
- **Cancel** an ongoing download
- Can be built into a standalone **`.exe`** — no Python required on end user's machine

---

## Requirements

- Windows 10 / 11
- **Python 3.10+** ([download at python.org](https://www.python.org/downloads/))
  - During install: check **"Add Python to PATH"**

---

## Option 1 — Run from source (for developers)

### Step 1: Clone the repo

```bash
git clone https://github.com/Thanh-Mathieu95/yt-downloader.git
cd yt-downloader
```

### Step 2: Install dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Start the app

**Quickest way** — double-click `start.bat`

Or run manually:

```bash
python app.py
```

Then open your browser at: **http://localhost:5000**

---

## Option 2 — Build a standalone `.exe`

This creates a `.exe` that runs on any Windows machine without Python or any other dependencies.

### Step 1: Get yt-dlp.exe

Download `yt-dlp.exe` from [github.com/yt-dlp/yt-dlp/releases/latest](https://github.com/yt-dlp/yt-dlp/releases/latest) and place it in the project root (same folder as `app.py`).

### Step 2: Build

Double-click `build.bat` — it will auto-install PyInstaller and build.

### Step 3: Get the output

After building, the full app is in:

```
dist\YTDownloader\
```

Zip that folder and **share it with anyone** — they just unzip and double-click `YTDownloader.exe`.

---

## Usage

### 1. Set up YouTube cookies (required)

YouTube requires authentication to download videos. Two options:

#### Option A — cookies.txt file (recommended)

1. Install the **"Get cookies.txt LOCALLY"** extension for Chrome/Edge
2. Open [youtube.com](https://youtube.com) and **sign in**
3. Click the extension icon → **Export**
4. Save `cookies.txt`
5. In the app, click **"Select cookies.txt"** and upload the file

> Cookies may expire after ~24h. If you get errors, export fresh cookies.

#### Option B — Use browser directly

1. **Fully close** Chrome/Edge (including tray icon)
2. Select your browser name in the app
3. Click **Fetch info** — the app reads cookies directly from your browser profile

> If the browser isn't fully closed you'll get "Could not copy cookie database".

---

### 2. Download a video

1. Paste a YouTube URL into the input field
2. Click **Fetch info** — the app shows the thumbnail, title, and duration
3. Choose a **quality** (144p → 1080p)
4. *(Optional)* Enable **Trim** → drag the slider or type start/end times
5. Click **Download**
6. Watch the progress bar — when done click **Save to device**

---

### 3. Install ffmpeg (needed for 720p+)

If you see a yellow **"ffmpeg not found"** banner:

- Click **"Auto-install ffmpeg"** — the app downloads and sets it up (~90MB)
- Or install manually from [ffmpeg.org](https://ffmpeg.org/download.html) and place `ffmpeg.exe` in the `ffmpeg/` folder

---

### 4. Update yt-dlp

YouTube changes frequently — yt-dlp needs periodic updates.

If you see **"nsig extraction failed"** or videos fail to download:
- Click **"↑ Update yt-dlp"** in the top-right corner

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `HTTP Error 403` | Expired cookies | Export a fresh cookies.txt |
| `Could not copy cookie database` | Browser still running | Fully close Chrome/Edge and retry |
| `Sign in to confirm` | No cookies set | Upload cookies.txt from a signed-in account |
| `nsig extraction failed` | Outdated yt-dlp | Click "↑ Update yt-dlp" |
| `Requested format is not available` | Quality not available | Select a lower quality — app will auto-retry |
| Video Private | Video is private | Cannot download |
| Age-restricted | Age restriction | Need cookies from an age-verified account |

---

## Project Structure

```
yt-downloader/
├── app.py              # Flask backend — all core logic
├── requirements.txt    # Python dependencies
├── start.bat           # Quick start script (Windows)
├── build.bat           # Build script for .exe
├── YTDownloader.spec   # PyInstaller config
├── templates/
│   └── index.html      # UI template
└── static/
    ├── script.js       # Frontend logic
    └── style.css       # Styles
```

These folders are created automatically at runtime (not in repo):

```
downloads/   # Downloaded videos
ffmpeg/      # ffmpeg binary (auto-installed via app)
```

---

## Tech Stack

- **Backend:** Python 3, Flask
- **Downloader:** yt-dlp
- **Video processing:** ffmpeg
- **Frontend:** HTML / CSS / Vanilla JavaScript
- **Desktop build:** PyInstaller

---

## Legal

This tool is intended for **personal learning and research only**. Downloading copyrighted content without permission from the rights holder violates [YouTube's Terms of Service](https://www.youtube.com/t/terms). Use responsibly.
