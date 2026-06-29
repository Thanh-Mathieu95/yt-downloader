// ─── State ────────────────────────────────────────────────────────────────────
let videoDuration   = 0;
let selectedPreset  = "best";
let selectedBrowser = "";
let hasFfmpeg       = false;
let jobs            = {};
let pollInterval    = null;

// ─── Boot ─────────────────────────────────────────────────────────────────────

async function boot() {
  await loadSystemStatus();
  await loadBrowsers();
  await checkCookiesStatus();
}

async function loadSystemStatus() {
  try {
    const r = await fetch("/api/system-status");
    const d = await r.json();
    hasFfmpeg = d.ffmpeg;
    document.getElementById("ffmpeg-banner").classList.toggle("hidden", hasFfmpeg);
  } catch (_) {}
}

// ─── ffmpeg install ───────────────────────────────────────────────────────────

async function installFfmpeg() {
  const btn = document.getElementById("btn-install-ffmpeg");
  btn.disabled = true;
  btn.textContent = "Đang cài...";
  document.getElementById("ffmpeg-install-progress").classList.remove("hidden");

  await fetch("/api/install-ffmpeg", { method: "POST" });
  pollFfmpegInstall();
}

function pollFfmpegInstall() {
  const iv = setInterval(async () => {
    const r = await fetch("/api/install-ffmpeg-status");
    const d = await r.json();
    document.getElementById("ffmpeg-bar").style.width = d.progress + "%";
    document.getElementById("ffmpeg-install-msg").textContent = d.status || "";

    if (d.done) {
      clearInterval(iv);
      hasFfmpeg = true;
      document.getElementById("ffmpeg-banner").classList.add("hidden");
      showToast("✓ ffmpeg đã cài xong! Reload để dùng chất lượng cao + Trim.");
    } else if (d.error) {
      clearInterval(iv);
      document.getElementById("ffmpeg-install-msg").textContent = "Lỗi: " + d.error;
      document.getElementById("btn-install-ffmpeg").disabled = false;
    }
  }, 1000);
}

// ─── Browser picker ───────────────────────────────────────────────────────────

function selectBrowser(id, btn) {
  selectedBrowser = id;
  document.querySelectorAll(".browser-btn").forEach(b => b.classList.remove("selected"));
  btn.classList.add("selected");
}

async function loadBrowsers() {
  try {
    const r = await fetch("/api/browsers");
    const browsers = await r.json();
    const container = document.getElementById("browser-btns");
    browsers.forEach(b => {
      const btn = document.createElement("button");
      btn.className = "browser-btn";
      btn.dataset.browser = b.id;
      btn.textContent = b.label;
      btn.onclick = () => selectBrowser(b.id, btn);
      container.appendChild(btn);
    });
    container.querySelector('[data-browser=""]').onclick = e => selectBrowser("", e.currentTarget);
  } catch (_) {}
}

// ─── Cookies ──────────────────────────────────────────────────────────────────

async function uploadCookies(input) {
  const file = input.files[0];
  if (!file) return;
  const form = new FormData();
  form.append("cookies", file);
  const r = await fetch("/api/upload-cookies", { method: "POST", body: form });
  const d = await r.json();
  if (!r.ok) { alert("Lỗi: " + d.error); return; }
  showCookiesStatus(true, false, 0);
  input.value = "";
  showToast("✓ cookies.txt đã lưu!");
}

async function deleteCookies() {
  await fetch("/api/delete-cookies", { method: "POST" });
  showCookiesStatus(false, false, null);
}

function showCookiesStatus(active, stale, ageHours) {
  document.getElementById("cookies-status").classList.toggle("hidden", !active);
  document.getElementById("upload-label").style.display = active ? "none" : "";
  const staleEl = document.getElementById("cookies-stale-warn");
  if (active && stale) {
    const h = ageHours ? Math.round(ageHours) : "?";
    staleEl.textContent = `⚠️ Cookie đã ${h} giờ — nên export lại để tránh lỗi "empty file"`;
    staleEl.classList.remove("hidden");
    document.getElementById("cookies-active-text").textContent = "⚠️ cookies.txt (có thể hết hạn)";
  } else {
    staleEl.classList.add("hidden");
    if (active) document.getElementById("cookies-active-text").textContent = "✓ cookies.txt đang hoạt động";
  }
}

