import type { CaptureSummary, DesktopAPI, FeedSummary } from "./types";

const mockDocuments = [
  {
    id: "mock-doc-1",
    source: "开发预览文档.md",
    content_preview: "这里会显示已经导入到本地知识库的文件摘要。"
  }
];

const mockMemories = [
  {
    id: "mock-memory-1",
    content: "第一版采用本地优先，不要求普通用户安装 Docker。",
    tags: ["产品", "本地优先"],
    agent_id: null,
    session_id: null,
    conversation_id: null,
    user_id: "default",
    memory_type: "long_term",
    metadata: {}
  }
];

const mockCaptures: CaptureSummary[] = [
  {
    id: "mock-capture-1",
    document_id: "mock-doc-1",
    url: "https://example.com/article",
    title: "公开文章示例",
    text_preview: "浏览器插件保存后，网页标题、来源、正文预览会显示在这里。",
    html_path: null,
    screenshot_path: null,
    source_platform: "example.com",
    capture_method: "page",
    tags: ["web"],
    captured_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
    status: "imported",
    error: null
  }
];

const mockFeeds: FeedSummary[] = [
  {
    id: "mock-feed-1",
    url: "https://example.com/feed.xml",
    title: "示例 RSS",
    created_at: new Date().toISOString(),
    last_refreshed_at: null,
    items: []
  }
];

