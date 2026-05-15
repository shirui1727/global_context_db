const path = require("node:path");
const fs = require("node:fs/promises");
const { spawn } = require("node:child_process");
const { TextDecoder } = require("node:util");
const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");

const isDev = !app.isPackaged && Boolean(process.env.VITE_DEV_SERVER_URL);
const DEFAULT_BACKEND_URL = process.env.GCD_BACKEND_URL || "http://127.0.0.1:8000";
const BACKEND_HOST = "127.0.0.1";
const BACKEND_PORT = "8000";
const SETTINGS_FILE = "desktop-settings.json";
const MAX_TEXT_FILE_BYTES = 5 * 1024 * 1024;
const IMPORTABLE_EXTENSIONS = new Set([".txt", ".md", ".markdown", ".json", ".csv", ".log"]);
const IGNORED_DIRECTORY_NAMES = new Set(["node_modules", ".git", "dist", "release", "__pycache__"]);
const projectRoot = path.resolve(__dirname, "..", "..");
const preloadPath = path.join(__dirname, "preload.cjs");
const utf8Decoder = new TextDecoder("utf-8", { fatal: true });

let mainWindow = null;
let backendProcess = null;
let backendReadyPromise = null;
let runtimeSettings = {
  backendUrl: DEFAULT_BACKEND_URL,
  backendMode: "local",
  apiKey: "",
  autoStartLocalBackend: true
};
let backendStatus = {
  url: DEFAULT_BACKEND_URL,
  running: false,
  ownedByApp: false,
  message: "正在连接服务..."
};

function settingsPath() {
  return path.join(app.getPath("userData"), SETTINGS_FILE);
}

function normalizeSettings(input = {}) {
  const backendUrl = String(input.backendUrl || DEFAULT_BACKEND_URL).trim() || DEFAULT_BACKEND_URL;
  return {
    backendUrl,
    backendMode: input.backendMode === "remote" ? "remote" : "local",
    apiKey: String(input.apiKey || "").trim(),
    autoStartLocalBackend: input.autoStartLocalBackend !== false
  };
}

async function loadSettings() {
  try {
    const raw = await fs.readFile(settingsPath(), "utf8");
    runtimeSettings = normalizeSettings(JSON.parse(raw));
  } catch (_error) {
    runtimeSettings = normalizeSettings(runtimeSettings);
  }
  updateBackendStatus({ url: runtimeSettings.backendUrl });
  return runtimeSettings;
}

async function saveSettings(next) {
  runtimeSettings = normalizeSettings({ ...runtimeSettings, ...next });
  await fs.mkdir(path.dirname(settingsPath()), { recursive: true });
  await fs.writeFile(settingsPath(), JSON.stringify(runtimeSettings, null, 2), "utf8");
  backendReadyPromise = null;
  updateBackendStatus({
    url: runtimeSettings.backendUrl,
    running: false,
    ownedByApp: false,
    message: "配置已保存，正在重新连接..."
  });
  return runtimeSettings;
}

function backendUrl(pathname = "") {
  return `${runtimeSettings.backendUrl}${pathname}`;
}

function backendHeaders(headers = {}) {
  if (!runtimeSettings.apiKey) {
    return headers;
  }
  return {
    ...headers,
    "x-api-key": runtimeSettings.apiKey,
    authorization: `Bearer ${runtimeSettings.apiKey}`
  };
}

function isLocalManageableBackend() {
  try {
    const target = new URL(runtimeSettings.backendUrl);
    return runtimeSettings.backendMode === "local" && runtimeSettings.autoStartLocalBackend && ["127.0.0.1", "localhost", "::1"].includes(target.hostname);
  } catch (_error) {
    return false;
  }
}

function toPosixPath(value) {
  return value.split(path.sep).join("/");
}

