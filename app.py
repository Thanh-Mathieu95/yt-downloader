import os, threading, subprocess, uuid, re, shutil, zipfile, urllib.request, json, sys, time, webbrowser
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file

try:
    import yt_dlp as _yt_dlp_module
except ImportError:
    _yt_dlp_module = None

_FROZEN = getattr(sys, "frozen", False)

if _FROZEN:
    # APP_DIR  — next to the .exe: user-writable files (downloads, cookies, ffmpeg)
    # BUNDLE_DIR — _internal/: read-only bundled files (templates, static, yt-dlp.exe)
    APP_DIR    = Path(sys.executable).parent
    BUNDLE_DIR = Path(sys._MEIPASS)
else:
    APP_DIR    = Path(__file__).parent
    BUNDLE_DIR = Path(__file__).parent

BASE_DIR      = APP_DIR
DOWNLOADS_DIR = APP_DIR / "downloads"
FFMPEG_DIR    = APP_DIR / "ffmpeg"
COOKIES_FILE  = APP_DIR / "cookies.txt"
DOWNLOADS_DIR.mkdir(exist_ok=True)
FFMPEG_DIR.mkdir(exist_ok=True)

app = Flask(__name__,
            template_folder=str(BUNDLE_DIR / "templates"),
            static_folder=str(BUNDLE_DIR / "static"))

jobs: dict[str, dict] = {}
ffmpeg_install_status: dict = {"running": False, "progress": 0, "done": False, "error": None, "status": ""}

BROWSER_PATHS = {
    "chrome":  Path(os.environ.get("LOCALAPPDATA","")) / "Google/Chrome/User Data",
    "edge":    Path(os.environ.get("LOCALAPPDATA","")) / "Microsoft/Edge/User Data",
    "firefox": Path(os.environ.get("APPDATA",""))      / "Mozilla/Firefox/Profiles",
    "brave":   Path(os.environ.get("LOCALAPPDATA","")) / "BraveSoftware/Brave-Browser/User Data",
    "opera":   Path(os.environ.get("APPDATA",""))      / "Opera Software/Opera Stable",
    "vivaldi": Path(os.environ.get("LOCALAPPDATA","")) / "Vivaldi/User Data",
}
BROWSER_LABELS = {"chrome":"Chrome","edge":"Edge","firefox":"Firefox","brave":"Brave","opera":"Opera","vivaldi":"Vivaldi"}

QUALITY_PRESETS = [
    {"key":"best",  "label":"Tốt nhất (tự động)", "height":None, "fmt":"bestvideo+bestaudio/best"},
    {"key":"1080p", "label":"1080p Full HD",       "height":1080, "fmt":"bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"},
    {"key":"720p",  "label":"720p HD",             "height":720,  "fmt":"bestvideo[height<=720]+bestaudio/best[height<=720]/best"},
    {"key":"480p",  "label":"480p",                "height":480,  "fmt":"best[height<=480]/best"},
    {"key":"360p",  "label":"360p",                "height":360,  "fmt":"best[height<=360]/best"},
    {"key":"144p",  "label":"144p (nhỏ nhất)",     "height":144,  "fmt":"best[height<=144]/worst"},
]

# ─── yt-dlp CLI helpers ───────────────────────────────────────────────────────

def ytdlp_cmd() -> list[str]:
    if _FROZEN:
        # Bundled mode: use the yt-dlp.exe packed alongside the app
        for d in [BUNDLE_DIR, APP_DIR]:
            exe = d / "yt-dlp.exe"
            if exe.exists():
                return [str(exe)]
    # Dev mode: always use the installed Python package (correct version)
    if _yt_dlp_module is not None:
        main = Path(_yt_dlp_module.__file__).parent / "__main__.py"
        return [sys.executable, str(main)]
    raise RuntimeError("yt-dlp không tìm thấy!")

def common_flags(browser: str | None = None) -> list[str]:
    flags = [
        "--extractor-args", "youtube:player_client=tv_embedded",
        "--no-playlist",
    ]
    if COOKIES_FILE.exists():
        flags += ["--cookies", str(COOKIES_FILE)]
    elif browser and browser in BROWSER_PATHS and BROWSER_PATHS[browser].exists():
        flags += ["--cookies-from-browser", browser]
    return flags