async function checkCookiesStatus() {
  try {
    const r = await fetch("/api/system-status");
    const d = await r.json();
    showCookiesStatus(d.has_cookies_file, d.cookies_stale, d.cookies_age_hours);
  } catch (_) {}
}

// ─── Info fetch ───────────────────────────────────────────────────────────────

async function fetchInfo() {
  const url   = document.getElementById("url-input").value.trim();
  const errEl = document.getElementById("url-error");
  errEl.classList.add("hidden");
  if (!url) { showErr(errEl, "Chưa nhập URL."); return; }

  setBusy(true);
  try {
    const r = await fetch("/api/info", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, browser: selectedBrowser || null }),
    });
    const d = await r.json();
    if (!r.ok) { showErr(errEl, d.error); return; }
    renderInfo(d);
  } catch (e) {
    showErr(errEl, "Lỗi mạng: " + e.message);
  } finally {
    setBusy(false);
  }
}

function setBusy(on) {
  document.getElementById("fetch-text").classList.toggle("hidden", on);
  document.getElementById("fetch-spinner").classList.toggle("hidden", !on);
  document.getElementById("btn-fetch").disabled = on;
}

function showErr(el, msg) {
  el.textContent = msg;
  el.classList.remove("hidden");
}

// ─── Render video info ────────────────────────────────────────────────────────

function renderInfo(d) {
  videoDuration = d.duration || 0;
  hasFfmpeg     = d.ffmpeg;

  document.getElementById("thumbnail").src       = d.thumbnail || "";
  document.getElementById("video-title").textContent    = d.title || "";
  document.getElementById("video-uploader").textContent = d.uploader ? "Kênh: " + d.uploader : "";
  document.getElementById("video-duration").textContent = d.duration ? "Thời lượng: " + fmt(d.duration) : "";
  document.getElementById("video-views").textContent    = d.view_count ? "Lượt xem: " + d.view_count.toLocaleString() : "";

  // Quality
  const grid = document.getElementById("quality-list");
  grid.innerHTML = "";

  let firstEnabled = null;
  d.quality_options.forEach(q => {
    const btn = document.createElement("button");
    btn.className = "quality-btn" + (q.disabled ? " disabled-quality" : "");
    btn.disabled  = q.disabled;
    btn.innerHTML = `<span class="q-label">${q.label}</span>`;
    if (!q.disabled) {
      btn.onclick = () => {
        document.querySelectorAll(".quality-btn").forEach(b => b.classList.remove("selected"));
        btn.classList.add("selected");
        selectedPreset = q.key;
      };
      if (!firstEnabled) firstEnabled = { btn, key: q.key };
    }
    grid.appendChild(btn);
  });

  if (firstEnabled) {
    firstEnabled.btn.classList.add("selected");
    selectedPreset = firstEnabled.key;
  }

  // Trim
  const trimToggle = document.getElementById("trim-toggle");
  trimToggle.checked = false;
  document.getElementById("trim-controls").classList.add("hidden");
  document.getElementById("no-ffmpeg-trim-warn").classList.toggle("hidden", hasFfmpeg);

  // Timeline
  document.getElementById("end-time").value   = fmt(videoDuration);
  document.getElementById("start-time").value = "0:00";
  document.getElementById("tl-end-label").textContent   = fmt(videoDuration);
  document.getElementById("tl-start-label").textContent = "0:00";
  initTimeline();

  document.getElementById("video-info").classList.remove("hidden");
}

// ─── Trim ─────────────────────────────────────────────────────────────────────

function toggleTrim() {
  const on = document.getElementById("trim-toggle").checked;
  if (on && !hasFfmpeg) {
    document.getElementById("trim-toggle").checked = false;
    showToast("⚠️ Cần cài ffmpeg trước!");
    return;
  }
  document.getElementById("trim-controls").classList.toggle("hidden", !on);
}