const mockAPI: DesktopAPI = {
  async getSettings() {
    return {
      backendUrl: "http://127.0.0.1:8000",
      backendMode: "local",
      apiKey: "",
      autoStartLocalBackend: true
    };
  },
  async saveSettings(payload) {
    return payload;
  },
  async testConnection() {
    return {
      ok: true,
      message: "开发预览连接正常",
      health: {
        ok: true,
        service: "global-context-db",
        data_dir: "data",
        sqlite_path: "data/gcd_v2.sqlite3",
        mcp: { host: "127.0.0.1", port: 8001, path: "/mcp" }
      }
    };
  },
  async getBackendStatus() {
    return {
      url: "http://127.0.0.1:8000",
      running: true,
      ownedByApp: false,
      message: "开发预览模式"
    };
  },
  async openBackendDashboard() {
    return true;
  },
  async openExternalUrl() {
    return true;
  },
  async chooseDocumentFile() {
    return null;
  },
  async chooseDocumentFolder() {
    return null;
  },
  async health() {
    return { ok: true };
  },
  async listDocuments() {
    return mockDocuments;
  },
  async listCaptures() {
    return mockCaptures;
  },
  async listMemories() {
    return mockMemories;
  },
  async listMemoryVersions() {
    return [];
  },
  async listAuditLogs() {
    return [];
  },
  async search(payload) {
    return {
      query: payload.query,
      results: [
        {
          id: "mock-result-1",
          kind: "chunk",
          text: `开发预览搜索：${payload.query}`,
          source: "开发预览",
          score: 0.91
        }
      ]
    };
  },
  async searchMemories(payload) {
    return {
      results: [
        {
          id: "mock-memory-result-1",
          kind: "memory",
          text: `记忆搜索：${payload.query}`,
          score: 0.88
        }
      ]
    };
  },
  async addMemory(payload) {
    const id = `mock-memory-${Date.now()}`;
    mockMemories.unshift({
      id,
      content: payload.content,
      tags: payload.tags,
      agent_id: null,
      session_id: null,
      conversation_id: null,
      user_id: "default",
      memory_type: "long_term",
      metadata: {}
    });
    return { memory_id: id, memory: mockMemories[0], status: "created" };
  },
  async updateMemory(payload) {
    const current = mockMemories.find((item) => item.id === payload.memoryId);
    if (current) {
      current.content = payload.content;
      current.tags = payload.tags;
    }
    return {
      memory_id: payload.memoryId,
      memory: current ?? {
        id: payload.memoryId,
        content: payload.content,
        tags: payload.tags,
        user_id: "default",
        agent_id: null,
        session_id: null,
        conversation_id: null,
        memory_type: "long_term",
        metadata: {}
      }
    };
  },
  async deleteMemory(payload) {
    const index = mockMemories.findIndex((item) => item.id === payload.memoryId);
    if (index >= 0) {
      mockMemories.splice(index, 1);
    }
    return { memory_id: payload.memoryId, deleted: index >= 0 };
  },
  async ingestText(payload) {
    const id = `mock-doc-${Date.now()}`;
    mockDocuments.unshift({
      id,
      source: payload.source,
      content_preview: payload.text.slice(0, 200)
    });
    return { document_id: id, chunks: Math.max(1, Math.ceil(payload.text.length / 800)) };
  },
  async ingestUrl(payload) {
    const id = `mock-url-doc-${Date.now()}`;
    const title = payload.url;
    mockDocuments.unshift({
      id,
      source: title,
      content_preview: "公开 URL 导入后的正文预览。"
    });
    mockCaptures.unshift({
      id: `mock-capture-${Date.now()}`,
      document_id: id,
      url: payload.url,
      title,
      text_preview: "公开 URL 导入后的正文预览。",
      html_path: null,
      screenshot_path: null,
      source_platform: payload.sourcePlatform ?? "web",
      capture_method: "url",
      tags: payload.tags ?? [],
      captured_at: new Date().toISOString(),
      created_at: new Date().toISOString(),
      status: "imported",
      error: null
    });
    return { capture_id: mockCaptures[0].id, document_id: id, chunks: 2, title, url: payload.url };
  },
  async addFeed(payload) {
    const feed = {
      id: `mock-feed-${Date.now()}`,
      url: payload.url,
      title: payload.title || payload.url,
      created_at: new Date().toISOString(),
      last_refreshed_at: null,
      items: []
    };
    mockFeeds.unshift(feed);
    return feed;
  },
  async listFeeds() {
    return mockFeeds;
  },
  async refreshFeed(payload) {
    const feed = mockFeeds.find((item) => item.id === payload.id) ?? mockFeeds[0];
    const refreshedAt = new Date().toISOString();
    feed.last_refreshed_at = refreshedAt;
    return {
      feed_id: feed.id,
      title: feed.title,
      imported: 0,
      skipped: 0,
      failed: 0,
      items: [],
      last_refreshed_at: refreshedAt
    };
  },
  async createCrawlJob(payload) {
    return {
      id: `mock-crawl-${Date.now()}`,
      urls: payload.urls,
      created_at: new Date().toISOString(),
      status: "completed",
      total: payload.urls.length,
      succeeded: payload.urls.length,
      failed: 0,
      items: payload.urls.map((url, index) => ({
        id: `mock-crawl-item-${index}`,
        job_id: "mock",
        url,
        title: url,
        document_id: `mock-doc-${index}`,
        status: "imported",
        error: null
      }))
    };
  },
  async getCrawlJob(payload) {
    return {
      id: payload.id,
      urls: [],
      created_at: new Date().toISOString(),
      status: "completed",
      total: 0,
      succeeded: 0,
      failed: 0,
      items: []
    };
  },
  async ingestFile() {
    return { document_id: "mock-file", chunks: 1 };
  },
  async scanFolder(payload) {
    return {
      folderPath: payload.folderPath,
      scanned: 2,
      importable: 2,
      skipped: 0,
      totalBytes: 2048,
      files: [
        {
          path: `${payload.folderPath}\\notes.md`,
          relativePath: "notes.md",
          size: 1024,
          ext: ".md",
          importable: true,
          status: "ready"
        },
        {
          path: `${payload.folderPath}\\brief.txt`,
          relativePath: "brief.txt",
          size: 1024,
          ext: ".txt",
          importable: true,
          status: "ready"
        }
      ]
    };
  },
  async ingestFolder(payload) {
    return {
      folderPath: payload.folderPath,
      scanned: 2,
      imported: 2,
      failed: 0,
      skipped: 0,
      totalBytes: 2048,
      totalChunks: 4,
      files: [
        {
          path: `${payload.folderPath}\\notes.md`,
          relativePath: "notes.md",
          size: 1024,
          ext: ".md",
          importable: true,
          status: "imported",
          document_id: "mock-folder-doc-1",
          chunks: 2
        },
        {
          path: `${payload.folderPath}\\brief.txt`,
          relativePath: "brief.txt",
          size: 1024,
          ext: ".txt",
          importable: true,
          status: "imported",
          document_id: "mock-folder-doc-2",
          chunks: 2
        }
      ]
    };
  },
  onBackendStatus() {
    return () => {};
  }
};

export function getDesktopAPI(): DesktopAPI {
  return window.desktopAPI ?? mockAPI;
}