def has_cookies(browser: str | None) -> bool:
    return COOKIES_FILE.exists() or (
        bool(browser) and browser in BROWSER_PATHS and BROWSER_PATHS[browser].exists()
    )

# ─── Misc helpers ─────────────────────────────────────────────────────────────

def sanitize(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()

def get_ffmpeg() -> str | None:
    local = FFMPEG_DIR / "ffmpeg.exe"
    if local.exists(): return str(local)
    found = shutil.which("ffmpeg")
    if found: return found
    for p in [r"C:\ffmpeg\bin\ffmpeg.exe", r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"]:
        if os.path.exists(p): return p
    return None

def detect_browsers() -> list[dict]:
    return [{"id":k,"label":BROWSER_LABELS[k]} for k,v in BROWSER_PATHS.items() if v.exists()]

def cookies_age_hours() -> float | None:
    if not COOKIES_FILE.exists(): return None
    return (time.time() - COOKIES_FILE.stat().st_mtime) / 3600

def _friendly_error(raw: str) -> str:
    r = raw.lower()
    if "downloaded file is empty" in r or ("http error 403" in r and "googlevideo" in r):
        return ("❌ YouTube chặn tải — stream trả về 403!\n\n"
                "Cách sửa:\n"
                "① Xóa cookies.txt cũ → mở youtube.com → đăng nhập → Export lại\n"
                "② Upload file cookies.txt MỚI vào app\n"
                "③ Thử chọn chất lượng thấp hơn (360p / 480p)")
    if "could not copy" in r and "cookie" in r:
        return ("❌ Browser đang mở → không đọc được cookie!\n\n"
                "→ Đóng hoàn toàn Chrome/Edge rồi thử lại\n"
                "→ Hoặc dùng cookies.txt (không cần đóng browser)")
    if "no longer valid" in r or "rotated" in r:
        return "❌ Cookie đã bị rotate/hết hạn!\n→ Xóa cookies.txt cũ và export lại"
    if "sign in to confirm" in r or ("bot" in r and "sign" in r):
        return ("❌ YouTube yêu cầu đăng nhập!\n\n"
                "→ Upload cookies.txt từ trình duyệt đã đăng nhập YouTube")
    if "requested format is not available" in r:
        return "requested format is not available"
    if "nsig extraction failed" in r or "player_url" in r:
        return ("❌ yt-dlp cần cập nhật để giải mã URL mới của YouTube!\n\n"
                "→ Bấm nút '↑ Update yt-dlp' ở góc trên bên phải")
    if "private video" in r: return "❌ Video Private — không thể tải"
    if "video unavailable" in r: return "❌ Video không khả dụng ở khu vực này"
    if "age-restricted" in r or "age restricted" in r:
        return "❌ Video giới hạn độ tuổi — cần cookies.txt từ tài khoản YouTube đã đăng nhập"
    return raw[:400] if len(raw) > 400 else raw

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index(): return render_template("index.html")

@app.route("/api/system-status")
def system_status():
    result = subprocess.run(ytdlp_cmd() + ["--version"], capture_output=True, text=True)
    age = cookies_age_hours()
    return jsonify({
        "ffmpeg": get_ffmpeg() is not None,
        "ytdlp_version": result.stdout.strip(),
        "has_cookies_file": COOKIES_FILE.exists(),
        "cookies_age_hours": age,
        "cookies_stale": age is not None and age > 24,
        "browsers": detect_browsers(),
    })

@app.route("/api/browsers")
def browsers(): return jsonify(detect_browsers())

# ── ffmpeg install ─────────────────────────────────────────────────────────────

@app.route("/api/install-ffmpeg", methods=["POST"])
def install_ffmpeg():
    if ffmpeg_install_status["running"]:
        return jsonify({"error": "Already installing"}), 400
    threading.Thread(target=_install_ffmpeg_worker, daemon=True).start()
    return jsonify({"ok": True})

@app.route("/api/install-ffmpeg-status")
def install_ffmpeg_status_route(): return jsonify(ffmpeg_install_status)

def _install_ffmpeg_worker():
    s = ffmpeg_install_status
    s.update(running=True, progress=5, done=False, error=None, status="Đang tải ffmpeg (~90MB)...")
    try:
        zip_path = FFMPEG_DIR / "ffmpeg_download.zip"
        def hook(c, b, total):
            if total > 0: s["progress"] = int(5 + c*b/total*80)
        urllib.request.urlretrieve(
            "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
            zip_path, hook)
        s.update(progress=85, status="Đang giải nén...")
        with zipfile.ZipFile(zip_path) as z:
            for m in z.namelist():
                if m.endswith("/bin/ffmpeg.exe"):
                    (FFMPEG_DIR/"ffmpeg.exe").write_bytes(z.read(m))
                if m.endswith("/bin/ffprobe.exe"):
                    (FFMPEG_DIR/"ffprobe.exe").write_bytes(z.read(m))
        zip_path.unlink(missing_ok=True)
        s.update(progress=100, done=True, status="Hoàn thành!")
    except Exception as e:
        s.update(error=str(e), status="Lỗi: "+str(e))
    finally:
        s["running"] = False

# ── yt-dlp update ─────────────────────────────────────────────────────────────

@app.route("/api/update-ytdlp", methods=["POST"])
def update_ytdlp():
    try:
        if _FROZEN or (BASE_DIR / "yt-dlp.exe").exists():
            # Download new yt-dlp.exe directly
            url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
            tmp = BASE_DIR / "yt-dlp.new.exe"
            urllib.request.urlretrieve(url, str(tmp))
            dst = BASE_DIR / "yt-dlp.exe"
            dst.unlink(missing_ok=True)
            tmp.rename(dst)
        else:
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade",
                            "--force-reinstall", "yt-dlp"],
                           capture_output=True, text=True, timeout=120)
        ver = subprocess.run(ytdlp_cmd() + ["--version"], capture_output=True, text=True).stdout.strip()
        return jsonify({"ok": True, "version": ver})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── cookies ───────────────────────────────────────────────────────────────────

