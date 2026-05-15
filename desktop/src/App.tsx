import { useEffect, useMemo, useState } from "react";
import { getDesktopAPI } from "./desktopApi";
import type {
  BackendStatus,
  CaptureSummary,
  CrawlJob,
  DocumentSummary,
  FeedSummary,
  FolderImportResult,
  FolderScanFile,
  FolderScanResult,
  MemorySummary,
  SearchResult
} from "./types";

type ActiveView = "capture" | "library" | "search" | "memory" | "folder";
type ToastTone = "info" | "success" | "error";
type Toast = { tone: ToastTone; message: string } | null;
type SelectedItem = SearchResult | DocumentSummary | MemorySummary | FolderScanFile | CaptureSummary | null;

const initialBackendStatus: BackendStatus = {
  url: "http://127.0.0.1:8000",
  running: false,
  ownedByApp: false,
  message: "正在连接本地服务。"
};

function splitTags(value: string) {
  return value
    .split(/[,\s，、]+/)
    .map((tag) => tag.trim())
    .filter(Boolean);
}

function scoreLabel(score?: number) {
  if (typeof score !== "number") {
    return "未评分";
  }
  return `${Math.round(score * 100)}%`;
}

function compactPath(value: string) {
  if (value.length <= 72) {
    return value;
  }
  return `${value.slice(0, 28)}...${value.slice(-36)}`;
}