function updateTimeline() {
  const s   = parseT(document.getElementById("start-time").value) || 0;
  const e   = parseT(document.getElementById("end-time").value)   || videoDuration;
  const dur = videoDuration || 1;
  const lp  = s / dur * 100;
  const rp  = e / dur * 100;
  document.getElementById("tl-left").style.left    = lp + "%";
  document.getElementById("tl-right").style.left   = rp + "%";
  document.getElementById("tl-selected").style.left  = lp + "%";
  document.getElementById("tl-selected").style.width = (rp - lp) + "%";
  document.getElementById("tl-start-label").textContent = fmt(s);
  document.getElementById("tl-end-label").textContent   = fmt(e);
}

function initTimeline() {
  updateTimeline();
  const track = document.querySelector(".tl-track");
  drag(document.getElementById("tl-left"),  track, "start-time");
  drag(document.getElementById("tl-right"), track, "end-time");
}

function drag(handle, track, inputId) {
  const move = (cx) => {
    const r   = track.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (cx - r.left) / r.width));
    document.getElementById(inputId).value = fmt(pct * videoDuration);
    updateTimeline();
  };
  handle.addEventListener("mousedown", e => {
    e.preventDefault();
    const mm = e2 => move(e2.clientX);
    const mu = () => { removeEventListener("mousemove", mm); removeEventListener("mouseup", mu); };
    addEventListener("mousemove", mm);
    addEventListener("mouseup", mu);
  });
  handle.addEventListener("touchstart", e => {
    e.preventDefault();
    const tm = e2 => move(e2.touches[0].clientX);
    const tu = () => { removeEventListener("touchmove", tm); removeEventListener("touchend", tu); };
    addEventListener("touchmove", tm, { passive: false });
    addEventListener("touchend", tu);
  });
}

// ─── Download ─────────────────────────────────────────────────────────────────

async function startDownload() {
  const url    = document.getElementById("url-input").value.trim();
  const trimOn = document.getElementById("trim-toggle").checked;
  const start  = trimOn ? parseT(document.getElementById("start-time").value) : null;
  const end    = trimOn ? parseT(document.getElementById("end-time").value)   : null;
  const title  = document.getElementById("video-title").textContent.trim();

  const r = await fetch("/api/download", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, preset_key: selectedPreset, start_time: start, end_time: end, browser: selectedBrowser || null, title }),
  });
  const d = await r.json();
  if (!r.ok) { alert("Lỗi: " + d.error); return; }

  jobs[d.job_id] = { id: d.job_id, status: "starting", progress: 0 };
  renderJobs();
  if (!pollInterval) pollInterval = setInterval(pollJobs, 1200);
}

async function pollJobs() {
  const active = Object.keys(jobs).filter(id => !["done","error","cancelled"].includes(jobs[id].status));
  if (!active.length) { clearInterval(pollInterval); pollInterval = null; return; }
  for (const id of active) {
    const r = await fetch("/api/status/" + id);
    if (r.ok) jobs[id] = { id, ...await r.json() };
  }
  renderJobs();
}

function renderJobs() {
  const list = document.getElementById("jobs-list");
  const sec  = document.getElementById("active-jobs");
  const arr  = Object.values(jobs);
  sec.classList.toggle("hidden", !arr.length);
  list.innerHTML = "";
  [...arr].reverse().forEach(job => {
    const done      = job.status === "done";
    const err       = job.status === "error";
    const cancelled = job.status === "cancelled";
    const active    = !done && !err && !cancelled;
    const speedInfo = job.speed ? `<span class="job-speed">${job.speed}</span>` : "";
    const div = document.createElement("div");
    div.className = "job-card";
    div.innerHTML = `
      <div class="job-title">${job.title || "Đang xử lý..."}</div>
      <div class="job-status-row">
        <span class="job-status ${done?"job-done":err?"job-error":cancelled?"job-cancelled":""}">${statusLabel(job.status)}</span>
        ${speedInfo}
        ${active ? `<button class="btn-cancel" onclick="cancelJob('${job.id}')">✕ Dừng</button>` : ""}
      </div>
      ${active ? `<div class="progress-bar"><div class="progress-fill" style="width:${job.progress}%"></div><span class="progress-pct">${job.progress}%</span></div>` : ""}
      ${done ? `<div class="job-actions"><button class="btn-dl" onclick="dlFile('${job.filename}')">⬇ Lưu về máy</button></div>` : ""}
      ${err  ? `<div class="job-error-msg">${job.error}</div>` : ""}
    `;
    list.appendChild(div);
  });
}

