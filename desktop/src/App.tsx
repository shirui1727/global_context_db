import { useEffect, useMemo, useState } from "react";
import { getDesktopAPI } from "./desktopApi";
import type {
  AuditLog,
  BackendStatus,
  CaptureSummary,
  CrawlJob,
  DocumentSummary,
  FeedSummary,
  FolderImportResult,
  FolderScanFile,
  FolderScanResult,
  MemorySummary,
  MemoryVersion,
  SearchResult,
  DesktopSettings,
  HealthInfo
} from "./types";

type ViewKey = "overview" | "capture" | "documents" | "memory" | "governance" | "settings";
type ToastTone = "info" | "success" | "error";
type Toast = { tone: ToastTone; message: string } | null;
type SelectedItem = SearchResult | DocumentSummary | MemorySummary | FolderScanFile | CaptureSummary | null;
type MemoryEditorState = { id: string; content: string; tags: string; source: MemorySummary | null };

const initialStatus: BackendStatus = {
  url: "http://127.0.0.1:8000",
  running: false,
  ownedByApp: false,
  message: "正在连接本地服务..."
};

const initialSettings: DesktopSettings = {
  backendUrl: "http://127.0.0.1:8000",
  backendMode: "local",
  apiKey: "",
  autoStartLocalBackend: true
};