function formatBytes(value: number) {
  if (!Number.isFinite(value) || value <= 0) {
    return "0 B";
  }
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function parseUrlLines(value: string) {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function formatDate(value?: string | null) {
  if (!value) {
    return "未记录";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function App() {
  const api = useMemo(() => getDesktopAPI(), []);
  const [activeView, setActiveView] = useState<ActiveView>("capture");
  const [backendStatus, setBackendStatus] = useState<BackendStatus>(initialBackendStatus);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [captures, setCaptures] = useState<CaptureSummary[]>([]);
  const [feeds, setFeeds] = useState<FeedSummary[]>([]);
  const [memories, setMemories] = useState<MemorySummary[]>([]);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [selected, setSelected] = useState<SelectedItem>(null);
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
  const [isLoading, setIsLoading] = useState(false);
  const [toast, setToast] = useState<Toast>(null);

  const showToast = (message: string, tone: ToastTone = "info") => {
    setToast({ message, tone });
    window.setTimeout(() => setToast(null), 3200);
  };

  const refreshAll = async () => {
    const [status, docs, caps, feedRows, mems] = await Promise.all([
      api.getBackendStatus(),
      api.listDocuments(),
      api.listCaptures(),
      api.listFeeds(),
      api.listMemories()
    ]);
    setBackendStatus(status);
    setDocuments(docs);
    setCaptures(caps);
    setFeeds(feedRows);
    setMemories(mems);
    setSelected((current) => current ?? caps[0] ?? docs[0] ?? mems[0] ?? null);
  };

  useEffect(() => {
    const unsubscribe = api.onBackendStatus((status) => setBackendStatus(status));
    void refreshAll().catch((error) => {
      showToast(error instanceof Error ? error.message : "加载本地数据失败。", "error");
    });
    return unsubscribe;
  }, [api]);

  const runSearch = async () => {
    const value = query.trim();
    if (!value) {
      showToast("先输入要搜索的内容。", "error");
      return;
    }

    setIsLoading(true);
    try {
      const response = await api.search({ query: value, topK: 8 });
      setSearchResults(response.results);
      setActiveView("search");
      setSelected(response.results[0] ?? null);
      showToast(`找到 ${response.results.length} 条结果。`, "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "搜索失败。", "error");
    } finally {
      setIsLoading(false);
    }
  };

  const ingestSelectedFile = async () => {
    setIsLoading(true);
    try {
      const filePath = await api.chooseDocumentFile();
      if (!filePath) {
        return;
      }
      const response = await api.ingestFile({ filePath });
      await refreshAll();
      setActiveView("library");
      showToast(`已导入 ${response.chunks} 个片段。`, "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "文件导入失败。", "error");
    } finally {
      setIsLoading(false);
    }
  };

  const chooseFolder = async () => {
    setIsLoading(true);
    try {
      const picked = await api.chooseDocumentFolder();
      if (!picked) {
        return;
      }
      setFolderPath(picked);
      const scan = await api.scanFolder({ folderPath: picked });
      setFolderScan(scan);
      setFolderImport(null);
      setActiveView("folder");
      setSelected(scan.files[0] ?? null);
      showToast(`扫描到 ${scan.importable} 个可导入文件。`, "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "扫描文件夹失败。", "error");
    } finally {
      setIsLoading(false);
    }
  };

  const scanFolder = async () => {
    const value = folderPath.trim();
    if (!value) {
      showToast("先选择一个文件夹。", "error");
      return;
    }

    setIsLoading(true);
    try {
      const scan = await api.scanFolder({ folderPath: value });
      setFolderScan(scan);
      setFolderImport(null);
      setActiveView("folder");
      setSelected(scan.files[0] ?? null);
      showToast(`扫描到 ${scan.importable} 个可导入文件。`, "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "扫描文件夹失败。", "error");
    } finally {
      setIsLoading(false);
    }
  };

  const importFolder = async () => {
    const value = folderPath.trim();
    if (!value) {
      showToast("先选择一个文件夹。", "error");
      return;
    }

    setIsLoading(true);
    try {
      const result = await api.ingestFolder({ folderPath: value });
      setFolderImport(result);
      const refreshed = await Promise.all([api.listDocuments(), api.listMemories(), api.getBackendStatus()]);
      setDocuments(refreshed[0]);
      setMemories(refreshed[1]);
      setBackendStatus(refreshed[2]);
      setActiveView("folder");
      setSelected(result.files.find((item) => item.status === "imported") ?? result.files[0] ?? null);
      showToast(`导入完成：${result.imported} 个文件。`, result.failed > 0 ? "info" : "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "文件夹导入失败。", "error");
    } finally {
      setIsLoading(false);
    }
  };

  const ingestManualText = async () => {
    const text = manualText.trim();
    if (!text) {
      showToast("先粘贴或输入一段内容。", "error");
      return;
    }

    setIsLoading(true);
    try {
      const response = await api.ingestText({ source: manualSource.trim() || "manual", text });
      setManualText("");
      await refreshAll();
      setActiveView("library");
      showToast(`已写入文档，生成 ${response.chunks} 个片段。`, "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "写入失败。", "error");
    } finally {
      setIsLoading(false);
    }
  };

  const addMemory = async () => {
    const content = memoryText.trim();
    if (!content) {
      showToast("先写一条要长期记住的信息。", "error");
      return;
    }

    setIsLoading(true);
    try {
      await api.addMemory({ content, tags: splitTags(memoryTags) });
      setMemoryText("");
      setMemoryTags("");
      await refreshAll();
      setActiveView("memory");
      showToast("记忆已写入。", "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "记忆写入失败。", "error");
    } finally {
      setIsLoading(false);
    }
  };

  const ingestUrl = async () => {
    const url = urlInput.trim();
    if (!url) {
      showToast("先粘贴一个公开 URL。", "error");
      return;
    }

    setIsLoading(true);
    try {
      const result = await api.ingestUrl({ url });
      setUrlInput("");
      await refreshAll();
      setActiveView("capture");
      showToast(`URL 已导入：${result.chunks} 个片段。`, "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "URL 导入失败。", "error");
    } finally {
      setIsLoading(false);
    }
  };

  const addFeed = async () => {
    const url = feedUrl.trim();
    if (!url) {
      showToast("先粘贴 RSS 地址。", "error");
      return;
    }

    setIsLoading(true);
    try {
      await api.addFeed({ url });
      setFeedUrl("");
      const feedRows = await api.listFeeds();
      setFeeds(feedRows);
      showToast("RSS 源已保存。", "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "RSS 保存失败。", "error");
    } finally {
      setIsLoading(false);
    }
  };

  const refreshFeed = async (id: string) => {
    setIsLoading(true);
    try {
      const result = await api.refreshFeed({ id });
      const [docs, caps, feedRows] = await Promise.all([api.listDocuments(), api.listCaptures(), api.listFeeds()]);
      setDocuments(docs);
      setCaptures(caps);
      setFeeds(feedRows);
      showToast(`RSS 刷新完成：新增 ${result.imported}，失败 ${result.failed}。`, result.failed > 0 ? "info" : "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "RSS 刷新失败。", "error");
    } finally {
      setIsLoading(false);
    }
  };

  const createCrawlJob = async () => {
    const urls = parseUrlLines(batchUrls);
    if (urls.length === 0) {
      showToast("先粘贴一批 URL，每行一个。", "error");
      return;
    }

    setIsLoading(true);
    try {
      const result = await api.createCrawlJob({ urls });
      setCrawlJob(result);
      const [docs, caps] = await Promise.all([api.listDocuments(), api.listCaptures()]);
      setDocuments(docs);
      setCaptures(caps);
      showToast(`批量导入完成：成功 ${result.succeeded}，失败 ${result.failed}。`, result.failed > 0 ? "info" : "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "批量导入失败。", "error");
    } finally {
      setIsLoading(false);
    }
  };

  const stats = {
    documents: documents.length,
    captures: captures.length,
    memories: memories.length,
    results: searchResults.length,
    folderFiles: folderScan?.files.length ?? 0
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">G</span>
          <div>
            <strong>Global Context DB</strong>
            <span>本地知识库桌面版</span>
          </div>
        </div>
        <nav className="nav-list" aria-label="主导航">
          <button className={activeView === "capture" ? "active" : ""} type="button" onClick={() => setActiveView("capture")}>
            <span className="nav-icon">◎</span>
            采集
          </button>
          <button className={activeView === "folder" ? "active" : ""} type="button" onClick={() => setActiveView("folder")}>
            <span className="nav-icon">□</span>
            文件夹
          </button>
          <button className={activeView === "library" ? "active" : ""} type="button" onClick={() => setActiveView("library")}>
            <span className="nav-icon">▦</span>
            文件库
          </button>
          <button className={activeView === "search" ? "active" : ""} type="button" onClick={() => setActiveView("search")}>
            <span className="nav-icon">⌕</span>
            搜索
          </button>
          <button className={activeView === "memory" ? "active" : ""} type="button" onClick={() => setActiveView("memory")}>
            <span className="nav-icon">◇</span>
            记忆
          </button>
        </nav>
        <div className="sidebar-stats">
          <div>
            <small>采集</small>
            <strong>{stats.captures}</strong>
          </div>
          <div>
            <small>文档</small>
            <strong>{stats.documents}</strong>
          </div>
          <div>
            <small>记忆</small>
            <strong>{stats.memories}</strong>
          </div>
        </div>
        <button className="ghost-button wide" type="button" onClick={() => void api.openBackendDashboard()}>
          打开后端诊断页
        </button>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div className="topbar-status">
            <span className={`status-dot ${backendStatus.running ? "online" : ""}`} />
            <span>{backendStatus.message}</span>
            <small>{backendStatus.url}</small>
          </div>
          <button className="ghost-button" type="button" disabled={isLoading} onClick={() => void refreshAll()}>
            刷新
          </button>
        </header>

        <section className="command-strip">
          <div className="search-box">
            <span>⌕</span>
            <input
              value={query}
              placeholder="搜索文件内容、决策、记忆"
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  void runSearch();
                }
              }}
            />
          </div>
          <button className="primary-button" type="button" disabled={isLoading} onClick={() => void runSearch()}>
            搜索
          </button>
          <button className="secondary-button" type="button" disabled={isLoading} onClick={() => void chooseFolder()}>
            选文件夹
          </button>
        </section>

        <div className="content-grid">
          <section className="main-panel">{renderActiveView()}</section>
          <DetailPanel item={selected} />
        </div>
      </main>

      {toast ? <div className={`toast ${toast.tone}`}>{toast.message}</div> : null}
    </div>
  );

  function renderActiveView() {
    if (activeView === "search") {
      return (
        <>
          <PanelHeader eyebrow="Search" title="搜索结果" meta={`${searchResults.length} 条`} />
          <div className="item-list">
            {searchResults.length === 0 ? <EmptyState text="输入关键词后会在这里显示匹配的文件片段和记忆。" /> : null}
            {searchResults.map((item) => (
              <button className="list-item" key={item.id} type="button" onClick={() => setSelected(item)}>
                <div>
                  <strong>{item.kind === "memory" ? "记忆" : compactPath(item.source || item.doc_id || item.id)}</strong>
                  <span>{item.text}</span>
                </div>
                <small>{scoreLabel(item.score)}</small>
              </button>
            ))}
          </div>
        </>
      );
    }

    if (activeView === "capture") {
      return (
        <>
          <PanelHeader eyebrow="Capture" title="资料采集" meta={`${captures.length} 条采集 / ${feeds.length} 个 RSS`} />
          <div className="input-block capture-tools">
            <div className="capture-status">
              <div>
                <strong>浏览器插件入口</strong>
                <span>{backendStatus.running ? "本地服务已就绪，插件可连接。" : "先打开桌面应用并等待本地服务启动。"}</span>
              </div>
              <code>http://127.0.0.1:8000/captures/web</code>
            </div>
            <div className="tool-card">
              <div className="tool-card-head">
                <strong>公开 URL 导入</strong>
                <small>适合博客、文档页、新闻页</small>
              </div>
              <div className="inline-fields">
                <input value={urlInput} placeholder="https://..." onChange={(event) => setUrlInput(event.target.value)} />
                <button className="primary-button" type="button" disabled={isLoading} onClick={() => void ingestUrl()}>
                  导入 URL
                </button>
              </div>
            </div>
            <div className="tool-card">
              <div className="tool-card-head">
                <strong>RSS 订阅</strong>
                <small>第一版手动刷新</small>
              </div>
              <div className="inline-fields">
                <input value={feedUrl} placeholder="RSS / Atom 地址" onChange={(event) => setFeedUrl(event.target.value)} />
                <button className="secondary-button" type="button" disabled={isLoading} onClick={() => void addFeed()}>
                  保存源
                </button>
              </div>
              <div className="feed-list">
                {feeds.length === 0 ? <span className="muted-line">还没有 RSS 源。</span> : null}
                {feeds.map((feed) => (
                  <div className="feed-row" key={feed.id}>
                    <div>
                      <strong>{feed.title}</strong>
                      <span>{compactPath(feed.url)}</span>
                    </div>
                    <small>{feed.last_refreshed_at ? formatDate(feed.last_refreshed_at) : "未刷新"}</small>
                    <button className="ghost-button" type="button" disabled={isLoading} onClick={() => void refreshFeed(feed.id)}>
                      刷新
                    </button>
                  </div>
                ))}
              </div>
            </div>
            <div className="tool-card">
              <div className="tool-card-head">
                <strong>批量 URL 导入</strong>
                <small>每行一个 URL，按队列逐条抓取</small>
              </div>
              <textarea value={batchUrls} placeholder={"https://example.com/a\nhttps://example.com/b"} onChange={(event) => setBatchUrls(event.target.value)} />
              <button className="primary-button" type="button" disabled={isLoading} onClick={() => void createCrawlJob()}>
                开始批量导入
              </button>
              {crawlJob ? (
                <div className="crawl-summary">
                  <strong>{crawlJob.status}</strong>
                  <span>
                    共 {crawlJob.total} 条，成功 {crawlJob.succeeded}，失败 {crawlJob.failed}
                  </span>
                </div>
              ) : null}
            </div>
          </div>
          <div className="item-list">
            {captures.length === 0 ? <EmptyState text="浏览器插件保存、公开 URL 导入、RSS 刷新后的资料会出现在这里。" /> : null}
            {captures.map((item) => (
              <button className="list-item" key={item.id} type="button" onClick={() => setSelected(item)}>
                <div>
                  <strong>{item.title || compactPath(item.url)}</strong>
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

    if (activeView === "memory") {
      return (
        <>
          <PanelHeader eyebrow="Memory" title="长期记忆" meta={`${memories.length} 条`} />
          <div className="input-block">
            <textarea
              value={memoryText}
              placeholder="写下一条之后要被 AI 或自己反复调用的信息"
              onChange={(event) => setMemoryText(event.target.value)}
            />
            <div className="inline-fields">
              <input value={memoryTags} placeholder="标签，用逗号分隔" onChange={(event) => setMemoryTags(event.target.value)} />
              <button className="primary-button" type="button" disabled={isLoading} onClick={() => void addMemory()}>
                写入记忆
              </button>
            </div>
          </div>
          <div className="item-list">
            {memories.length === 0 ? <EmptyState text="还没有长期记忆。" /> : null}
            {memories.map((item) => (
              <button className="list-item" key={item.id} type="button" onClick={() => setSelected(item)}>
                <div>
                  <strong>{item.tags.length ? item.tags.join(" / ") : "未标记"}</strong>
                  <span>{item.content}</span>
                </div>
                <small>memory</small>
              </button>
            ))}
          </div>
        </>
      );
    }

    if (activeView === "library") {
      return (
        <>
          <PanelHeader eyebrow="Library" title="本地文件库" meta={`${documents.length} 个文档`} />
          <div className="input-block">
            <div className="inline-fields">
              <input value={manualSource} placeholder="来源名称" onChange={(event) => setManualSource(event.target.value)} />
              <button className="secondary-button" type="button" disabled={isLoading} onClick={() => void ingestSelectedFile()}>
                选择文件
              </button>
            </div>
            <textarea value={manualText} placeholder="也可以直接粘贴一段文本入库" onChange={(event) => setManualText(event.target.value)} />
            <button className="primary-button" type="button" disabled={isLoading} onClick={() => void ingestManualText()}>
              写入文本
            </button>
          </div>
          <div className="item-list">
            {documents.length === 0 ? <EmptyState text="还没有导入文件。先点击“选择文件”或粘贴文本。" /> : null}
            {documents.map((item) => (
              <button className="list-item" key={item.id} type="button" onClick={() => setSelected(item)}>
                <div>
                  <strong>{compactPath(item.source)}</strong>
                  <span>{item.content_preview}</span>
                </div>
                <small>doc</small>
              </button>
            ))}
          </div>
        </>
      );
    }

    return (
      <>
        <PanelHeader
          eyebrow="Folder"
          title="文件夹导入"
          meta={`${folderScan?.importable ?? 0} 个可导入 / ${folderImport?.imported ?? 0} 个已导入`}
        />
        <div className="input-block">
          <div className="inline-fields">
            <input value={folderPath} placeholder="选择要扫描的文件夹" onChange={(event) => setFolderPath(event.target.value)} />
            <button className="secondary-button" type="button" disabled={isLoading} onClick={() => void chooseFolder()}>
              选文件夹
            </button>
          </div>
          <div className="inline-fields">
            <button className="ghost-button" type="button" disabled={isLoading} onClick={() => void scanFolder()}>
              重新扫描
            </button>
            <button className="primary-button" type="button" disabled={isLoading || !folderPath.trim()} onClick={() => void importFolder()}>
              开始导入
            </button>
          </div>
          <div className="folder-summary">
            <div>
              <small>扫描</small>
              <strong>{folderScan ? folderScan.scanned : 0}</strong>
            </div>
            <div>
              <small>可导入</small>
              <strong>{folderScan ? folderScan.importable : 0}</strong>
            </div>
            <div>
              <small>总大小</small>
              <strong>{formatBytes(folderScan?.totalBytes ?? 0)}</strong>
            </div>
            <div>
              <small>已导入</small>
              <strong>{folderImport ? folderImport.imported : 0}</strong>
            </div>
          </div>
        </div>
        <div className="item-list">
          {folderScan?.files?.length ? null : <EmptyState text="先选择一个文件夹，系统会把可导入的文本文件列出来。" />}
          {folderScan?.files?.map((item) => (
            <button className="list-item" key={`${item.relativePath}-${item.path}`} type="button" onClick={() => setSelected(item)}>
              <div>
                <strong>{compactPath(item.relativePath)}</strong>
                <span>{item.reason || `${formatBytes(item.size)} · ${item.importable ? "可导入" : "跳过"}`}</span>
              </div>
              <small>{item.status}</small>
            </button>
          ))}
          {folderImport?.files?.length ? <ImportSummary items={folderImport.files} /> : null}
        </div>
      </>
    );
  }
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

function EmptyState(props: { text: string }) {
  return <div className="empty-state">{props.text}</div>;
}

function ImportSummary(props: { items: FolderScanFile[] }) {
  return (
    <div className="import-summary">
      <div className="import-summary-head">
        <strong>导入结果</strong>
        <small>{props.items.length} 项</small>
      </div>
      {props.items.map((item) => (
        <div className={`import-row ${item.status}`} key={`${item.relativePath}-${item.status}`}>
          <span>{compactPath(item.relativePath)}</span>
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
          <span>{compactPath(item.title || item.url)}</span>
          <small>{item.status === "imported" ? "已导入" : item.error || "失败"}</small>
        </div>
      ))}
    </div>
  );
}

function DetailPanel(props: { item: SelectedItem }) {
  const item = props.item;
  let title = "等待选择";
  let subtitle = "选择左侧项目后查看详情。";
  let body = "";
  let meta: Array<[string, string]> = [];

  if (item && "content_preview" in item) {
    title = compactPath(item.source);
    subtitle = "文档";
    body = item.content_preview;
    meta = [["ID", item.id], ["来源", item.source]];
  } else if (item && "content" in item) {
    title = item.tags.length ? item.tags.join(" / ") : "长期记忆";
    subtitle = "记忆";
    body = item.content;
    meta = [["ID", item.id], ["标签", item.tags.join(", ") || "无"]];
  } else if (item && "importable" in item) {
    title = compactPath(item.relativePath);
    subtitle = item.status === "imported" ? "已导入文件" : item.status;
    body = item.reason || `${formatBytes(item.size)} · ${item.ext || "unknown"}`;
    meta = [
      ["路径", item.path],
      ["大小", formatBytes(item.size)],
      ["状态", item.status],
      ["可导入", item.importable ? "是" : "否"]
    ];
    if (typeof item.chunks === "number") {
      meta.push(["片段", String(item.chunks)]);
    }
    if (item.document_id) {
      meta.push(["文档 ID", item.document_id]);
    }
  } else if (item && "capture_method" in item) {
    title = item.title || compactPath(item.url);
    subtitle = `采集 · ${item.capture_method}`;
    body = item.error || item.text_preview || "暂无预览。";
    meta = [
      ["URL", item.url],
      ["平台", item.source_platform || "web"],
      ["状态", item.status],
      ["时间", formatDate(item.created_at)],
      ["标签", item.tags.join(", ") || "无"]
    ];
    if (item.document_id) {
      meta.push(["文档 ID", item.document_id]);
    }
    if (item.html_path) {
      meta.push(["HTML", item.html_path]);
    }
    if (item.screenshot_path) {
      meta.push(["截图", item.screenshot_path]);
    }
  } else if (item) {
    title = item.kind === "memory" ? "记忆结果" : compactPath(item.source || item.doc_id || item.id);
    subtitle = item.kind;
    body = item.text;
    meta = [
      ["ID", item.id],
      ["来源", item.source || item.doc_id || "无"],
      ["匹配度", scoreLabel(item.score)]
    ];
  }

  return (
    <aside className="detail-panel">
      <div className="detail-head">
        <span className="eyebrow">Preview</span>
        <h2>{title}</h2>
        <small>{subtitle}</small>
      </div>
      <div className="detail-body">{body || "暂无内容。"}</div>
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

export default App;