function formatFileSize(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function isWithinIgnoredDataPath(relativePath) {
  const normalized = toPosixPath(relativePath).toLowerCase();
  return normalized === "data/lancedb" || normalized.startsWith("data/lancedb/") || normalized.includes("/data/lancedb/");
}

function resolveFolderPath(folderPath) {
  const value = String(folderPath ?? "").trim();
  if (!value) throw new Error("请选择一个文件夹。");
  return path.resolve(value);
}

async function readUtf8Text(filePath) {
  const raw = await fs.readFile(filePath);
  return utf8Decoder.decode(raw);
}

async function collectFolderFiles(folderPath) {
  const files = [];
  let scanned = 0;
  let importable = 0;
  let skipped = 0;
  let totalBytes = 0;

  async function walk(currentDir) {
    let entries;
    try {
      entries = await fs.readdir(currentDir, { withFileTypes: true });
    } catch (error) {
      skipped += 1;
      files.push({
        path: currentDir,
        relativePath: toPosixPath(path.relative(folderPath, currentDir)) || ".",
        size: 0,
        ext: "",
        importable: false,
        reason: `无法读取目录：${error instanceof Error ? error.message : "未知错误"}`,
        status: "skipped"
      });
      return;
    }

    for (const entry of entries) {
      const absolutePath = path.join(currentDir, entry.name);
      const relativePath = toPosixPath(path.relative(folderPath, absolutePath));
      const lowerName = entry.name.toLowerCase();

      if (entry.isDirectory()) {
        if (IGNORED_DIRECTORY_NAMES.has(lowerName) || isWithinIgnoredDataPath(relativePath)) continue;
        await walk(absolutePath);
        continue;
      }
      if (!entry.isFile()) continue;

      scanned += 1;
      const ext = path.extname(entry.name).toLowerCase();
      if (!IMPORTABLE_EXTENSIONS.has(ext)) {
        skipped += 1;
        files.push({ path: absolutePath, relativePath, size: 0, ext, importable: false, reason: "不支持的文件类型", status: "skipped" });
        continue;
      }

      let stat;
      try {
        stat = await fs.stat(absolutePath);
      } catch (error) {
        skipped += 1;
        files.push({
          path: absolutePath,
          relativePath,
          size: 0,
          ext,
          importable: false,
          reason: `无法读取文件信息：${error instanceof Error ? error.message : "未知错误"}`,
          status: "skipped"
        });
        continue;
      }

      if (stat.size > MAX_TEXT_FILE_BYTES) {
        skipped += 1;
        files.push({
          path: absolutePath,
          relativePath,
          size: stat.size,
          ext,
          importable: false,
          reason: `文件过大（${formatFileSize(stat.size)}），上限 5 MB`,
          status: "skipped"
        });
        continue;
      }

      importable += 1;
      totalBytes += stat.size;
      files.push({ path: absolutePath, relativePath, size: stat.size, ext, importable: true, status: "ready" });
    }
  }

  await walk(folderPath);
  return { folderPath, scanned, importable, skipped, totalBytes, files };
}

function normalizeIngestResult(file, result) {
  return { ...file, status: "imported", document_id: result.document_id, chunks: result.chunks };
}

function normalizeFailedResult(file, message) {
  return { ...file, status: "failed", reason: message };
}

function updateBackendStatus(patch) {
  backendStatus = {
    ...backendStatus,
    ...patch,
    url: runtimeSettings.backendUrl
  };
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("gcd:backend-status", backendStatus);
  }
}

async function checkBackend() {
  try {
    const response = await fetch(backendUrl("/health"), { headers: backendHeaders() });
    return response.ok;
  } catch (_error) {
    return false;
  }
}

function startBackend() {
  if (backendProcess || !isLocalManageableBackend()) return;
  const python = process.env.PYTHON || "python";
  updateBackendStatus({ running: false, ownedByApp: true, message: "正在启动本地服务..." });
  backendProcess = spawn(python, ["-m", "uvicorn", "app.main:app", "--host", BACKEND_HOST, "--port", BACKEND_PORT], {
    cwd: projectRoot,
    env: process.env,
    stdio: isDev ? "inherit" : "ignore",
    windowsHide: true,
    shell: process.platform === "win32"
  });
  backendProcess.on("exit", (code) => {
    backendProcess = null;
    updateBackendStatus({
      running: false,
      ownedByApp: false,
      message: `本地服务已退出${typeof code === "number" ? `，代码 ${code}` : ""}。`
    });
  });
}

async function ensureBackend() {
  if (backendReadyPromise) return backendReadyPromise;
  backendReadyPromise = ensureBackendInner().finally(() => {
    backendReadyPromise = null;
  });
  return backendReadyPromise;
}