function splitTags(value: string) {
  return value
    .split(/[,\s，、]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatBytes(value: number) {
  if (!Number.isFinite(value) || value <= 0) return "0 B";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value?: string | null) {
  if (!value) return "未记录";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function shortPath(value: string, max = 64) {
  if (value.length <= max) return value;
  return `${value.slice(0, 26)}...${value.slice(-30)}`;
}

function scoreLabel(score?: number) {
  return typeof score === "number" ? `${Math.round(score * 100)}%` : "未评分";
}

function deriveMcpUrl(backendUrl: string) {
  try {
    const url = new URL(backendUrl);
    url.port = "8001";
    url.pathname = "/mcp";
    url.search = "";
    url.hash = "";
    return url.toString().replace(/\/$/, "");
  } catch (_error) {
    return backendUrl.replace(/:8000\/?$/, ":8001/mcp");
  }
}

export default function App() {
  const api = useMemo(() => getDesktopAPI(), []);
  const [view, setView] = useState<ViewKey>("overview");
  const [status, setStatus] = useState(initialStatus);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [captures, setCaptures] = useState<CaptureSummary[]>([]);
  const [feeds, setFeeds] = useState<FeedSummary[]>([]);
  const [memories, setMemories] = useState<MemorySummary[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [versions, setVersions] = useState<MemoryVersion[]>([]);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [selected, setSelected] = useState<SelectedItem>(null);
  const [memoryEditor, setMemoryEditor] = useState<MemoryEditorState | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [urlInput, setUrlInput] = useState("");
  const [feedUrl, setFeedUrl] = useState("");
  const [batchUrls, setBatchUrls] = useState("");
  const [crawlJob, setCrawlJob] = useState<CrawlJob | null>(null);
  const [manualSource, setManualSource] = useState("manual-note");
  const [manualText, setManualText] = useState("");
  const [memoryText, setMemoryText] = useState("");
  const [memoryTags, setMemoryTags] = useState("");
  const [folderPath, setFolderPath] = useState("");
  const [folderScan, setFolderScan] = useState<FolderScanResult | null>(null);
  const [folderImport, setFolderImport] = useState<FolderImportResult | null>(null);
  const [settings, setSettings] = useState<DesktopSettings>(initialSettings);
  const [healthInfo, setHealthInfo] = useState<HealthInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<Toast>(null);

  const showToast = (message: string, tone: ToastTone = "info") => {
    setToast({ message, tone });
    window.setTimeout(() => setToast(null), 2800);
  };

  const refreshAll = async () => {
    const [savedSettings, backendStatus, docs, caps, feedRows, mems, logs] = await Promise.all([
      api.getSettings(),
      api.getBackendStatus(),
      api.listDocuments(),
      api.listCaptures(),
      api.listFeeds(),
      api.listMemories(),
      api.listAuditLogs({ limit: 50 })
    ]);
    setSettings(savedSettings);
    setStatus(backendStatus);
    setDocuments(docs);
    setCaptures(caps);
    setFeeds(feedRows);
    setMemories(mems);
    setAuditLogs(logs);
    setSelected((current) => current ?? caps[0] ?? docs[0] ?? mems[0] ?? null);
  };

  const saveDesktopSettings = async () => {
    const backendUrl = settings.backendUrl.trim();
    if (!backendUrl) return showToast("后端地址不能为空", "error");
    setLoading(true);
    try {
      const saved = await api.saveSettings({ ...settings, backendUrl });
      setSettings(saved);
      const backendStatus = await api.getBackendStatus();
      setStatus(backendStatus);
      await refreshAll();
      setView("settings");
      showToast("连接配置已保存", "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "保存配置失败", "error");
    } finally {
      setLoading(false);
    }
  };

  const testDesktopConnection = async () => {
    setLoading(true);
    try {
      const result = await api.testConnection();
      setHealthInfo(result.health ?? null);
      const backendStatus = await api.getBackendStatus();
      setStatus(backendStatus);
      showToast(result.message, result.ok ? "success" : "error");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "连接测试失败", "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const unsubscribe = api.onBackendStatus((next) => setStatus(next));
    void refreshAll().catch((error) => showToast(error instanceof Error ? error.message : "加载失败", "error"));
    return unsubscribe;
  }, [api]);

  useEffect(() => {
    if (!memoryEditor) return;
    const current = memories.find((item) => item.id === memoryEditor.id);
    if (current) {
      setMemoryEditor({
        id: current.id,
        content: current.content,
        tags: current.tags.join(", "),
        source: current
      });
    }
  }, [memories, memoryEditor?.id]);

  const setMemoryAsEditor = async (memoryId: string) => {
    const current = memories.find((item) => item.id === memoryId);
    if (!current) return;
    setMemoryEditor({
      id: current.id,
      content: current.content,
      tags: current.tags.join(", "),
      source: current
    });
    const [versionRows] = await Promise.all([api.listMemoryVersions({ memoryId, limit: 20 })]);
    setVersions(versionRows);
    setDeleteConfirmId(null);
    setSelected(current);
    setView("memory");
  };

  const runSearch = async () => {
    const value = query.trim();
    if (!value) return showToast("先输入搜索词", "error");
    setLoading(true);
    try {
      const response = await api.search({ query: value, topK: 8 });
      setSearchResults(response.results);
      setSelected(response.results[0] ?? null);
      setView("overview");
      showToast(`找到 ${response.results.length} 条结果`, "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "搜索失败", "error");
    } finally {
      setLoading(false);
    }
  };

  const ingestUrl = async () => {
    const url = urlInput.trim();
    if (!url) return showToast("先输入公开 URL", "error");
    setLoading(true);
    try {
      const result = await api.ingestUrl({ url });
      setUrlInput("");
      await refreshAll();
      setSelected(captures[0] ?? null);
      setView("capture");
      showToast(`URL 已导入：${result.chunks} 个片段`, "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "URL 导入失败", "error");
    } finally {
      setLoading(false);
    }
  };

  const addFeed = async () => {
    const url = feedUrl.trim();
    if (!url) return showToast("先输入 RSS 地址", "error");
    setLoading(true);
    try {
      await api.addFeed({ url });
      setFeedUrl("");
      setFeeds(await api.listFeeds());
      showToast("RSS 源已保存", "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "保存失败", "error");
    } finally {
      setLoading(false);
    }
  };

  const refreshFeed = async (id: string) => {
    setLoading(true);
    try {
      const result = await api.refreshFeed({ id });
      await refreshAll();
      showToast(`RSS 刷新完成：新增 ${result.imported}，失败 ${result.failed}`, result.failed > 0 ? "info" : "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "刷新失败", "error");
    } finally {
      setLoading(false);
    }
  };

  const ingestManualText = async () => {
    const text = manualText.trim();
    if (!text) return showToast("先输入文本", "error");
    setLoading(true);
    try {
      const response = await api.ingestText({ source: manualSource.trim() || "manual", text });
      setManualText("");
      await refreshAll();
      setView("documents");
      showToast(`文本已入库：${response.chunks} 个片段`, "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "写入失败", "error");
    } finally {
      setLoading(false);
    }
  };

  const addMemory = async () => {
    const content = memoryText.trim();
    if (!content) return showToast("先写一条记忆", "error");
    setLoading(true);
    try {
      const result = await api.addMemory({ content, tags: splitTags(memoryTags) });
      setMemoryText("");
      setMemoryTags("");
      await refreshAll();
      if (result.memory) {
        await setMemoryAsEditor(result.memory.id);
      }
      showToast(result.status === "deduplicated" ? "发现重复，已复用旧记忆" : "记忆已写入", "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "记忆写入失败", "error");
    } finally {
      setLoading(false);
    }
  };

  const updateMemory = async () => {
    if (!memoryEditor) return;
    const content = memoryEditor.content.trim();
    if (!content) return showToast("记忆内容不能为空", "error");
    setLoading(true);
    try {
      await api.updateMemory({
        memoryId: memoryEditor.id,
        content,
        tags: splitTags(memoryEditor.tags)
      });
      await refreshAll();
      await setMemoryAsEditor(memoryEditor.id);
      showToast("记忆已更新", "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "更新失败", "error");
    } finally {
      setLoading(false);
    }
  };

  const deleteMemory = async () => {
    if (!memoryEditor) return;
    if (deleteConfirmId !== memoryEditor.id) {
      setDeleteConfirmId(memoryEditor.id);
      showToast("再次点击删除才会真正删除这条记忆", "info");
      return;
    }
    setLoading(true);
    try {
      await api.deleteMemory({ memoryId: memoryEditor.id });
      setMemoryEditor(null);
      setDeleteConfirmId(null);
      setVersions([]);
      await refreshAll();
      showToast("记忆已删除", "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "删除失败", "error");
    } finally {
      setLoading(false);
    }
  };

  const createCrawlJob = async () => {
    const urls = batchUrls
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    if (urls.length === 0) return showToast("先粘贴多行 URL", "error");
    setLoading(true);
    try {
      const result = await api.createCrawlJob({ urls });
      setCrawlJob(result);
      await refreshAll();
      showToast(`批量导入完成：成功 ${result.succeeded}，失败 ${result.failed}`, result.failed > 0 ? "info" : "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "批量导入失败", "error");
    } finally {
      setLoading(false);
    }
  };

  const chooseFolder = async () => {
    setLoading(true);
    try {
      const picked = await api.chooseDocumentFolder();
      if (!picked) return;
      setFolderPath(picked);
      const scan = await api.scanFolder({ folderPath: picked });
      setFolderScan(scan);
      setFolderImport(null);
      setView("documents");
      setSelected(scan.files[0] ?? null);
      showToast(`扫描完成：${scan.importable} 个可导入文件`, "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "扫描失败", "error");
    } finally {
      setLoading(false);
    }
  };

  const scanFolder = async () => {
    if (!folderPath.trim()) return showToast("先选择文件夹", "error");
    setLoading(true);
    try {
      const scan = await api.scanFolder({ folderPath: folderPath.trim() });
      setFolderScan(scan);
      setFolderImport(null);
      setSelected(scan.files[0] ?? null);
      showToast(`扫描完成：${scan.importable} 个可导入文件`, "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "扫描失败", "error");
    } finally {
      setLoading(false);
    }
  };

  const importFolder = async () => {
    if (!folderPath.trim()) return showToast("先选择文件夹", "error");
    setLoading(true);
    try {
      const result = await api.ingestFolder({ folderPath: folderPath.trim() });
      setFolderImport(result);
      await refreshAll();
      showToast(`导入完成：成功 ${result.imported}，失败 ${result.failed}`, result.failed > 0 ? "info" : "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "文件夹导入失败", "error");
    } finally {
      setLoading(false);
    }
  };

  const stats = {
    documents: documents.length,
    captures: captures.length,
    memories: memories.length,
    feeds: feeds.length,
    audits: auditLogs.length,
    results: searchResults.length
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">G</span>
          <div>
            <strong>Global Context DB</strong>
            <span>NAS 公共记忆库桌面壳</span>
          </div>
        </div>

        <nav className="nav-list" aria-label="主导航">
          <NavButton active={view === "overview"} onClick={() => setView("overview")} label="概览" />
          <NavButton active={view === "capture"} onClick={() => setView("capture")} label="采集" />
          <NavButton active={view === "documents"} onClick={() => setView("documents")} label="文档" />
          <NavButton active={view === "memory"} onClick={() => setView("memory")} label="记忆" />
          <NavButton active={view === "governance"} onClick={() => setView("governance")} label="治理" />
          <NavButton active={view === "settings"} onClick={() => setView("settings")} label="设置" />
        </nav>

        <div className="sidebar-stats">
          <StatBox label="采集" value={stats.captures} />
          <StatBox label="文档" value={stats.documents} />
          <StatBox label="记忆" value={stats.memories} />
        </div>

        <button className="ghost-button wide" type="button" onClick={() => void api.openBackendDashboard()}>
          打开后端首页
        </button>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div className="topbar-status">
            <span className={`status-dot ${status.running ? "online" : ""}`} />
            <span>{status.message}</span>
            <small>{status.url}</small>
          </div>
          <button className="ghost-button" type="button" disabled={loading} onClick={() => void refreshAll()}>
            刷新
          </button>
        </header>

        <section className="command-strip">
          <div className="search-box">
            <span>⌕</span>
            <input
              value={query}
              placeholder="搜索文档、记忆、采集内容"
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void runSearch();
              }}
            />
          </div>
          <button className="primary-button" type="button" disabled={loading} onClick={() => void runSearch()}>
            搜索
          </button>
          <button className="secondary-button" type="button" disabled={loading} onClick={() => void chooseFolder()}>
            选择文件夹
          </button>
        </section>

        <div className="content-grid">
          <section className="main-panel">{renderView()}</section>
          <DetailPanel
            item={selected}
            memoryEditor={memoryEditor}
            onMemoryContentChange={(value) => setMemoryEditor((current) => (current ? { ...current, content: value } : current))}
            onMemoryTagsChange={(value) => setMemoryEditor((current) => (current ? { ...current, tags: value } : current))}
            onUpdateMemory={() => void updateMemory()}
            onDeleteMemory={() => void deleteMemory()}
            deleteConfirmActive={deleteConfirmId === memoryEditor?.id}
            onOpenSelectedUrl={() => {
              if (selected && "url" in selected) {
                void api.openExternalUrl({ url: selected.url });
              }
            }}
            versions={versions}
          />
        </div>
      </main>

      {toast ? <div className={`toast ${toast.tone}`}>{toast.message}</div> : null}
    </div>
  );

  function renderView() {
    if (view === "capture") {
      return (
        <>
          <PanelHeader eyebrow="Capture" title="资料采集" meta={`${captures.length} 条采集 / ${feeds.length} 个 RSS`} />
          <div className="input-block capture-tools">
            <InfoCard
              title="浏览器剪藏"
              description="插件直接把当前页面、选中文本、截图保存到本地服务。"
              extra="http://127.0.0.1:8000/captures/web"
            />
            <ToolCard
              title="公开 URL 导入"
              description="适合博客、文档页、新闻页。"
              actionLabel="导入 URL"
              onAction={() => void ingestUrl()}
            >
              <input value={urlInput} placeholder="https://..." onChange={(event) => setUrlInput(event.target.value)} />
            </ToolCard>
            <ToolCard
              title="RSS 订阅"
              description="先手动刷新，不做后台定时。"
              actionLabel="保存 RSS"
              onAction={() => void addFeed()}
            >
              <input value={feedUrl} placeholder="RSS / Atom 地址" onChange={(event) => setFeedUrl(event.target.value)} />
              <div className="feed-list">
                {feeds.length === 0 ? <div className="muted-line">还没有 RSS 源。</div> : null}
                {feeds.map((feed) => (
                  <div className="feed-row" key={feed.id}>
                    <div>
                      <strong>{feed.title}</strong>
                      <span>{shortPath(feed.url)}</span>
                    </div>
                    <small>{feed.last_refreshed_at ? formatDate(feed.last_refreshed_at) : "未刷新"}</small>
                    <button className="ghost-button" type="button" disabled={loading} onClick={() => void refreshFeed(feed.id)}>
                      刷新
                    </button>
                  </div>
                ))}
              </div>
            </ToolCard>
            <ToolCard
              title="批量 URL 导入"
              description="一行一个 URL，按队列逐条抓取。"
              actionLabel="开始导入"
              onAction={() => void createCrawlJob()}
            >
              <textarea value={batchUrls} placeholder={"https://example.com/a\nhttps://example.com/b"} onChange={(event) => setBatchUrls(event.target.value)} />
              {crawlJob ? (
                <div className="crawl-summary">
                  <strong>{crawlJob.status}</strong>
                  <span>共 {crawlJob.total} 条，成功 {crawlJob.succeeded}，失败 {crawlJob.failed}</span>
                </div>
              ) : null}
            </ToolCard>
          </div>
          <div className="item-list">
            {captures.length === 0 ? <EmptyState text="采集记录会在这里显示。" /> : null}
            {captures.map((item) => (
              <button className="list-item" key={item.id} type="button" onClick={() => setSelected(item)}>
                <div>
                  <strong>{item.title || shortPath(item.url)}</strong>
                  <span>{item.error || item.text_preview || item.url}</span>
                </div>
                <small>{item.capture_method}</small>
              </button>
            ))}
            {crawlJob?.items.length ? <CrawlSummary job={crawlJob} /> : null}
          </div>
        </>
      );
    }

    if (view === "documents") {
      return (
        <>
          <PanelHeader eyebrow="Library" title="文档管理" meta={`${documents.length} 个文档`} />
          <div className="input-block">
            <div className="inline-fields">
              <input value={manualSource} placeholder="来源名称" onChange={(event) => setManualSource(event.target.value)} />
              <button className="secondary-button" type="button" disabled={loading} onClick={() => void ingestManualText()}>
                写入文本
              </button>
            </div>
            <textarea value={manualText} placeholder="直接粘贴一段文本入库" onChange={(event) => setManualText(event.target.value)} />
            <div className="inline-fields">
              <button className="ghost-button" type="button" disabled={loading} onClick={() => void scanFolder()}>
                重新扫描
              </button>
              <button className="primary-button" type="button" disabled={loading || !folderPath.trim()} onClick={() => void importFolder()}>
                导入文件夹
              </button>
            </div>
            <div className="folder-summary">
              <Metric label="扫描" value={folderScan?.scanned ?? 0} />
              <Metric label="可导入" value={folderScan?.importable ?? 0} />
              <Metric label="导入" value={folderImport?.imported ?? 0} />
              <Metric label="总大小" value={formatBytes(folderScan?.totalBytes ?? 0)} />
            </div>
          </div>
          <div className="item-list">
            {documents.length === 0 ? <EmptyState text="导入后会在这里看到文档摘要。" /> : null}
            {documents.map((item) => (
              <button className="list-item" key={item.id} type="button" onClick={() => setSelected(item)}>
                <div>
                  <strong>{shortPath(item.source)}</strong>
                  <span>{item.content_preview}</span>
                </div>
                <small>doc</small>
              </button>
            ))}
            {folderScan?.files?.length ? <ImportList title="扫描结果" items={folderScan.files} /> : null}
            {folderImport?.files?.length ? <ImportList title="导入结果" items={folderImport.files} /> : null}
          </div>
        </>
      );
    }

    if (view === "memory") {
      return (
        <>
          <PanelHeader eyebrow="Memory" title="记忆管理" meta={`${memories.length} 条记忆`} />
          <div className="input-block">
            <textarea
              value={memoryText}
              placeholder="写一条需要长期保留的记忆"
              onChange={(event) => setMemoryText(event.target.value)}
            />
            <div className="inline-fields">
              <input value={memoryTags} placeholder="标签，用逗号分隔" onChange={(event) => setMemoryTags(event.target.value)} />
              <button className="primary-button" type="button" disabled={loading} onClick={() => void addMemory()}>
                写入记忆
              </button>
            </div>
          </div>
          <div className="item-list">
            {memories.length === 0 ? <EmptyState text="记忆会在这里列出，支持编辑和删除。" /> : null}
            {memories.map((item) => (
              <button className="list-item" key={item.id} type="button" onClick={() => void setMemoryAsEditor(item.id)}>
                <div>
                  <strong>{item.tags.length ? item.tags.join(" / ") : "未标记"}</strong>
                  <span>{item.content}</span>
                </div>
                <small>{item.memory_type || "memory"}</small>
              </button>
            ))}
          </div>
        </>
      );
    }

    if (view === "governance") {
      return (
        <>
          <PanelHeader eyebrow="Governance" title="治理视图" meta={`${auditLogs.length} 条审计 / ${versions.length} 条版本`} />
          <div className="governance-grid">
            <PanelCard title="最近审计">
              {auditLogs.length === 0 ? <EmptyState text="暂时没有审计记录。" /> : null}
              {auditLogs.map((log) => (
                <div className="feed-row" key={log.id}>
                  <div>
                    <strong>{log.action}</strong>
                    <span>{log.actor || "system"} · {log.target_type || "target"} · {log.target_id || "-"}</span>
                  </div>
                  <small>{formatDate(log.created_at)}</small>
                </div>
              ))}
            </PanelCard>
            <PanelCard title="最近搜索">
              {searchResults.length === 0 ? <EmptyState text="先搜索一次，再看结果会显示在这里。" /> : null}
              {searchResults.map((item) => (
                <button className="list-item" key={item.id} type="button" onClick={() => setSelected(item)}>
                  <div>
                    <strong>{item.kind}</strong>
                    <span>{item.text}</span>
                  </div>
                  <small>{scoreLabel(item.score)}</small>
                </button>
              ))}
            </PanelCard>
          </div>
        </>
      );
    }

    if (view === "settings") {
      return (
        <>
          <PanelHeader eyebrow="Settings" title="连接设置" meta={settings.backendMode === "remote" ? "NAS / 远程服务" : "本机服务"} />
          <div className="input-block settings-form">
            <label className="field-label">
              <span>后端地址</span>
              <input
                value={settings.backendUrl}
                placeholder="http://192.168.10.5:8000"
                onChange={(event) => setSettings((current) => ({ ...current, backendUrl: event.target.value }))}
              />
            </label>
            <div className="settings-row">
              <label className="radio-tile">
                <input
                  type="radio"
                  checked={settings.backendMode === "local"}
                  onChange={() => setSettings((current) => ({ ...current, backendMode: "local" }))}
                />
                <span>本机服务</span>
              </label>
              <label className="radio-tile">
                <input
                  type="radio"
                  checked={settings.backendMode === "remote"}
                  onChange={() => setSettings((current) => ({ ...current, backendMode: "remote", autoStartLocalBackend: false }))}
                />
                <span>NAS / 远程服务</span>
              </label>
            </div>
            <label className="field-label">
              <span>API Key</span>
              <input
                value={settings.apiKey}
                placeholder="没有开启鉴权可以留空"
                type="password"
                onChange={(event) => setSettings((current) => ({ ...current, apiKey: event.target.value }))}
              />
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={settings.autoStartLocalBackend}
                disabled={settings.backendMode === "remote"}
                onChange={(event) => setSettings((current) => ({ ...current, autoStartLocalBackend: event.target.checked }))}
              />
              <span>本机模式下自动启动 FastAPI 服务</span>
            </label>
            <div className="inline-fields">
              <button
                className="ghost-button"
                type="button"
                onClick={() => setSettings((current) => ({ ...current, backendUrl: "http://192.168.10.5:8000", backendMode: "remote", autoStartLocalBackend: false }))}
              >
                填入 NAS 示例
              </button>
              <button className="primary-button" type="button" disabled={loading} onClick={() => void saveDesktopSettings()}>
                保存并重连
              </button>
            </div>
            <button className="secondary-button" type="button" disabled={loading} onClick={() => void testDesktopConnection()}>
              测试连接
            </button>
          </div>
          <div className="item-list">
            <InfoCard title="当前连接" description={status.message} extra={status.url} />
            <InfoCard title="MCP 地址" description="给 Codex、OpenClaw 等工具使用" extra={deriveMcpUrl(settings.backendUrl)} />
            {healthInfo ? (
              <div className="health-grid">
                <Metric label="服务" value={healthInfo.service || "unknown"} />
                <Metric label="数据目录" value={healthInfo.data_dir || "-"} />
                <Metric label="SQLite" value={healthInfo.sqlite_path || "-"} />
                <Metric label="MCP" value={healthInfo.mcp ? `${healthInfo.mcp.host}:${healthInfo.mcp.port}${healthInfo.mcp.path}` : "-"} />
              </div>
            ) : null}
          </div>
        </>
      );
    }

    return (
      <>
        <PanelHeader eyebrow="Overview" title="概览" meta={`${stats.results} 条搜索结果`} />
        <div className="overview-grid">
          <Kpi title="文档" value={stats.documents} hint="已入库正文" />
          <Kpi title="采集" value={stats.captures} hint="网页 / URL / RSS" />
          <Kpi title="记忆" value={stats.memories} hint="长期记忆" />
          <Kpi title="审计" value={stats.audits} hint="可追溯操作" />
        </div>
        <div className="overview-panels">
          <PanelCard title="最近文档">
            {documents.slice(0, 5).map((item) => (
              <button className="list-item" key={item.id} type="button" onClick={() => setSelected(item)}>
                <div>
                  <strong>{shortPath(item.source)}</strong>
                  <span>{item.content_preview}</span>
                </div>
                <small>doc</small>
              </button>
            ))}
          </PanelCard>
          <PanelCard title="最近记忆">
            {memories.slice(0, 5).map((item) => (
              <button className="list-item" key={item.id} type="button" onClick={() => void setMemoryAsEditor(item.id)}>
                <div>
                  <strong>{item.tags.length ? item.tags.join(" / ") : "未标记"}</strong>
                  <span>{item.content}</span>
                </div>
                <small>{item.memory_type || "memory"}</small>
              </button>
            ))}
          </PanelCard>
        </div>
      </>
    );
  }
}

function NavButton(props: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button className={props.active ? "active" : ""} type="button" onClick={props.onClick}>
      <span className="nav-icon">•</span>
      {props.label}
    </button>
  );
}

function StatBox(props: { label: string; value: number }) {
  return (
    <div>
      <small>{props.label}</small>
      <strong>{props.value}</strong>
    </div>
  );
}

function Metric(props: { label: string; value: number | string }) {
  return (
    <div>
      <small>{props.label}</small>
      <strong>{props.value}</strong>
    </div>
  );
}

function Kpi(props: { title: string; value: number; hint: string }) {
  return (
    <div className="kpi">
      <small>{props.title}</small>
      <strong>{props.value}</strong>
      <span>{props.hint}</span>
    </div>
  );
}

function PanelHeader(props: { eyebrow: string; title: string; meta: string }) {
  return (
    <div className="panel-header">
      <div>
        <span className="eyebrow">{props.eyebrow}</span>
        <h1>{props.title}</h1>
      </div>
      <small>{props.meta}</small>
    </div>
  );
}

function PanelCard(props: { title: string; children: React.ReactNode }) {
  return (
    <section className="panel-card">
      <div className="panel-card-head">
        <strong>{props.title}</strong>
      </div>
      <div className="panel-card-body">{props.children}</div>
    </section>
  );
}

function ToolCard(props: { title: string; description: string; actionLabel: string; onAction: () => void; children: React.ReactNode }) {
  return (
    <div className="tool-card">
      <div className="tool-card-head">
        <div>
          <strong>{props.title}</strong>
          <small>{props.description}</small>
        </div>
        <button className="secondary-button" type="button" onClick={props.onAction}>
          {props.actionLabel}
        </button>
      </div>
      {props.children}
    </div>
  );
}

function InfoCard(props: { title: string; description: string; extra: string }) {
  return (
    <div className="capture-status">
      <div>
        <strong>{props.title}</strong>
        <span>{props.description}</span>
      </div>
      <code>{props.extra}</code>
    </div>
  );
}

function EmptyState(props: { text: string }) {
  return <div className="empty-state">{props.text}</div>;
}

function ImportList(props: { title: string; items: FolderScanFile[] }) {
  return (
    <div className="import-summary">
      <div className="import-summary-head">
        <strong>{props.title}</strong>
        <small>{props.items.length} 项</small>
      </div>
      {props.items.map((item) => (
        <div className={`import-row ${item.status}`} key={`${item.relativePath}-${item.status}`}>
          <span>{shortPath(item.relativePath)}</span>
          <small>{item.status === "imported" ? `${item.chunks ?? 0} chunks` : item.reason || item.status}</small>
        </div>
      ))}
    </div>
  );
}

function CrawlSummary(props: { job: CrawlJob }) {
  return (
    <div className="import-summary">
      <div className="import-summary-head">
        <strong>批量导入结果</strong>
        <small>{props.job.items.length} 项</small>
      </div>
      {props.job.items.map((item) => (
        <div className={`import-row ${item.status === "imported" ? "imported" : "failed"}`} key={item.id}>
          <span>{shortPath(item.title || item.url)}</span>
          <small>{item.status === "imported" ? "已导入" : item.error || "失败"}</small>
        </div>
      ))}
    </div>
  );
}

function DetailPanel(props: {
  item: SelectedItem;
  memoryEditor: MemoryEditorState | null;
  onMemoryContentChange: (value: string) => void;
  onMemoryTagsChange: (value: string) => void;
  onUpdateMemory: () => void;
  onDeleteMemory: () => void;
  deleteConfirmActive: boolean;
  onOpenSelectedUrl: () => void;
  versions: MemoryVersion[];
}) {
  const item = props.item;
  let title = "等待选择";
  let subtitle = "选中左侧项目后查看详情";
  let body = "";
  let meta: Array<[string, string]> = [];

  if (item && "content_preview" in item) {
    title = shortPath(item.source);
    subtitle = "文档";
    body = item.content_preview;
    meta = [["ID", item.id], ["来源", item.source]];
  } else if (item && "content" in item) {
    title = item.tags.length ? item.tags.join(" / ") : "记忆";
    subtitle = "长期记忆";
    body = item.content;
    meta = [
      ["ID", item.id],
      ["标签", item.tags.join(", ") || "无"],
      ["类型", item.memory_type || "long_term"],
      ["更新时间", formatDate(item.updated_at ?? item.created_at)]
    ];
  } else if (item && "importable" in item) {
    title = shortPath(item.relativePath);
    subtitle = item.status;
    body = item.reason || `${formatBytes(item.size)} · ${item.ext || "unknown"}`;
    meta = [
      ["路径", item.path],
      ["大小", formatBytes(item.size)],
      ["状态", item.status],
      ["可导入", item.importable ? "是" : "否"]
    ];
    if (typeof item.chunks === "number") meta.push(["片段", String(item.chunks)]);
    if (item.document_id) meta.push(["文档 ID", item.document_id]);
  } else if (item && "capture_method" in item) {
    title = item.title || shortPath(item.url);
    subtitle = `采集 · ${item.capture_method}`;
    body = item.error || item.text_preview || "暂无预览";
    meta = [
      ["URL", item.url],
      ["平台", item.source_platform || "web"],
      ["状态", item.status],
      ["时间", formatDate(item.created_at)],
      ["标签", item.tags.join(", ") || "无"]
    ];
    if (item.document_id) meta.push(["文档 ID", item.document_id]);
    if (item.html_path) meta.push(["HTML", item.html_path]);
    if (item.screenshot_path) meta.push(["截图", item.screenshot_path]);
  } else if (item) {
    title = item.kind === "memory" ? "搜索到的记忆" : shortPath(item.source || item.doc_id || item.id);
    subtitle = item.kind;
    body = item.text;
    meta = [
      ["ID", item.id],
      ["来源", item.source || item.doc_id || "无"],
      ["评分", scoreLabel(item.score)]
    ];
  }

  return (
    <aside className="detail-panel">
      <div className="detail-head">
        <span className="eyebrow">Preview</span>
        <h2>{title}</h2>
        <small>{subtitle}</small>
      </div>
      <div className="detail-body">{body || "暂无内容"}</div>
      <div className="detail-actions">
        {item && "url" in item ? (
          <button className="secondary-button" type="button" onClick={props.onOpenSelectedUrl}>
            打开来源
          </button>
        ) : null}
      </div>
      {props.memoryEditor ? (
        <div className="memory-editor">
          <div className="inline-fields">
            <input value={props.memoryEditor.id} readOnly />
          </div>
          <textarea value={props.memoryEditor.content} onChange={(event) => props.onMemoryContentChange(event.target.value)} />
          <input value={props.memoryEditor.tags} placeholder="标签" onChange={(event) => props.onMemoryTagsChange(event.target.value)} />
          <div className="inline-fields">
            <button className="secondary-button" type="button" onClick={props.onUpdateMemory}>
              更新
            </button>
            <button className="ghost-button" type="button" onClick={props.onDeleteMemory}>
              {props.deleteConfirmActive ? "确认删除" : "删除"}
            </button>
          </div>
          <div className="version-list">
            <div className="import-summary-head">
              <strong>版本历史</strong>
              <small>{props.versions.length} 条</small>
            </div>
            {props.versions.map((version) => (
              <div className="import-row" key={version.id}>
                <span>{version.change_type}</span>
                <small>{formatDate(version.changed_at)}</small>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      <div className="meta-list">
        {meta.map(([key, value]) => (
          <div key={key}>
            <small>{key}</small>
            <span>{value}</span>
          </div>
        ))}
      </div>
    </aside>
  );
}
