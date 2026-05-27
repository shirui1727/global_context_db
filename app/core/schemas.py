from typing import Any

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    source: str = "manual"
    text: str
    cube_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    cube_id: str | None = None
    cube_ids: list[str] = Field(default_factory=list)
    context_domain: str | None = None
    kind: str | None = None
    mode: str = "context_search"
    legacy_flat: bool = False
    context_budget_chars: int = Field(default=12000, ge=100, le=100000)


class RetrievalEvalCase(BaseModel):
    query: str
    expected_domain: str | None = None
    expected_id: str | None = None


class RetrievalEvalRequest(BaseModel):
    cases: list[RetrievalEvalCase]
    top_k: int = Field(default=5, ge=1, le=20)


class ContextCubeCreate(BaseModel):
    id: str | None = None
    name: str
    cube_type: str = "project"
    owner_id: str | None = None
    visibility: str = "private"
    status: str = "active"
    created_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContextCubeUpdate(BaseModel):
    name: str | None = None
    cube_type: str | None = None
    owner_id: str | None = None
    visibility: str | None = None
    status: str | None = None
    metadata: dict[str, Any] | None = None


class ContextCubeBindingCreate(BaseModel):
    target_domain: str
    target_id: str
    binding_kind: str = "owns"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReaderItem(BaseModel):
    source_domain: str
    source_id: str
    cube_id: str | None = None
    content: str
    content_kind: str = "note"
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0, le=1)
    provenance: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionCreate(BaseModel):
    id: str | None = None
    cube_id: str | None = None
    source_agent: str = "unknown_agent"
    project_path: str | None = None
    status: str = "running"
    title: str | None = None
    summary: str = ""
    created_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionUpdate(BaseModel):
    cube_id: str | None = None
    source_agent: str | None = None
    project_path: str | None = None
    status: str | None = None
    title: str | None = None
    summary: str | None = None
    ended_at: str | None = None
    metadata: dict[str, Any] | None = None


class SessionEventCreate(BaseModel):
    event_type: str = "assistant_note"
    role: str | None = None
    content: str = ""
    tool_name: str | None = None
    tool_args: dict[str, Any] = Field(default_factory=dict)
    tool_result: str | None = None
    created_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionTraceCreate(BaseModel):
    trace_id: str | None = None
    origin_function: str
    status: str = "ok"
    memory_query: str = ""
    memory_context: str = ""
    method_params: dict[str, Any] = Field(default_factory=dict)
    method_return_value: Any = None
    error_message: str = ""
    feedback_text: str = ""
    created_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionSummaryCreate(BaseModel):
    summary_kind: str = "manual"
    content: str
    status: str = "active"
    created_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionModelUsageCreate(BaseModel):
    model: str
    tokens_in: int = Field(default=0, ge=0)
    tokens_out: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResumeContextRequest(BaseModel):
    query: str | None = None
    project_path: str | None = None
    session_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    recent_events_limit: int = Field(default=20, ge=1, le=100)
    include_raw_events: bool = True
    context_budget_chars: int = Field(default=12000, ge=1000, le=100000)
    format: str = "handoff"


class ImprovementTaskCreate(BaseModel):
    task_kind: str
    target_domain: str
    target_id: str
    cube_id: str | None = None
    priority: int = Field(default=50, ge=0, le=100)
    reason: str = ""
    created_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ImprovementTaskUpdate(BaseModel):
    status: str | None = None
    priority: int | None = Field(default=None, ge=0, le=100)
    reason: str | None = None
    claimed_by: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] | None = None


class ImproveRequest(BaseModel):
    task_kind: str = "rebuild_vectors"
    target_domain: str = "system"
    target_id: str = "all"
    cube_id: str | None = None
    execute: bool = False
    clean_legacy: bool = True
    priority: int = Field(default=50, ge=0, le=100)
    reason: str = ""
    created_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RememberRequest(BaseModel):
    content_type: str = "memory"
    content: str = ""
    source: str = "remember"
    cube_id: str | None = None
    session_id: str | None = None
    project_path: str | None = None
    tags: list[str] = Field(default_factory=list)
    user_id: str = "default"
    agent_id: str | None = None
    memory_type: str = "long_term"
    asset: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecallRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    cube_id: str | None = None
    cube_ids: list[str] = Field(default_factory=list)
    session_id: str | None = None
    project_path: str | None = None
    mode: str = "context_search"
    include_resume: bool = False
    include_raw_events: bool = False
    context_budget_chars: int = Field(default=12000, ge=1000, le=100000)


class ForgetRequest(BaseModel):
    target_domain: str
    target_id: str
    reason: str = ""
    actor: str | None = None