@app.route("/api/upload-cookies", methods=["POST"])
def upload_cookies():
    f = request.files.get("cookies")
    if not f: return jsonify({"error":"No file"}), 400
    content = f.read().decode("utf-8", errors="replace")
    if "youtube.com" not in content and "google.com" not in content:
        return jsonify({"error":"File này không phải cookies YouTube. Export từ youtube.com."}), 400
    COOKIES_FILE.write_text(content, encoding="utf-8")
    return jsonify({"ok": True})

@app.route("/api/delete-cookies", methods=["POST"])
def delete_cookies():
    COOKIES_FILE.unlink(missing_ok=True)
    return jsonify({"ok": True})

# ── video info ────────────────────────────────────────────────────────────────

@app.route("/api/info", methods=["POST"])
def get_info():
    data    = request.json
    url     = (data.get("url") or "").strip()
    browser = data.get("browser") or None
    if not url: return jsonify({"error":"Chưa nhập URL"}), 400
    if not has_cookies(browser):
        return jsonify({"error":"⚠️ Cần cookies YouTube!\nChọn trình duyệt hoặc upload cookies.txt"}), 400

    cmd = ytdlp_cmd() + common_flags(browser) + [
        "--dump-json", "--no-download", "--no-warnings", url
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0:
            err = (r.stderr or r.stdout).strip()
            # Extract the last ERROR: line
            for line in reversed(err.splitlines()):
                if "ERROR:" in line:
                    err = line.split("ERROR:",1)[-1].strip()
                    break
            return jsonify({"error": _friendly_error(err)}), 400
        info = json.loads(r.stdout.strip().splitlines()[-1])
    except subprocess.TimeoutExpired:
        return jsonify({"error":"Timeout — kiểm tra kết nối mạng"}), 400
    except Exception as e:
        return jsonify({"error": _friendly_error(str(e))}), 400

    available_heights = {f.get("height") for f in info.get("formats",[]) if f.get("height")}
    max_height = max(available_heights) if available_heights else 9999

    quality_options = []
    for p in QUALITY_PRESETS:
        h = p["height"]
        if h and h > max_height: continue
        quality_options.append({"key":p["key"],"label":p["label"],"disabled":False})

    return jsonify({
        "title":           info.get("title","Unknown"),
        "duration":        info.get("duration", 0),
        "thumbnail":       info.get("thumbnail",""),
        "uploader":        info.get("uploader",""),
        "view_count":      info.get("view_count", 0),
        "quality_options": quality_options,
        "ffmpeg":          get_ffmpeg() is not None,
    })

# ── download ──────────────────────────────────────────────────────────────────

@app.route("/api/download", methods=["POST"])
def start_download():
    data       = request.json
    url        = (data.get("url") or "").strip()
    preset_key = data.get("preset_key") or "best"
    start_time = data.get("start_time")
    end_time   = data.get("end_time")
    browser    = data.get("browser") or None
    title      = (data.get("title") or "").strip()
    if not url: return jsonify({"error":"Chưa nhập URL"}), 400

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status":"starting","progress":0,"filename":None,"error":None,"title":title}
    threading.Thread(target=_dl_worker,
                     args=(job_id, url, preset_key, start_time, end_time, browser),
                     daemon=True).start()
    return jsonify({"job_id": job_id})


def _dl_worker(job_id, url, preset_key, start_time, end_time, browser):
    job    = jobs[job_id]
    ffmpeg = get_ffmpeg()
    trim   = bool((start_time is not None or end_time is not None) and ffmpeg)

    fmt = next((p["fmt"] for p in QUALITY_PRESETS if p["key"] == preset_key), "best")

    _attempt(job_id, job, url, fmt, start_time, end_time, browser, ffmpeg, trim)

    # Auto-retry with "best" if the specific format wasn't available (skip if cancelled)
    if job.get("status") == "error" and job.get("status") != "cancelled" and "requested format is not available" in str(job.get("error", "")):
        job.update(status="starting", error=None, progress=0, speed="")
        _attempt(job_id, job, url, "best", start_time, end_time, browser, ffmpeg, trim)
        if job.get("status") == "error":
            job["error"] = ("❌ Không thể tải video này.\n\n"
                            "Thử:\n• Upload lại cookies.txt mới từ youtube.com\n"
                            "• Chọn chất lượng thấp hơn (360p / 480p)")


def _attempt(job_id, job, url, fmt, start_time, end_time, browser, ffmpeg, trim):
    tmp_name = f"tmp_{job_id}"
    tmp_tmpl = str(DOWNLOADS_DIR / f"{tmp_name}.%(ext)s")

    # Clean up any leftover partial files from a previous attempt
    for stale in DOWNLOADS_DIR.glob(f"{tmp_name}.*"):
        stale.unlink(missing_ok=True)

    cmd = ytdlp_cmd() + common_flags(browser) + [
        "-f", fmt,
        "-o", tmp_tmpl,
        "--no-warnings",
        "--newline",
        "--progress",
    ]
    if ffmpeg:
        ffmpeg_dir = str(FFMPEG_DIR) if (FFMPEG_DIR / "ffmpeg.exe").exists() else os.path.dirname(ffmpeg)
        cmd += ["--ffmpeg-location", ffmpeg_dir, "--merge-output-format", "mp4"]
    cmd.append(url)

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace",
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        job["_proc"] = proc
        all_lines = []
        for line in proc.stdout:
            line = line.rstrip()
            all_lines.append(line)
            m = re.search(r'(\d+\.?\d*)%\s+of\s+~?([\d.]+\w+)\s+at\s+([\d.]+\w+/s)', line)
            if m:
                job["progress"] = int(float(m.group(1)) * (0.7 if trim else 0.9))
                job["status"]   = "downloading"
                job["speed"]    = m.group(3)
                job["size"]     = m.group(2)
            elif re.search(r'(\d+\.?\d*)%', line):
                job["progress"] = int(float(re.search(r'(\d+\.?\d*)%', line).group(1)) * (0.7 if trim else 0.9))
                job["status"]   = "downloading"
            if "[Merger]" in line or "Merging" in line:
                job.update(status="merging", progress=90, speed="")
            if "ERROR:" in line:
                job["error"] = line.split("ERROR:", 1)[-1].strip()  # raw, for retry check

        proc.wait()
        job.pop("_proc", None)

        if job.get("status") == "cancelled":
            for f in DOWNLOADS_DIR.glob(f"{tmp_name}.*"):
                f.unlink(missing_ok=True)
            return

        if proc.returncode != 0:
            if not job.get("error"):
                err_lines = [l for l in all_lines if "ERROR:" in l]
                job["error"] = err_lines[-1].split("ERROR:", 1)[-1].strip() if err_lines else f"yt-dlp exited {proc.returncode}"
            job["error"] = _friendly_error(job["error"])
            job["status"] = "error"
            return

        downloaded = next((f for f in DOWNLOADS_DIR.iterdir() if f.stem == tmp_name), None)
        if not downloaded:
            job.update(status="error", error="File không tìm thấy sau khi tải xong")
            return

        title = sanitize(job.get("title") or "video") or "video"
        final = DOWNLOADS_DIR / f"{title}.mp4"
        n = 1
        while final.exists():
            final = DOWNLOADS_DIR / f"{title}_{n}.mp4"
            n += 1

        if trim:
            job.update(status="trimming", progress=88, speed="")
            _trim(ffmpeg, downloaded, final, start_time, end_time)
            downloaded.unlink(missing_ok=True)
        else:
            downloaded.rename(final)

        job.update(status="done", progress=100, filename=final.name, speed="")

    except Exception as e:
        job.update(status="error", error=_friendly_error(str(e)))


def _trim(ffmpeg, src, dst, t_start, t_end):
    cmd = [ffmpeg, "-y"]
    if t_start: cmd += ["-ss", str(t_start)]
    cmd += ["-i", str(src)]
    if t_end:   cmd += ["-t", str(t_end-(t_start or 0))]
    cmd += ["-c:v","libx264","-c:a","aac","-movflags","+faststart", str(dst)]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg trim failed:\n" + r.stderr.decode(errors="replace")[-300:])

# ── misc ──────────────────────────────────────────────────────────────────────

@app.route("/api/status/<job_id>")
def job_status(job_id):
    j = jobs.get(job_id)
    if not j:
        return jsonify({"error": "Not found"}), 404
    return jsonify({k: v for k, v in j.items() if not k.startswith("_")})

@app.route("/api/cancel/<job_id>", methods=["POST"])
def cancel_job(job_id):
    j = jobs.get(job_id)
    if not j:
        return jsonify({"error": "Not found"}), 404
    proc = j.get("_proc")
    j["status"] = "cancelled"
    if proc and proc.poll() is None:
        if os.name == "nt":
            # Kill entire process tree (yt-dlp + ffmpeg children)
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True)
        else:
            import signal
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    return jsonify({"ok": True})