function statusLabel(s) {
  return { starting:"Đang bắt đầu...", downloading:"Đang tải...", merging:"Đang ghép video+âm thanh...",
           processing:"Đang xử lý...", trimming:"Đang cắt video...", retrying:"Đang thử lại...",
           done:"✓ Hoàn thành!", cancelled:"✕ Đã dừng", error:"✗ Lỗi" }[s] || s;
}

async function cancelJob(id) {
  jobs[id].status = "cancelled";
  renderJobs();
  await fetch("/api/cancel/" + id, { method: "POST" });
}

function dlFile(name) {
  const a = document.createElement("a");
  a.href = "/api/download-file/" + encodeURIComponent(name);
  a.download = name;
  a.click();
}

// ─── Files panel ──────────────────────────────────────────────────────────────

function toggleFilesPanel() {
  const panel   = document.getElementById("files-panel");
  const overlay = document.getElementById("files-overlay");
  const open    = panel.classList.toggle("open");
  panel.classList.toggle("hidden", !open);
  overlay.classList.toggle("hidden", !open);
  if (open) loadFiles();
}

async function loadFiles() {
  const list = document.getElementById("files-list");
  list.innerHTML = '<p class="muted center">Đang tải...</p>';
  const files = await (await fetch("/api/files")).json();
  if (!files.length) { list.innerHTML = '<p class="muted center">Chưa có file nào.</p>'; return; }
  list.innerHTML = "";
  files.forEach(f => {
    const div = document.createElement("div");
    div.className = "file-item";
    div.innerHTML = `
      <div class="file-name">${f.name}</div>
      <div class="file-size muted">${fmtSize(f.size)}</div>
      <div class="file-actions">
        <button class="btn-sm btn-dl-sm" onclick="dlFile('${f.name}')">⬇ Tải</button>
        <button class="btn-sm btn-del-sm" onclick="delFile('${f.name}',this)">🗑</button>
      </div>`;
    list.appendChild(div);
  });
}

async function delFile(name, btn) {
  if (!confirm("Xóa " + name + "?")) return;
  await fetch("/api/delete-file", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({filename:name}) });
  btn.closest(".file-item").remove();
}

// ─── Update yt-dlp ────────────────────────────────────────────────────────────

async function updateYtdlp() {
  const btn = document.getElementById("btn-update");
  btn.disabled = true; btn.textContent = "Đang cập nhật...";
  showToast("Đang cập nhật yt-dlp, chờ ~30 giây...", 30000);
  const r = await fetch("/api/update-ytdlp", { method: "POST" });
  const d = await r.json();
  showToast(r.ok ? `✓ yt-dlp đã cập nhật lên ${d.version}!` : "Lỗi: " + d.error);
  btn.disabled = false; btn.textContent = "↑ Update yt-dlp";
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmt(sec) {
  sec = Math.round(sec || 0);
  const h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), s = sec % 60;
  return h ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}
function pad(n) { return String(n).padStart(2, "0"); }

function parseT(str) {
  if (!str) return null;
  const parts = str.split(":").map(Number);
  if (parts.some(isNaN)) return null;
  if (parts.length === 3) return parts[0]*3600 + parts[1]*60 + parts[2];
  if (parts.length === 2) return parts[0]*60 + parts[1];
  return parts[0];
}

function fmtSize(b) {
  if (b < 1024) return b + " B";
  if (b < 1048576) return (b/1024).toFixed(1) + " KB";
  if (b < 1073741824) return (b/1048576).toFixed(1) + " MB";
  return (b/1073741824).toFixed(2) + " GB";
}

function showToast(msg, ms = 4000) {
  document.querySelector(".toast")?.remove();
  const el = document.createElement("div");
  el.className = "toast"; el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), ms);
}

// ─── Init ─────────────────────────────────────────────────────────────────────

document.getElementById("url-input").addEventListener("keydown", e => { if (e.key === "Enter") fetchInfo(); });
boot();