class MemoryEvidenceCreate(BaseModel):
    source_domain: str
    source_id: str
    quote: str = ""
    confidence: float = Field(default=1.0, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryPromotionCreate(BaseModel):
    source_session_id: str
    cube_id: str | None = None
    source_event_ids: list[str] = Field(default_factory=list)
    proposed_content: str
    tags: list[str] = Field(default_factory=list)
    memory_type: str = "long_term"
    user_id: str = "default"
    agent_id: str | None = None
    project_path: str | None = None
    reason: str = ""
    created_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryPromotionUpdate(BaseModel):
    proposed_content: str | None = None
    tags: list[str] | None = None
    memory_type: str | None = None
    status: str | None = None
    reason: str | None = None
    reviewed_by: str | None = None
    metadata: dict[str, Any] | None = None


class MemoryPromotionReview(BaseModel):
    action: str = "approve"
    reviewed_by: str | None = None
    trust_level: str = "verified"
    status_on_memory: str = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryCreate(BaseModel):
    content: str
    cube_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    user_id: str = "default"
    agent_id: str | None = None
    session_id: str | None = None
    conversation_id: str | None = None
    memory_type: str = "long_term"
    context_domain: str = "memory"
    status: str = "active"
    source_kind: str = "agent_note"
    trust_level: str = "verified"
    metadata: dict[str, Any] = Field(default_factory=dict)
    evidence: list[MemoryEvidenceCreate] = Field(default_factory=list)


class MemoryUpdate(BaseModel):
    content: str | None = None
    cube_id: str | None = None
    tags: list[str] | None = None
    user_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    conversation_id: str | None = None
    memory_type: str | None = None
    context_domain: str | None = None
    status: str | None = None
    source_kind: str | None = None
    trust_level: str | None = None
    metadata: dict[str, Any] | None = None


class DocumentSummary(BaseModel):
    id: str
    source: str
    content_preview: str


class FileReferenceCreate(BaseModel):
    uri: str
    cube_id: str | None = None
    title: str | None = None
    media_type: str | None = None
    asset_kind: str | None = None
    asset_key: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    checksum: str | None = None
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    storage_mode: str = "referenced"
    context_domain: str = "asset"
    status: str = "active"
    source_kind: str = "nas_reference"
    trust_level: str = "unverified"
    version_group_id: str | None = None
    analysis_status: str = "indexed"
    metadata: dict[str, Any] = Field(default_factory=dict)


class FileReferenceUpdate(BaseModel):
    title: str | None = None
    media_type: str | None = None
    asset_kind: str | None = None
    asset_key: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    checksum: str | None = None
    summary: str | None = None
    tags: list[str] | None = None
    status: str | None = None
    source_kind: str | None = None
    trust_level: str | None = None
    version_group_id: str | None = None
    analysis_status: str | None = None
    derived_artifacts: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class AssetCreate(BaseModel):
    uri: str
    cube_id: str | None = None
    title: str | None = None
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    media_type: str | None = None
    asset_kind: str = "generic_asset"
    asset_key: str | None = None
    checksum: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    modified_at: str | None = None
    storage_mode: str = "referenced"
    status: str = "active"
    trust_level: str = "unverified"
    source_kind: str = "nas_reference"
    analysis_status: str = "indexed"
    version_group_id: str | None = None
    created_by: str | None = None
    confirmed_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssetUpdate(BaseModel):
    cube_id: str | None = None
    title: str | None = None
    summary: str | None = None
    tags: list[str] | None = None
    media_type: str | None = None
    asset_kind: str | None = None
    status: str | None = None
    trust_level: str | None = None
    source_kind: str | None = None
    analysis_status: str | None = None
    updated_by: str | None = None
    confirmed_by: str | None = None
    metadata: dict[str, Any] | None = None


class AssetSearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=50)
    cube_id: str | None = None
    cube_ids: list[str] = Field(default_factory=list)
    status: list[str] | None = None
    asset_kind: str | None = None
    trust_level: str | None = None


class AssetObservedItem(BaseModel):
    uri: str
    asset_key: str | None = None
    checksum: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    modified_at: str | None = None
    media_type: str | None = None
    asset_kind: str = "generic_asset"
    title: str | None = None
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    trust_level: str = "unverified"
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssetScanRunCreate(BaseModel):
    scope_prefix: str
    mark_missing: bool = True
    observed: list[AssetObservedItem] = Field(default_factory=list)
    created_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssetArtifactCreate(BaseModel):
    version_id: str | None = None
    artifact_kind: str
    artifact_uri: str
    media_type: str | None = None
    checksum: str | None = None
    status: str = "ready"
    generated_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssetArtifactUpdate(BaseModel):
    artifact_uri: str | None = None
    media_type: str | None = None
    checksum: str | None = None
    status: str | None = None
    generated_by: str | None = None
    metadata: dict[str, Any] | None = None


class AssetAnalysisArtifact(BaseModel):
    artifact_kind: str
    artifact_uri: str
    media_type: str | None = None
    checksum: str | None = None
    status: str = "ready"
    text: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssetAnalysisManifest(BaseModel):
    version_id: str | None = None
    analysis_status: str = "indexed"
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)
    generated_by: str | None = None
    artifacts: list[AssetAnalysisArtifact] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemorySummary(BaseModel):
    id: str
    content: str
    tags: list[str]
    user_id: str = "default"
    agent_id: str | None = None
    session_id: str | None = None
    conversation_id: str | None = None
    memory_type: str = "long_term"
    metadata: dict[str, Any] = Field(default_factory=dict)


class WebCaptureRequest(BaseModel):
    url: str
    title: str | None = None
    text: str = ""
    html: str | None = None
    screenshot: str | None = None
    tags: list[str] = Field(default_factory=list)
    source_platform: str | None = None
    captured_at: str | None = None
    capture_method: str = "page"


class UrlIngestRequest(BaseModel):
    url: str
    tags: list[str] = Field(default_factory=list)
    source_platform: str | None = None


class FeedCreateRequest(BaseModel):
    url: str
    title: str | None = None


class CrawlJobCreateRequest(BaseModel):
    urls: list[str] = Field(default_factory=list)


class SnapshotCreateRequest(BaseModel):
    label: str | None = None


class SnapshotRestoreRequest(BaseModel):
    snapshot_path: str
