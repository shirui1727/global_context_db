export type BackendStatus = {
  url: string;
  running: boolean;
  ownedByApp: boolean;
  message: string;
};

export type DocumentSummary = {
  id: string;
  source: string;
  content_preview: string;
};

export type MemorySummary = {
  id: string;
  content: string;
  tags: string[];
  user_id?: string;
  agent_id?: string | null;
  session_id?: string | null;
  conversation_id?: string | null;
  memory_type?: string;
  metadata?: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
};

export type MemoryVersion = {
  id: string;
  memory_id: string;
  content: string;
  tags: string[];
  user_id?: string | null;
  agent_id?: string | null;
  session_id?: string | null;
  conversation_id?: string | null;
  memory_type?: string | null;
  metadata?: Record<string, unknown>;
  changed_at?: string | null;
  change_type: string;
};

export type AuditLog = {
  id: string;
  actor?: string | null;
  action: string;
  target_type?: string | null;
  target_id?: string | null;
  created_at?: string | null;
  metadata?: Record<string, unknown>;
};

export type SearchResult = {
  id: string;
  kind: string;
  text: string;
  source?: string;
  doc_id?: string;
  chunk_index?: number;
  tags?: string[] | string;
  user_id?: string | null;
  agent_id?: string | null;
  session_id?: string | null;
  conversation_id?: string | null;
  memory_type?: string | null;
  metadata?: Record<string, unknown>;
  score?: number;
};

export type SearchResponse = {
  query: string;
  results: SearchResult[];
};

export type IngestResponse = {
  document_id: string;
  chunks: number;
};

export type AddMemoryResponse = {
  memory_id: string;
  memory?: MemorySummary;
  status?: "created" | "deduplicated";
};

export type UpdateMemoryResponse = {
  memory_id: string;
  memory: MemorySummary;
};

export type DeleteMemoryResponse = {
  memory_id: string;
  deleted: boolean;
};

export type CaptureSummary = {
  id: string;
  document_id?: string | null;
  url: string;
  title: string;
  text_preview: string;
  html_path?: string | null;
  screenshot_path?: string | null;
  source_platform?: string | null;
  capture_method: string;
  tags: string[];
  captured_at?: string | null;
  created_at: string;
  status: "imported" | "failed";
  error?: string | null;
};

export type UrlIngestResponse = {
  capture_id: string;
  document_id: string;
  chunks: number;
  title: string;
  url: string;
};

export type FeedItemSummary = {
  id: string;
  feed_id: string;
  url: string;
  title: string;
  published_at?: string | null;
  document_id?: string | null;
  status: "imported" | "failed";
  error?: string | null;
  created_at: string;
};

export type FeedSummary = {
  id: string;
  url: string;
  title: string;
  created_at: string;
  last_refreshed_at?: string | null;
  items: FeedItemSummary[];
};

export type FeedRefreshResponse = {
  feed_id: string;
  title?: string | null;
  imported: number;
  skipped: number;
  failed: number;
  items: FeedItemSummary[];
  last_refreshed_at: string;
};

export type CrawlJobItem = {
  id: string;
  job_id: string;
  url: string;
  title?: string | null;
  document_id?: string | null;
  status: "imported" | "failed";
  error?: string | null;
};

export type CrawlJob = {
  id: string;
  urls: string[];
  created_at: string;
  status: "running" | "completed";
  total: number;
  succeeded: number;
  failed: number;
  items: CrawlJobItem[];
};

export type FolderScanFile = {
  path: string;
  relativePath: string;
  size: number;
  ext: string;
  importable: boolean;
  status: "ready" | "skipped" | "imported" | "failed";
  reason?: string;
  document_id?: string;
  chunks?: number;
};

export type FolderScanResult = {
  folderPath: string;
  scanned: number;
  importable: number;
  skipped: number;
  totalBytes: number;
  files: FolderScanFile[];
};

export type FolderImportResult = {
  folderPath: string;
  scanned: number;
  imported: number;
  failed: number;
  skipped: number;
  totalBytes: number;
  totalChunks: number;
  files: FolderScanFile[];
};

export type DesktopAPI = {
  getBackendStatus: () => Promise<BackendStatus>;
  openBackendDashboard: () => Promise<boolean>;
  openExternalUrl: (payload: { url: string }) => Promise<boolean>;
  chooseDocumentFile: () => Promise<string | null>;
  chooseDocumentFolder: () => Promise<string | null>;
  health: () => Promise<{ ok: boolean }>;
  listDocuments: () => Promise<DocumentSummary[]>;
  listCaptures: () => Promise<CaptureSummary[]>;
  listMemories: () => Promise<MemorySummary[]>;
  listMemoryVersions: (payload: { memoryId: string; limit?: number }) => Promise<MemoryVersion[]>;
  listAuditLogs: (payload?: { limit?: number }) => Promise<AuditLog[]>;
  search: (payload: { query: string; topK: number }) => Promise<SearchResponse>;
  searchMemories: (payload: { query: string; topK: number }) => Promise<{ results: SearchResult[] }>;
  addMemory: (payload: { content: string; tags: string[] }) => Promise<AddMemoryResponse>;
  updateMemory: (payload: { memoryId: string; content: string; tags: string[] }) => Promise<UpdateMemoryResponse>;
  deleteMemory: (payload: { memoryId: string }) => Promise<DeleteMemoryResponse>;
  ingestText: (payload: { source: string; text: string }) => Promise<IngestResponse>;
  ingestUrl: (payload: { url: string; tags?: string[]; sourcePlatform?: string | null }) => Promise<UrlIngestResponse>;
  addFeed: (payload: { url: string; title?: string | null }) => Promise<FeedSummary>;
  listFeeds: () => Promise<FeedSummary[]>;
  refreshFeed: (payload: { id: string }) => Promise<FeedRefreshResponse>;
  createCrawlJob: (payload: { urls: string[] }) => Promise<CrawlJob>;
  getCrawlJob: (payload: { id: string }) => Promise<CrawlJob>;
  ingestFile: (payload: { filePath: string }) => Promise<IngestResponse>;
  scanFolder: (payload: { folderPath: string }) => Promise<FolderScanResult>;
  ingestFolder: (payload: { folderPath: string }) => Promise<FolderImportResult>;
  onBackendStatus: (callback: (status: BackendStatus) => void) => () => void;
};
