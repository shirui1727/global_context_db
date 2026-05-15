from typing import Any

from mcp.server.fastmcp import FastMCP

from app.core.config import settings
from app.core.schemas import IngestRequest, MemoryCreate, MemoryUpdate
from app.ingest.pipeline import ingest_text
from app.memory.service import (
    add_memory,
    delete_memory,
    list_audit_logs,
    list_memories,
    list_memory_versions,
    search_memory,
    update_memory,
)
from app.retrieval.service import search_context
from app.storage.bootstrap import bootstrap

mcp = FastMCP(
    "global-context-db",
    instructions=(
        "Shared memory and context database for AI tools. "
        "Use it to store durable memories, recall relevant context, and ingest text documents."
    ),
)


def configure_http_transport() -> None:
    mcp.settings.host = settings.mcp_host
    mcp.settings.port = settings.mcp_port
    mcp.settings.streamable_http_path = settings.mcp_path
    mcp.settings.transport_security = None


def require_mcp_write_key(api_key: str | None = None) -> None:
    if not settings.require_mcp_api_key:
        return
    if settings.api_key and api_key == settings.api_key:
        return
    raise ValueError("invalid or missing MCP API key")


@mcp.tool()
def gcd_health() -> dict[str, Any]:
    """Check whether the memory service is available."""
    bootstrap(settings)
    return {
        "ok": True,
        "service": settings.service_name,
        "data_dir": str(settings.data_dir),
    }


@mcp.tool()
def gcd_add_memory(
    content: str,
    user_id: str = "default",
    tags: list[str] | None = None,
    agent_id: str | None = None,
    session_id: str | None = None,
    conversation_id: str | None = None,
    memory_type: str = "long_term",
    metadata: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Store a durable memory for later recall."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return add_memory(
        MemoryCreate(
            content=content,
            tags=tags or [],
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            conversation_id=conversation_id,
            memory_type=memory_type,
            metadata=metadata or {},
        )
    )


@mcp.tool()
def gcd_search_memories(
    query: str,
    top_k: int = 5,
    user_id: str | None = None,
    agent_id: str | None = None,
    memory_type: str | None = None,
) -> dict[str, Any]:
    """Search stored memories by semantic similarity."""
    bootstrap(settings)
    return search_memory(query, top_k, user_id=user_id, agent_id=agent_id, memory_type=memory_type)


@mcp.tool()
def gcd_list_memories(
    user_id: str | None = None,
    agent_id: str | None = None,
    memory_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List recent memories, optionally filtered by user, agent, or memory type."""
    bootstrap(settings)
    return list_memories(user_id=user_id, agent_id=agent_id, memory_type=memory_type, limit=limit)


@mcp.tool()
def gcd_list_memory_versions(memory_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """List version history for a memory."""
    bootstrap(settings)
    return list_memory_versions(memory_id, limit)


@mcp.tool()
def gcd_list_audit_logs(limit: int = 100) -> list[dict[str, Any]]:
    """List recent audit logs for memory changes."""
    bootstrap(settings)
    return list_audit_logs(limit)


@mcp.tool()
def gcd_update_memory(
    memory_id: str,
    content: str | None = None,
    tags: list[str] | None = None,
    user_id: str | None = None,
    agent_id: str | None = None,
    session_id: str | None = None,
    conversation_id: str | None = None,
    memory_type: str | None = None,
    metadata: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Update a stored memory."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return update_memory(
        memory_id,
        MemoryUpdate(
            content=content,
            tags=tags,
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            conversation_id=conversation_id,
            memory_type=memory_type,
            metadata=metadata,
        ),
    )


@mcp.tool()
def gcd_delete_memory(memory_id: str, api_key: str | None = None) -> dict[str, Any]:
    """Delete a stored memory."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return delete_memory(memory_id)


@mcp.tool()
def gcd_ingest_text(source: str, text: str, api_key: str | None = None) -> dict[str, Any]:
    """Ingest a text document into the shared context database."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return ingest_text(IngestRequest(source=source, text=text))


@mcp.tool()
def gcd_search_context(query: str, top_k: int = 5) -> dict[str, Any]:
    """Search all stored context, including memories and document chunks."""
    bootstrap(settings)
    return search_context(query, top_k)


def main() -> None:
    bootstrap(settings)
    mcp.run()


def http_main() -> None:
    bootstrap(settings)
    configure_http_transport()
    mcp.run("streamable-http")


if __name__ == "__main__":
    main()