async function ensureBackendInner() {
  if (await checkBackend()) {
    updateBackendStatus({ running: true, ownedByApp: false, message: "已连接到服务。" });
    return backendStatus;
  }

  if (!isLocalManageableBackend()) {
    updateBackendStatus({ running: false, ownedByApp: false, message: "远程服务未连接，请检查 NAS 地址。" });
    return backendStatus;
  }

  startBackend();
  for (let attempt = 0; attempt < 60; attempt += 1) {
    if (await checkBackend()) {
      updateBackendStatus({ running: true, ownedByApp: true, message: "本地服务已启动。" });
      return backendStatus;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }

  updateBackendStatus({ running: false, ownedByApp: false, message: "本地服务启动超时。" });
  return backendStatus;
}

async function requestBackend(pathname, options = {}) {
  if (pathname !== "/health") await ensureBackend();
  const response = await fetch(backendUrl(pathname), {
    ...options,
    headers: backendHeaders(options.headers || {})
  });
  const text = await response.text();
  let body = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch (_error) {
    body = text;
  }
  if (!response.ok) {
    const detail = body && typeof body === "object" && "detail" in body ? body.detail : text;
    throw new Error(typeof detail === "string" ? detail : `请求失败：${response.status}`);
  }
  return body;
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1360,
    height: 900,
    minWidth: 1080,
    minHeight: 720,
    backgroundColor: "#f5f7fb",
    title: "Global Context DB",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: preloadPath
    }
  });
  if (isDev) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL || "http://127.0.0.1:5173");
  } else {
    mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

function registerIpcHandlers() {
  ipcMain.handle("gcd:get-settings", async () => runtimeSettings);
  ipcMain.handle("gcd:save-settings", async (_event, payload) => {
    const saved = await saveSettings(payload || {});
    void ensureBackend();
    return saved;
  });
  ipcMain.handle("gcd:get-backend-status", async () => {
    const running = await checkBackend();
    updateBackendStatus({ running, message: running ? "服务运行中。" : "服务未连接。" });
    return backendStatus;
  });
  ipcMain.handle("gcd:open-backend-dashboard", async () => {
    await shell.openExternal(backendUrl("/"));
    return true;
  });
  ipcMain.handle("gcd:open-external-url", async (_event, payload) => {
    const url = String(payload?.url ?? "").trim();
    if (!url) throw new Error("URL 为空。");
    await shell.openExternal(url);
    return true;
  });
  ipcMain.handle("gcd:choose-document-file", async () => {
    const result = await dialog.showOpenDialog(mainWindow ?? undefined, {
      title: "选择要导入的文件",
      properties: ["openFile"],
      filters: [
        { name: "Text Documents", extensions: ["txt", "md", "markdown", "json", "csv", "log"] },
        { name: "All Files", extensions: ["*"] }
      ]
    });
    return result.canceled ? null : result.filePaths[0] ?? null;
  });
  ipcMain.handle("gcd:choose-document-folder", async () => {
    const result = await dialog.showOpenDialog(mainWindow ?? undefined, {
      title: "选择要导入的文件夹",
      properties: ["openDirectory"]
    });
    return result.canceled ? null : result.filePaths[0] ?? null;
  });
  ipcMain.handle("gcd:scan-folder", async (_event, payload) => collectFolderFiles(resolveFolderPath(payload?.folderPath)));
  ipcMain.handle("gcd:ingest-folder", async (_event, payload) => {
    const folderPath = resolveFolderPath(payload?.folderPath);
    const scan = await collectFolderFiles(folderPath);
    const files = [];
    for (const file of scan.files) {
      if (!file.importable) {
        files.push({ ...file, status: "skipped" });
        continue;
      }
      try {
        const text = await readUtf8Text(file.path);
        const result = await requestBackend("/documents/ingest", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source: file.relativePath, text })
        });
        files.push(normalizeIngestResult(file, result));
      } catch (error) {
        files.push(normalizeFailedResult(file, error instanceof Error ? error.message : "导入失败"));
      }
    }
    const imported = files.filter((file) => file.status === "imported").length;
    const failed = files.filter((file) => file.status === "failed").length;
    const skipped = files.filter((file) => file.status === "skipped").length;
    const totalChunks = files.reduce((sum, file) => sum + (typeof file.chunks === "number" ? file.chunks : 0), 0);
    return { folderPath, scanned: scan.scanned, imported, failed, skipped, totalBytes: scan.totalBytes, totalChunks, files };
  });

  ipcMain.handle("gcd:health", () => requestBackend("/health"));
  ipcMain.handle("gcd:list-documents", () => requestBackend("/documents"));
  ipcMain.handle("gcd:list-captures", () => requestBackend("/captures"));
  ipcMain.handle("gcd:list-memories", () => requestBackend("/memories"));
  ipcMain.handle("gcd:list-memory-versions", (_event, payload) => {
    const memoryId = String(payload?.memoryId ?? "").trim();
    return requestBackend(`/memories/${encodeURIComponent(memoryId)}/versions?limit=${Number(payload?.limit ?? 20)}`);
  });
  ipcMain.handle("gcd:list-audit-logs", (_event, payload) => requestBackend(`/audit-logs?limit=${Number(payload?.limit ?? 100)}`));
  ipcMain.handle("gcd:search", (_event, payload) =>
    requestBackend("/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: String(payload?.query ?? ""), top_k: Number(payload?.topK ?? 5) })
    })
  );
  ipcMain.handle("gcd:search-memories", (_event, payload) => {
    const params = new URLSearchParams({ q: String(payload?.query ?? ""), top_k: String(Number(payload?.topK ?? 5)) });
    return requestBackend(`/memories/search?${params.toString()}`);
  });
  ipcMain.handle("gcd:add-memory", (_event, payload) =>
    requestBackend("/memories", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: String(payload?.content ?? ""), tags: Array.isArray(payload?.tags) ? payload.tags.map(String) : [] })
    })
  );
  ipcMain.handle("gcd:update-memory", (_event, payload) =>
    requestBackend(`/memories/${encodeURIComponent(String(payload?.memoryId ?? ""))}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: String(payload?.content ?? ""), tags: Array.isArray(payload?.tags) ? payload.tags.map(String) : [] })
    })
  );
  ipcMain.handle("gcd:delete-memory", (_event, payload) =>
    requestBackend(`/memories/${encodeURIComponent(String(payload?.memoryId ?? ""))}`, { method: "DELETE" })
  );
  ipcMain.handle("gcd:ingest-text", (_event, payload) =>
    requestBackend("/documents/ingest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: String(payload?.source ?? "manual"), text: String(payload?.text ?? "") })
    })
  );
  ipcMain.handle("gcd:ingest-url", (_event, payload) =>
    requestBackend("/documents/ingest-url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: String(payload?.url ?? ""),
        tags: Array.isArray(payload?.tags) ? payload.tags.map(String) : [],
        source_platform: payload?.sourcePlatform ? String(payload.sourcePlatform) : null
      })
    })
  );
  ipcMain.handle("gcd:add-feed", (_event, payload) =>
    requestBackend("/feeds", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: String(payload?.url ?? ""), title: payload?.title ? String(payload.title) : null })
    })
  );
  ipcMain.handle("gcd:list-feeds", () => requestBackend("/feeds"));
  ipcMain.handle("gcd:refresh-feed", (_event, payload) => requestBackend(`/feeds/${encodeURIComponent(String(payload?.id ?? ""))}/refresh`, { method: "POST" }));
  ipcMain.handle("gcd:create-crawl-job", (_event, payload) =>
    requestBackend("/crawl/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls: Array.isArray(payload?.urls) ? payload.urls.map(String) : [] })
    })
  );
  ipcMain.handle("gcd:get-crawl-job", (_event, payload) => requestBackend(`/crawl/jobs/${encodeURIComponent(String(payload?.id ?? ""))}`));
  ipcMain.handle("gcd:ingest-file", async (_event, payload) => {
    const filePath = String(payload?.filePath ?? "").trim();
    if (!filePath) throw new Error("请选择一个文件。");
    const text = await fs.readFile(filePath, "utf8");
    return requestBackend("/documents/ingest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: filePath, text })
    });
  });
}

app.whenReady().then(async () => {
  await loadSettings();
  registerIpcHandlers();
  createWindow();
  await ensureBackend();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  if (backendProcess) backendProcess.kill();
});
