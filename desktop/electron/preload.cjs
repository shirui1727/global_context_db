const { contextBridge, ipcRenderer } = require("electron");

const desktopAPI = {
  getBackendStatus: () => ipcRenderer.invoke("gcd:get-backend-status"),
  openBackendDashboard: () => ipcRenderer.invoke("gcd:open-backend-dashboard"),
  openExternalUrl: (payload) => ipcRenderer.invoke("gcd:open-external-url", payload),
  chooseDocumentFile: () => ipcRenderer.invoke("gcd:choose-document-file"),
  chooseDocumentFolder: () => ipcRenderer.invoke("gcd:choose-document-folder"),
  health: () => ipcRenderer.invoke("gcd:health"),
  listDocuments: () => ipcRenderer.invoke("gcd:list-documents"),
  listCaptures: () => ipcRenderer.invoke("gcd:list-captures"),
  listMemories: () => ipcRenderer.invoke("gcd:list-memories"),
  listMemoryVersions: (payload) => ipcRenderer.invoke("gcd:list-memory-versions", payload),
  listAuditLogs: (payload) => ipcRenderer.invoke("gcd:list-audit-logs", payload ?? {}),
  search: (payload) => ipcRenderer.invoke("gcd:search", payload),
  searchMemories: (payload) => ipcRenderer.invoke("gcd:search-memories", payload),
  addMemory: (payload) => ipcRenderer.invoke("gcd:add-memory", payload),
  updateMemory: (payload) => ipcRenderer.invoke("gcd:update-memory", payload),
  deleteMemory: (payload) => ipcRenderer.invoke("gcd:delete-memory", payload),
  ingestText: (payload) => ipcRenderer.invoke("gcd:ingest-text", payload),
  ingestUrl: (payload) => ipcRenderer.invoke("gcd:ingest-url", payload),
  addFeed: (payload) => ipcRenderer.invoke("gcd:add-feed", payload),
  listFeeds: () => ipcRenderer.invoke("gcd:list-feeds"),
  refreshFeed: (payload) => ipcRenderer.invoke("gcd:refresh-feed", payload),
  createCrawlJob: (payload) => ipcRenderer.invoke("gcd:create-crawl-job", payload),
  getCrawlJob: (payload) => ipcRenderer.invoke("gcd:get-crawl-job", payload),
  ingestFile: (payload) => ipcRenderer.invoke("gcd:ingest-file", payload),
  scanFolder: (payload) => ipcRenderer.invoke("gcd:scan-folder", payload),
  ingestFolder: (payload) => ipcRenderer.invoke("gcd:ingest-folder", payload),
  onBackendStatus: (callback) => {
    const listener = (_event, status) => callback(status);
    ipcRenderer.on("gcd:backend-status", listener);
    return () => ipcRenderer.removeListener("gcd:backend-status", listener);
  }
};

contextBridge.exposeInMainWorld("desktopAPI", desktopAPI);
