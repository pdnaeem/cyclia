// Cyclia desktop shell: starts the local calculation engine and opens the window.
const { app, BrowserWindow, dialog, ipcMain, shell, Menu, protocol, net } = require("electron");
const BUILD = "ui-fix-4";
const { spawn } = require("child_process");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

let autoUpdater = null;
try { ({ autoUpdater } = require("electron-updater")); } catch (e) { /* not bundled in development */ }

let engine = null;
let logStream = null;
function appLog(line) {
  try {
    if (!logStream) {
      const dir = path.join(app.getPath("userData"), "logs");
      fs.mkdirSync(dir, { recursive: true });
      logStream = fs.createWriteStream(path.join(dir, "desktop.log"), { flags: "a" });
    }
    logStream.write(`${new Date().toISOString()} ${line}\n`);
  } catch (e) { /* logging must never break the app */ }
}
let win = null;
let quitting = false;
const token = crypto.randomBytes(16).toString("hex");

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => { if (win) { if (win.isMinimized()) win.restore(); win.focus(); } });
}

// The engine (Python) cannot read inside app.asar. Electron can, so on every start the UI is copied
// out of the archive into a plain folder the engine can serve. This does not depend on the installer layout.
function copyDir(src, dst) {
  fs.mkdirSync(dst, { recursive: true });
  for (const name of fs.readdirSync(src)) {
    const s = path.join(src, name), d = path.join(dst, name);
    if (fs.statSync(s).isDirectory()) copyDir(s, d);
    else fs.writeFileSync(d, fs.readFileSync(s));
  }
}
function uiDir() {
  const source = path.join(__dirname, "ui");
  if (!app.isPackaged) return source;
  const candidates = [];
  try {
    const target = path.join(app.getPath("userData"), "ui");
    fs.rmSync(target, { recursive: true, force: true });
    copyDir(source, target);
    candidates.push(target);
  } catch (e) { appLog("ui copy failed: " + e.message); }
  candidates.push(path.join(process.resourcesPath || "", "ui"));
  for (const c of candidates) {
    if (fs.existsSync(path.join(c, "index.html"))) { appLog("ui folder: " + c); return c; }
  }
  throw new Error("The interface files were not found. Tried:\n" + candidates.join("\n") + "\n\nPlease reinstall Cyclia.");
}

function engineCommand() {
  const dataDir = path.join(app.getPath("userData"), "data");
  const common = ["--port", "0", "--data", dataDir, "--token", token];
  // Installed app: standalone engine built with PyInstaller (no Python needed on the user's computer)
  const exe = process.platform === "win32" ? "cyclia-engine.exe" : "cyclia-engine";
  const bundled = path.join(process.resourcesPath || "", "engine", exe);
  if (app.isPackaged && fs.existsSync(bundled)) return { cmd: bundled, args: common };
  // Development: run server.py with the local Python
  const script = path.join(__dirname, "..", "engine", "server.py");
  const py = process.env.CYCLIA_PYTHON || (process.platform === "win32" ? "python" : "python3");
  return { cmd: py, args: [script, ...common] };
}

function startEngine() {
  return new Promise((resolve, reject) => {
    const { cmd, args } = engineCommand();
    engine = spawn(cmd, args, {
      env: { ...process.env, CYCLIA_UI: uiDir(), PYTHONUNBUFFERED: "1", PYTHONIOENCODING: "utf-8" },
      windowsHide: true,
    });
    let log = "";
    let ready = false;
    const timer = setTimeout(() => reject(new Error("The engine did not start within 90 seconds.\n\n" + log.slice(-2000))), 90000);
    engine.stdout.on("data", (d) => {
      const s = d.toString();
      log += s;
      const m = s.match(/CYCLIA_READY port=(\d+)/);
      if (m && !ready) { ready = true; clearTimeout(timer); resolve(Number(m[1])); }
    });
    engine.stderr.on("data", (d) => { log += d.toString(); appLog("engine: " + d.toString().trim()); });
    engine.on("error", (e) => { clearTimeout(timer); reject(new Error(`Could not run "${cmd}": ${e.message}`)); });
    engine.on("exit", (code) => {
      clearTimeout(timer);
      if (!ready) { reject(new Error(`The engine stopped (code ${code}).\n\n${log.slice(-3000)}`)); return; }
      if (!quitting) {
        dialog.showErrorBox("Cyclia engine stopped",
          `The calculation engine closed unexpectedly (code ${code}). Your projects are saved. Cyclia will now close; please start it again.\n\n${log.slice(-1500)}`);
        app.quit();
      }
    });
  });
}


