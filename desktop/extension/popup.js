const API_URL = "http://127.0.0.1:8000";
const statusEl = document.getElementById("status");
const messageEl = document.getElementById("message");
const buttons = Array.from(document.querySelectorAll("button"));

function setMessage(text, tone = "") {
  messageEl.textContent = text;
  messageEl.className = tone;
}

function setBusy(value) {
  for (const button of buttons) {
    button.disabled = value;
  }
}

function splitTags() {
  return document
    .getElementById("tags")
    .value.split(/[,\s，、]+/)
    .map((tag) => tag.trim())
    .filter(Boolean);
}

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.id) {
    throw new Error("没有找到当前标签页。");
  }
  if (!tab.url || !/^https?:\/\//i.test(tab.url)) {
    throw new Error("浏览器内部页不能采集，请打开普通网页。");
  }
  return tab;
}

async function extractPage(tabId, mode) {
  const injected = await chrome.scripting.executeScript({
    target: { tabId },
    files: ["content.js"]
  });
  if (!injected) {
    throw new Error("无法注入采集脚本。");
  }
  const [result] = await chrome.scripting.executeScript({
    target: { tabId },
    func: (captureMode) => {
      if (typeof gcdExtractPage === "function") {
        return gcdExtractPage(captureMode);
      }
      const selection = window.getSelection ? String(window.getSelection()).trim() : "";
      const readableText = Array.from(document.querySelectorAll("article, main"))
        .map((node) => node.innerText || "")
        .join("\n\n")
        .trim();
      const bodyText = document.body ? document.body.innerText || "" : "";
      const text = captureMode === "selection" ? selection : readableText || bodyText;

      return {
        url: location.href,
        title: document.title || location.href,
        text,
        html: document.documentElement ? document.documentElement.outerHTML : "",
        source_platform: location.hostname.replace(/^www\./, ""),
        captured_at: new Date().toISOString()
      };
    },
    args: [mode]
  });
  if (!result || !result.result) {
    throw new Error("没有读取到页面内容。");
  }
  return result.result;
}

async function captureScreenshot(tab) {
  return chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });
}

async function postCapture(payload) {
  const response = await fetch(`${API_URL}/captures/web`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body && body.detail ? body.detail : `保存失败：${response.status}`;
    throw new Error(detail);
  }
  return body;
}

async function save(mode) {
  setBusy(true);
  setMessage("正在读取页面...");
  try {
    const tab = await getActiveTab();
    const page = await extractPage(tab.id, mode === "selection" ? "selection" : "page");
    if (mode === "selection" && !page.text.trim()) {
      throw new Error("当前没有选中文本。");
    }
    if (mode === "screenshot") {
      page.screenshot = await captureScreenshot(tab);
    }
    const result = await postCapture({
      ...page,
      tags: splitTags(),
      capture_method: mode
    });
    setMessage(`已保存，生成 ${result.chunks || 0} 个片段。`, "success");
  } catch (error) {
    const message = error instanceof Error ? error.message : "保存失败。";
    if (message.includes("Failed to fetch")) {
      setMessage("连接失败，请先打开 Global Context DB 桌面应用。", "error");
    } else {
      setMessage(message, "error");
    }
  } finally {
    setBusy(false);
  }
}

async function checkHealth() {
  try {
    const response = await fetch(`${API_URL}/health`);
    statusEl.textContent = response.ok ? "本地服务已连接" : "本地服务不可用";
  } catch (_error) {
    statusEl.textContent = "请先打开桌面应用";
  }
}

document.getElementById("savePage").addEventListener("click", () => void save("page"));
document.getElementById("saveSelection").addEventListener("click", () => void save("selection"));
document.getElementById("saveScreenshot").addEventListener("click", () => void save("screenshot"));
void checkHealth();
