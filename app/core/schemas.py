from typing import Any

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    source: str = "manual"
    text: str


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)


class MemoryCreate(BaseModel):
    content: str
    tags: list[str] = Field(default_factory=list)
    user_id: str = "default"
    agent_id: str | None = None
    session_id: str | None = None
    conversation_id: str | None = None
    memory_type: str = "long_term"
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryUpdate(BaseModel):
    content: str | None = None
    tags: list[str] | None = None
    user_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    conversation_id: str | None = None
    memory_type: str | None = None
    metadata: dict[str, Any] | None = None


class DocumentSummary(BaseModel):
    id: str
    source: str
    content_preview: str


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