@app.route("/api/download-file/<filename>")
def download_file(filename):
    p = DOWNLOADS_DIR / filename
    return send_file(p, as_attachment=True, download_name=filename) if p.exists() else ("Not found", 404)

@app.route("/api/files")
def list_files():
    files = [{"name":f.name,"size":f.stat().st_size,"modified":f.stat().st_mtime}
             for f in DOWNLOADS_DIR.iterdir()
             if f.is_file() and not f.name.startswith("tmp_")]
    return jsonify(sorted(files, key=lambda x: x["modified"], reverse=True))

@app.route("/api/delete-file", methods=["POST"])
def delete_file():
    p = DOWNLOADS_DIR / (request.json.get("filename") or "")
    if p.exists() and p.parent == DOWNLOADS_DIR: p.unlink()
    return jsonify({"ok": True})



if __name__ == "__main__":
    try:
        ver = subprocess.run(ytdlp_cmd() + ["--version"], capture_output=True, text=True).stdout.strip()
    except Exception:
        ver = "not found"
    print(f"\n{'='*50}\n  YouTube Downloader\n  yt-dlp {ver}")
    print(f"  ffmpeg: {get_ffmpeg() or 'not found'}")
    print(f"  Open: http://localhost:5000\n{'='*50}\n")
    if _FROZEN:
        threading.Timer(1.5, lambda: webbrowser.open("http://localhost:5000")).start()
    app.run(debug=False, port=5000, host="127.0.0.1")
