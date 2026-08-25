// 星枢一体化壳 — 时序修正版: 后端就绪→加载→显示; 加载失败自动重试
const { app, BrowserWindow, Tray, Menu, globalShortcut, shell } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const http = require("http");

const PORT = 8899;
const URL_APP = `http://127.0.0.1:${PORT}`;
const BACKEND = path.join(__dirname, "StarPivot", "StarPivot.exe");

// ═══ 单实例锁: 重复双击只唤醒已有窗口, 不再开第二个 ═══
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    // 有人又双击了: 唤醒并置顶现有窗口
    if (win) {
      if (win.isMinimized()) win.restore();
      win.show();
      win.focus();
    }
  });
}

let win = null, tray = null, backendProc = null;

function ping() {
  return new Promise(res => {
    http.get(`${URL_APP}/api/settings`, r => res(r.statusCode === 200))
      .on("error", () => res(false));
  });
}

async function waitBackend(ms = 60000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    if (await ping()) return true;
    await new Promise(r => setTimeout(r, 700));
  }
  return false;
}

async function startBackend() {
  if (await ping()) return true;
  if (!fs.existsSync(BACKEND)) return false;
  backendProc = spawn(BACKEND, [], { cwd: path.dirname(BACKEND) });
  return waitBackend();
}

function createWindow() {
  win = new BrowserWindow({
    width: 1280, height: 820, minWidth: 1180, minHeight: 740,
    backgroundColor: "#0b1220",
    icon: path.join(__dirname, "assets", "icon.ico"),
    autoHideMenuBar: true,
    webPreferences: { contextIsolation: true },
    show: false,
  });
  win.once("ready-to-show", () => win.show());
  win.webContents.on("did-fail-load", async () => {        // 首次加载失败(后端慢) → 等待重载
    const ok = await waitBackend(30000);
    if (ok && win && !win.isDestroyed()) win.loadURL(URL_APP);
  });
  win.on("close", e => {
    if (app.isQuiting) return;
    e.preventDefault(); win.hide();
  });
  return win;
}

function createTray() {
  try { tray = new Tray(path.join(__dirname, "assets", "icon.ico")); } catch { return; }
  tray.setToolTip("星枢 · 天文AI助手");
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: "显示星枢", click: () => win && (win.show(), win.focus()) },
    { label: "打开浏览器版", click: () => shell.openExternal(URL_APP) },
    { type: "separator" },
    { label: "退出", click: () => { app.isQuiting = true; app.quit(); } },
  ]));
  tray.on("double-click", () => win && (win.show(), win.focus()));
}

app.whenReady().then(async () => {
  win = createWindow();
  try { await win.webContents.session.clearCache(); } catch(e) {}   // 清electron缓存, 防吃旧页面
  const ok = await startBackend();                    // 先等后端
  if (win && !win.isDestroyed()) {
    if (ok) win.loadURL(URL_APP + '?v=' + Date.now());
    else win.loadURL("data:text/html,<h3 style='font-family:sans-serif'>后端启动失败: 请检查 StarPivot 目录与杀毒白名单</h3>");
  }
  createTray();
  globalShortcut.register("Alt+Shift+S", () => {
    if (!win) return;
    win.isVisible() ? win.hide() : (win.show(), win.focus());
  });
});

app.on("before-quit", () => { backendProc && backendProc.kill(); });
app.on("will-quit", () => globalShortcut.unregisterAll());