// The window's pages (not /api/) are served by Electron straight from the app files, so the interface
// shows even if the engine cannot find its own copy. API calls still go to the engine on the same origin.
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8", ".png": "image/png", ".svg": "image/svg+xml", ".json": "application/json" };
function serveUiFromApp(port) {
  const origin = `http://127.0.0.1:${port}`;
  const root = path.join(__dirname, "ui");
  protocol.handle("http", (req) => {
    const u = new URL(req.url);
    if (u.origin !== origin || u.pathname.startsWith("/api/")) return net.fetch(req, { bypassCustomProtocolHandlers: true });
    let rel = decodeURIComponent(u.pathname);
    if (rel === "/" || rel === "") rel = "/index.html";
    const full = path.normalize(path.join(root, rel));
    if (!full.startsWith(root)) return new Response("Forbidden", { status: 403 });
    try {
      let data = fs.readFileSync(full);
      if (full.endsWith("index.html")) data = Buffer.from(data.toString("utf8").replace("__API_TOKEN__", token), "utf8");
      return new Response(data, { headers: { "Content-Type": MIME[path.extname(full).toLowerCase()] || "application/octet-stream", "Cache-Control": "no-store" } });
    } catch (e) {
      appLog("ui file missing: " + full);
      return net.fetch(req, { bypassCustomProtocolHandlers: true });
    }
  });
  appLog("ui served by app from " + root);
}

// Splash with the author credit while the engine starts (a few seconds on first launch).
let splash = null;
function showSplash() {
  splash = new BrowserWindow({ width: 560, height: 330, frame: false, resizable: false, movable: true, show: false,
    center: true, skipTaskbar: false, backgroundColor: "#12271f", icon: path.join(__dirname, "ui", "icon.png"),
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true } });
  splash.once("ready-to-show", () => splash && splash.show());
  splash.loadFile(path.join(__dirname, "splash.html")).catch(() => {});
  splash.on("closed", () => { splash = null; });
}
function closeSplash() { if (splash && !splash.isDestroyed()) splash.close(); }

async function createWindow() {
  const shownAt = Date.now();
  showSplash();
  win = new BrowserWindow({
    width: 1400, height: 900, minWidth: 1000, minHeight: 660, title: "Cyclia", show: false,
    backgroundColor: "#f6f5f0", icon: path.join(__dirname, "ui", "icon.png"),
    webPreferences: { preload: path.join(__dirname, "preload.js"), contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  win.once("ready-to-show", () => {
    // keep the splash (and its credit) on screen for at least 1.8 s
    setTimeout(() => { win.show(); closeSplash(); }, Math.max(0, 1800 - (Date.now() - shownAt)));
  });
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^(https?:\/\/|mailto:)/.test(url)) shell.openExternal(url);
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (e, url) => { if (!url.startsWith("http://127.0.0.1:")) e.preventDefault(); });
  try {
    const port = await startEngine();
    serveUiFromApp(port);
    await win.loadURL(`http://127.0.0.1:${port}/`);
  } catch (e) {
    closeSplash();
    dialog.showErrorBox("Cyclia could not start",
      `${e.message}\n\nIf you are running from source, install Python 3.10+ and run: pip install -r engine/requirements.txt`);
    app.quit();
  }
}

ipcMain.handle("pick-folder", async () => {
  const r = await dialog.showOpenDialog(win, { properties: ["openDirectory"] });
  return r.canceled ? null : r.filePaths[0];
});
ipcMain.handle("pick-file", async (_e, ext) => {
  const filters = ext ? [{ name: String(ext).toUpperCase(), extensions: [String(ext)] }, { name: "All files", extensions: ["*"] }] : [];
  const r = await dialog.showOpenDialog(win, { properties: ["openFile"], filters });
  return r.canceled ? null : r.filePaths[0];
});
ipcMain.handle("save-file", async (_e, name, ext) => {
  const r = await dialog.showSaveDialog(win, {
    defaultPath: path.join(app.getPath("documents"), String(name || "export")),
    filters: [{ name: String(ext).toUpperCase(), extensions: [String(ext)] }],
  });
  return r.canceled ? null : r.filePath;
});
ipcMain.handle("open-path", (_e, p) => shell.openPath(String(p)));
ipcMain.handle("show-in-folder", (_e, p) => shell.showItemInFolder(String(p)));
ipcMain.handle("app-log-path", () => path.join(app.getPath("userData"), "logs", "desktop.log"));

function checkForUpdates() {
  if (!autoUpdater || !app.isPackaged) return;
  try { if (/YOUR_GITHUB_USER/.test(fs.readFileSync(path.join(__dirname, "package.json"), "utf8"))) return; } catch (e) { return; }
  autoUpdater.logger = { info: appLog, warn: appLog, error: appLog, debug: () => {} };
  autoUpdater.autoDownload = true;
  autoUpdater.on("update-downloaded", async (info) => {
    const r = await dialog.showMessageBox(win, { type: "info", buttons: ["Restart now", "Later"], defaultId: 0,
      message: `Cyclia ${info.version} is ready to install.`, detail: "Your projects are saved. Restart to finish the update." });
    if (r.response === 0) { quitting = true; autoUpdater.quitAndInstall(); }
  });
  autoUpdater.on("error", (e) => appLog("update check failed: " + (e && e.message)));
  autoUpdater.checkForUpdates().catch((e) => appLog("update check failed: " + e.message));
}
process.on("uncaughtException", (e) => appLog("uncaught: " + (e && e.stack)));

app.whenReady().then(() => {
  if (app.isPackaged) Menu.setApplicationMenu(null);
  appLog(`start ${app.getVersion()} (${BUILD}) on ${process.platform}`);
  createWindow().then(() => setTimeout(checkForUpdates, 8000));
});
app.on("before-quit", () => { quitting = true; });
app.on("window-all-closed", () => app.quit());
app.on("quit", () => { if (engine && !engine.killed) engine.kill(); });
