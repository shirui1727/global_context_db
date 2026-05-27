from typing import Any

from mcp.server.fastmcp import FastMCP
import uvicorn
from starlette.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.schemas import (
    AssetArtifactCreate,
    AssetAnalysisArtifact,
    AssetAnalysisManifest,
    AssetCreate,
    AssetObservedItem,
    ContextCubeBindingCreate,
    ContextCubeCreate,
    ContextCubeUpdate,
    AssetScanRunCreate,
    AssetSearchRequest,
    AssetUpdate,
    FileReferenceCreate,
    FileReferenceUpdate,
    ForgetRequest,
    ImprovementTaskCreate,
    ImprovementTaskUpdate,
    ImproveRequest,
    IngestRequest,
    MemoryCreate,
    MemoryEvidenceCreate,
    MemoryPromotionCreate,
    MemoryPromotionReview,
    MemoryUpdate,
    RecallRequest,
    RememberRequest,
    ResumeContextRequest,
    RetrievalEvalCase,
    RetrievalEvalRequest,
    SessionCreate,
    SessionEventCreate,
    SessionTraceCreate,
    SessionUpdate,
)
from app.backup.service import export_snapshot, list_snapshots, restore_snapshot
from app.assets.service import (
    create_asset,
    get_asset,
    list_asset_artifacts,
    list_assets,
    rebuild_asset_vectors,
    register_asset_analysis_manifest,
    register_asset_artifact,
    run_asset_scan,
    search_assets,
    update_asset,
)
from app.files.service import add_file_reference, list_file_references, update_file_reference
from app.governance.service import diagnostics
from app.control.service import forget as control_forget
from app.control.service import improve as control_improve
from app.control.service import recall as control_recall
from app.control.service import remember as control_remember
from app.cubes.service import bind_to_cube, create_cube, get_cube, list_cube_bindings, list_cubes, update_cube
from app.improvements.service import create_improvement_task, list_improvement_tasks, update_improvement_task
from app.ingest.pipeline import ingest_text
from app.memory.service import (
    add_memory,
    add_memory_evidence,
    create_memory_promotion,
    delete_memory,
    list_audit_logs,
    list_memory_evidence,
    list_memory_promotions,
    list_memories,
    list_memory_versions,
    enqueue_memory_quality_improvements,
    memory_quality_report,
    review_memory_promotion,
    search_memory,
    update_memory,
)
from app.retrieval.service import run_retrieval_eval, search_context
from app.sessions.service import (
    add_session_event,
    add_session_trace,
    create_session,
    get_resume_context,
    update_session,
)
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
    cube_id: str | None = None,
    user_id: str = "default",
    tags: list[str] | None = None,
    agent_id: str | None = None,
    session_id: str | None = None,
    conversation_id: str | None = None,
    memory_type: str = "long_term",
    context_domain: str = "memory",
    status: str = "active",
    source_kind: str = "agent_note",
    trust_level: str = "verified",
    metadata: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Store a durable memory for later recall."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return add_memory(
        MemoryCreate(
            content=content,
            cube_id=cube_id,
            tags=tags or [],
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            conversation_id=conversation_id,
            memory_type=memory_type,
            context_domain=context_domain,
            status=status,
            source_kind=source_kind,
            trust_level=trust_level,
            metadata=metadata or {},
        )
    )


@mcp.tool()
def gcd_search_memories(
    query: str,
    top_k: int = 5,
    cube_id: str | None = None,
    cube_ids: list[str] | None = None,
    user_id: str | None = None,
    agent_id: str | None = None,
    memory_type: str | None = None,
) -> dict[str, Any]:
    """Search stored memories by semantic similarity."""
    bootstrap(settings)
    scoped_cube_ids = cube_ids or ([cube_id] if cube_id else None)
    return search_memory(query, top_k, user_id=user_id, agent_id=agent_id, memory_type=memory_type, cube_ids=scoped_cube_ids)


@mcp.tool()
def memory_search(
    query: str,
    top_k: int = 5,
    cube_id: str | None = None,
    cube_ids: list[str] | None = None,
    user_id: str | None = None,
    agent_id: str | None = None,
    memory_type: str | None = None,
) -> dict[str, Any]:
    """Compatibility alias for older clients that call memory_search."""
    bootstrap(settings)
    scoped_cube_ids = cube_ids or ([cube_id] if cube_id else None)
    return search_memory(query, top_k, user_id=user_id, agent_id=agent_id, memory_type=memory_type, cube_ids=scoped_cube_ids)


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
def gcd_add_memory_evidence(
    memory_id: str,
    source_domain: str,
    source_id: str,
    quote: str = "",
    confidence: float = 1.0,
    metadata: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Attach evidence to a long-term memory."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return add_memory_evidence(
        memory_id,
        MemoryEvidenceCreate(
            source_domain=source_domain,
            source_id=source_id,
            quote=quote,
            confidence=confidence,
            metadata=metadata or {},
        ),
    )


@mcp.tool()
def gcd_list_memory_evidence(memory_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """List evidence references for a memory."""
    bootstrap(settings)
    return list_memory_evidence(memory_id, limit)


@mcp.tool()
def gcd_create_memory_promotion(
    source_session_id: str,
    proposed_content: str,
    source_event_ids: list[str] | None = None,
    tags: list[str] | None = None,
    memory_type: str = "long_term",
    user_id: str = "default",
    agent_id: str | None = None,
    project_path: str | None = None,
    reason: str = "",
    created_by: str | None = None,
    metadata: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Create a proposal to promote session material into long-term memory."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return create_memory_promotion(
        MemoryPromotionCreate(
            source_session_id=source_session_id,
            source_event_ids=source_event_ids or [],
            proposed_content=proposed_content,
            tags=tags or [],
            memory_type=memory_type,
            user_id=user_id,
            agent_id=agent_id,
            project_path=project_path,
            reason=reason,
            created_by=created_by,
            metadata=metadata or {},
        )
    )


@mcp.tool()
def gcd_list_memory_promotions(
    limit: int = 100,
    status: str | None = None,
    source_session_id: str | None = None,
) -> list[dict[str, Any]]:
    """List memory promotion proposals."""
    bootstrap(settings)
    return list_memory_promotions(limit=limit, status=status, source_session_id=source_session_id)


@mcp.tool()
def gcd_memory_quality_report(limit: int = 100) -> dict[str, Any]:
    """Report low-evidence, stale, and conflict candidate memories."""
    bootstrap(settings)
    return memory_quality_report(limit)


@mcp.tool()
def gcd_enqueue_memory_quality_improvements(
    limit: int = 100,
    created_by: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Turn memory quality candidates into tracked improvement tasks."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return enqueue_memory_quality_improvements(limit=limit, created_by=created_by)


@mcp.tool()
def gcd_create_cube(
    name: str,
    cube_type: str = "project",
    owner_id: str | None = None,
    visibility: str = "private",
    status: str = "active",
    created_by: str | None = None,
    metadata: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Create a Context Cube memory space for project/user/agent/shared isolation."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return create_cube(
        ContextCubeCreate(
            name=name,
            cube_type=cube_type,
            owner_id=owner_id,
            visibility=visibility,
            status=status,
            created_by=created_by,
            metadata=metadata or {},
        )
    )


@mcp.tool()
def gcd_list_cubes(
    limit: int = 100,
    cube_type: str | None = None,
    owner_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """List Context Cubes."""
    bootstrap(settings)
    return list_cubes(limit=limit, cube_type=cube_type, owner_id=owner_id, status=status)


@mcp.tool()
def gcd_get_cube(cube_id: str) -> dict[str, Any]:
    """Get one Context Cube by id."""
    bootstrap(settings)
    return get_cube(cube_id)


@mcp.tool()
def gcd_update_cube(
    cube_id: str,
    name: str | None = None,
    cube_type: str | None = None,
    owner_id: str | None = None,
    visibility: str | None = None,
    status: str | None = None,
    metadata: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Update Context Cube metadata or lifecycle status."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return update_cube(
        cube_id,
        ContextCubeUpdate(
            name=name,
            cube_type=cube_type,
            owner_id=owner_id,
            visibility=visibility,
            status=status,
            metadata=metadata,
        ),
    )


@mcp.tool()
def gcd_bind_to_cube(
    cube_id: str,
    target_domain: str,
    target_id: str,
    binding_kind: str = "owns",
    metadata: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Bind a memory/document/asset/session/improvement object to a Context Cube."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return bind_to_cube(
        cube_id,
        ContextCubeBindingCreate(
            target_domain=target_domain,
            target_id=target_id,
            binding_kind=binding_kind,
            metadata=metadata or {},
        ),
    )


@mcp.tool()
def gcd_list_cube_bindings(cube_id: str, limit: int = 100) -> list[dict[str, Any]]:
    """List objects bound to a Context Cube."""
    bootstrap(settings)
    return list_cube_bindings(cube_id, limit)


@mcp.tool()
def gcd_run_retrieval_eval(
    cases: list[dict[str, Any]],
    top_k: int = 5,
) -> dict[str, Any]:
    """Run a fixed retrieval evaluation fixture and report domain/id hit rates."""
    bootstrap(settings)
    request = RetrievalEvalRequest(cases=[RetrievalEvalCase(**case) for case in cases], top_k=top_k)
    return run_retrieval_eval([case.model_dump() for case in request.cases], top_k=request.top_k)


@mcp.tool()
def gcd_review_memory_promotion(
    proposal_id: str,
    action: str = "approve",
    reviewed_by: str | None = None,
    trust_level: str = "verified",
    status_on_memory: str = "active",
    metadata: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Approve/promote or reject a memory promotion proposal."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return review_memory_promotion(
        proposal_id,
        MemoryPromotionReview(
            action=action,
            reviewed_by=reviewed_by,
            trust_level=trust_level,
            status_on_memory=status_on_memory,
            metadata=metadata or {},
        ),
    )


@mcp.tool()
def gcd_list_audit_logs(limit: int = 100) -> list[dict[str, Any]]:
    """List recent audit logs for memory changes."""
    bootstrap(settings)
    return list_audit_logs(limit)


@mcp.tool()
def gcd_diagnostics() -> dict[str, Any]:
    """Return read-only service diagnostics for governance and recovery."""
    bootstrap(settings)
    return diagnostics()


@mcp.tool()
def gcd_export_snapshot(label: str | None = None, api_key: str | None = None) -> dict[str, Any]:
    """Export a manual snapshot of sqlite, lancedb and artifacts."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return export_snapshot(label)


@mcp.tool()
def gcd_list_snapshots(limit: int = 20) -> list[dict[str, Any]]:
    """List available manual snapshots."""
    bootstrap(settings)
    return list_snapshots(limit)


@mcp.tool()
def gcd_restore_snapshot(snapshot_path: str, api_key: str | None = None) -> dict[str, Any]:
    """Restore a previously exported snapshot."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return restore_snapshot(snapshot_path)


@mcp.tool()
def memory_export_snapshot(label: str | None = None, api_key: str | None = None) -> dict[str, Any]:
    """Compatibility alias for older clients that expect memory_export_snapshot."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return export_snapshot(label)


@mcp.tool()
def memory_restore_snapshot(snapshot_path: str, api_key: str | None = None) -> dict[str, Any]:
    """Compatibility alias for older clients that expect memory_restore_snapshot."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return restore_snapshot(snapshot_path)


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
def gcd_add_asset(
    uri: str,
    cube_id: str | None = None,
    title: str | None = None,
    summary: str = "",
    tags: list[str] | None = None,
    media_type: str | None = None,
    asset_kind: str = "generic_asset",
    asset_key: str | None = None,
    checksum: str | None = None,
    size_bytes: int | None = None,
    modified_at: str | None = None,
    status: str = "active",
    trust_level: str = "unverified",
    source_kind: str = "nas_reference",
    analysis_status: str = "indexed",
    version_group_id: str | None = None,
    created_by: str | None = None,
    confirmed_by: str | None = None,
    metadata: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Create or update a governed NAS asset with stable identity, location, and version tracking."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return create_asset(
        AssetCreate(
            uri=uri,
            cube_id=cube_id,
            title=title,
            summary=summary,
            tags=tags or [],
            media_type=media_type,
            asset_kind=asset_kind,
            asset_key=asset_key,
            checksum=checksum,
            size_bytes=size_bytes,
            modified_at=modified_at,
            status=status,
            trust_level=trust_level,
            source_kind=source_kind,
            analysis_status=analysis_status,
            version_group_id=version_group_id,
            created_by=created_by,
            confirmed_by=confirmed_by,
            metadata=metadata or {},
        )
    )


@mcp.tool()
def gcd_search_assets(
    query: str,
    top_k: int = 5,
    cube_id: str | None = None,
    cube_ids: list[str] | None = None,
    asset_kind: str | None = None,
    trust_level: str | None = None,
) -> dict[str, Any]:
    """Search governed assets only, without mixing memories or documents."""
    bootstrap(settings)
    return search_assets(
        AssetSearchRequest(
            query=query,
            top_k=top_k,
            cube_id=cube_id,
            cube_ids=cube_ids or [],
            asset_kind=asset_kind,
            trust_level=trust_level,
        )
    )


@mcp.tool()
def gcd_list_assets(
    limit: int = 100,
    status: str | None = None,
    asset_kind: str | None = None,
    trust_level: str | None = None,
) -> list[dict[str, Any]]:
    """List governed assets."""
    bootstrap(settings)
    return list_assets(limit, status=status, asset_kind=asset_kind, trust_level=trust_level)


@mcp.tool()
def gcd_update_asset(
    asset_id: str,
    title: str | None = None,
    summary: str | None = None,
    tags: list[str] | None = None,
    media_type: str | None = None,
    asset_kind: str | None = None,
    status: str | None = None,
    trust_level: str | None = None,
    source_kind: str | None = None,
    analysis_status: str | None = None,
    updated_by: str | None = None,
    confirmed_by: str | None = None,
    metadata: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Update governed asset metadata and lifecycle state."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return update_asset(
        asset_id,
        AssetUpdate(
            title=title,
            summary=summary,
            tags=tags,
            media_type=media_type,
            asset_kind=asset_kind,
            status=status,
            trust_level=trust_level,
            source_kind=source_kind,
            analysis_status=analysis_status,
            updated_by=updated_by,
            confirmed_by=confirmed_by,
            metadata=metadata,
        ),
    )


@mcp.tool()
def gcd_list_asset_versions(asset_id: str) -> list[dict[str, Any]]:
    """List versions for a governed asset."""
    bootstrap(settings)
    return get_asset(asset_id)["versions"]


@mcp.tool()
def gcd_list_asset_artifacts(asset_id: str) -> list[dict[str, Any]]:
    """List derived artifacts registered for a governed asset."""
    bootstrap(settings)
    return list_asset_artifacts(asset_id)


@mcp.tool()
def gcd_register_asset_artifact(
    asset_id: str,
    artifact_kind: str,
    artifact_uri: str,
    version_id: str | None = None,
    media_type: str | None = None,
    checksum: str | None = None,
    status: str = "ready",
    generated_by: str | None = None,
    metadata: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Register a derived asset artifact such as thumbnail, OCR text, ASR text, or keyframe."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return register_asset_artifact(
        asset_id,
        AssetArtifactCreate(
            version_id=version_id,
            artifact_kind=artifact_kind,
            artifact_uri=artifact_uri,
            media_type=media_type,
            checksum=checksum,
            status=status,
            generated_by=generated_by,
            metadata=metadata or {},
        ),
    )


@mcp.tool()
def gcd_register_asset_analysis_manifest(
    asset_id: str,
    artifacts: list[dict[str, Any]],
    version_id: str | None = None,
    analysis_status: str = "indexed",
    summary: str | None = None,
    tags: list[str] | None = None,
    generated_by: str | None = None,
    metadata: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Register a batch of derived media analysis artifacts and index text outputs."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return register_asset_analysis_manifest(
        asset_id,
        AssetAnalysisManifest(
            version_id=version_id,
            analysis_status=analysis_status,
            summary=summary,
            tags=tags or [],
            generated_by=generated_by,
            artifacts=[AssetAnalysisArtifact(**item) for item in artifacts],
            metadata=metadata or {},
        ),
    )


@mcp.tool()
def gcd_run_asset_scan(
    scope_prefix: str,
    observed: list[dict[str, Any]],
    mark_missing: bool = True,
    created_by: str | None = None,
    metadata: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Process a manifest-based asset scan without directly reading NAS files."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return run_asset_scan(
        AssetScanRunCreate(
            scope_prefix=scope_prefix,
            mark_missing=mark_missing,
            observed=[AssetObservedItem(**item) for item in observed],
            created_by=created_by,
            metadata=metadata or {},
        )
    )


@mcp.tool()
def gcd_rebuild_asset_vectors(clean_legacy: bool = True, api_key: str | None = None) -> dict[str, Any]:
    """Rebuild asset vectors and optionally remove old file_reference vector rows."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return rebuild_asset_vectors(clean_legacy=clean_legacy)


@mcp.tool()
def gcd_start_session(
    source_agent: str = "unknown_agent",
    cube_id: str | None = None,
    project_path: str | None = None,
    title: str | None = None,
    summary: str = "",
    metadata: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Start a v0.3 agent session for trace and resume context."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return create_session(
        SessionCreate(
            cube_id=cube_id,
            source_agent=source_agent,
            project_path=project_path,
            title=title,
            summary=summary,
            created_by=source_agent,
            metadata=metadata or {},
        )
    )


@mcp.tool()
def gcd_record_session_event(
    session_id: str,
    event_type: str = "assistant_note",
    role: str | None = None,
    content: str = "",
    tool_name: str | None = None,
    tool_args: dict[str, Any] | None = None,
    tool_result: str | None = None,
    metadata: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Record one v0.3 session event."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return add_session_event(
        session_id,
        SessionEventCreate(
            event_type=event_type,
            role=role,
            content=content,
            tool_name=tool_name,
            tool_args=tool_args or {},
            tool_result=tool_result,
            metadata=metadata or {},
        ),
    )


@mcp.tool()
def gcd_record_tool_trace(
    session_id: str,
    origin_function: str,
    status: str = "ok",
    memory_query: str = "",
    memory_context: str = "",
    method_params: dict[str, Any] | None = None,
    method_return_value: Any = None,
    error_message: str = "",
    feedback_text: str = "",
    metadata: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Record an agent tool trace and mirror it into session events."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return add_session_trace(
        session_id,
        SessionTraceCreate(
            origin_function=origin_function,
            status=status,
            memory_query=memory_query,
            memory_context=memory_context,
            method_params=method_params or {},
            method_return_value=method_return_value,
            error_message=error_message,
            feedback_text=feedback_text,
            metadata=metadata or {},
        ),
    )


@mcp.tool()
def gcd_get_resume_context(
    query: str | None = None,
    session_id: str | None = None,
    project_path: str | None = None,
    top_k: int = 5,
    include_raw_events: bool = True,
    context_budget_chars: int = 12000,
) -> dict[str, Any]:
    """Build deterministic resume context from session events, tasks, memories, documents, and assets."""
    bootstrap(settings)
    return get_resume_context(
        ResumeContextRequest(
            query=query,
            session_id=session_id,
            project_path=project_path,
            top_k=top_k,
            include_raw_events=include_raw_events,
            context_budget_chars=context_budget_chars,
        )
    )


@mcp.tool()
def gcd_end_session(session_id: str, summary: str | None = None, api_key: str | None = None) -> dict[str, Any]:
    """End a v0.3 agent session."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return update_session(session_id, SessionUpdate(status="ended", summary=summary or None))


@mcp.tool()
def gcd_create_improvement_task(
    task_kind: str,
    target_domain: str,
    target_id: str,
    cube_id: str | None = None,
    priority: int = 50,
    reason: str = "",
    created_by: str | None = None,
    metadata: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Create a deterministic v0.3 improvement task."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return create_improvement_task(
        ImprovementTaskCreate(
            task_kind=task_kind,
            cube_id=cube_id,
            target_domain=target_domain,
            target_id=target_id,
            priority=priority,
            reason=reason,
            created_by=created_by,
            metadata=metadata or {},
        )
    )


@mcp.tool()
def gcd_list_improvement_tasks(
    limit: int = 100,
    status: str | None = None,
    task_kind: str | None = None,
    target_domain: str | None = None,
    target_id: str | None = None,
) -> list[dict[str, Any]]:
    """List v0.3 improvement tasks."""
    bootstrap(settings)
    return list_improvement_tasks(limit, status=status, task_kind=task_kind, target_domain=target_domain, target_id=target_id)


@mcp.tool()
def gcd_update_improvement_task(
    task_id: str,
    status: str | None = None,
    priority: int | None = None,
    reason: str | None = None,
    claimed_by: str | None = None,
    error_message: str | None = None,
    metadata: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Update a v0.3 improvement task."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return update_improvement_task(
        task_id,
        ImprovementTaskUpdate(
            status=status,
            priority=priority,
            reason=reason,
            claimed_by=claimed_by,
            error_message=error_message,
            metadata=metadata,
        ),
    )


@mcp.tool()
def gcd_improve(
    task_kind: str = "rebuild_vectors",
    cube_id: str | None = None,
    target_domain: str = "system",
    target_id: str = "all",
    execute: bool = False,
    clean_legacy: bool = True,
    priority: int = 50,
    reason: str = "",
    created_by: str | None = None,
    metadata: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Create or execute a v0.3 improvement task."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return control_improve(
        ImproveRequest(
            task_kind=task_kind,
            cube_id=cube_id,
            target_domain=target_domain,
            target_id=target_id,
            execute=execute,
            clean_legacy=clean_legacy,
            priority=priority,
            reason=reason,
            created_by=created_by,
            metadata=metadata or {},
        )
    )


@mcp.tool()
def gcd_remember(
    content_type: str = "memory",
    cube_id: str | None = None,
    content: str = "",
    source: str = "remember",
    session_id: str | None = None,
    project_path: str | None = None,
    tags: list[str] | None = None,
    user_id: str = "default",
    agent_id: str | None = None,
    memory_type: str = "long_term",
    asset: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """High-level remember verb for agent clients."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return control_remember(
        RememberRequest(
            content_type=content_type,
            content=content,
            source=source,
            cube_id=cube_id,
            session_id=session_id,
            project_path=project_path,
            tags=tags or [],
            user_id=user_id,
            agent_id=agent_id,
            memory_type=memory_type,
            asset=asset,
            metadata=metadata or {},
        )
    )


@mcp.tool()
def gcd_recall(
    query: str,
    top_k: int = 5,
    cube_id: str | None = None,
    cube_ids: list[str] | None = None,
    session_id: str | None = None,
    project_path: str | None = None,
    mode: str = "context_search",
    include_resume: bool = False,
    include_raw_events: bool = False,
    context_budget_chars: int = 12000,
) -> dict[str, Any]:
    """High-level recall verb for grouped context search and optional resume context."""
    bootstrap(settings)
    return control_recall(
        RecallRequest(
            query=query,
            top_k=top_k,
            cube_id=cube_id,
            cube_ids=cube_ids or [],
            session_id=session_id,
            project_path=project_path,
            mode=mode,
            include_resume=include_resume,
            include_raw_events=include_raw_events,
            context_budget_chars=context_budget_chars,
        )
    )


@mcp.tool()
def gcd_forget(
    target_domain: str,
    target_id: str,
    reason: str = "",
    actor: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """High-level soft forget verb for memory or asset records."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return control_forget(ForgetRequest(target_domain=target_domain, target_id=target_id, reason=reason, actor=actor))


@mcp.tool()
def gcd_add_file_reference(
    uri: str,
    title: str | None = None,
    media_type: str | None = None,
    asset_kind: str | None = None,
    asset_key: str | None = None,
    size_bytes: int | None = None,
    checksum: str | None = None,
    summary: str = "",
    tags: list[str] | None = None,
    status: str = "active",
    source_kind: str = "nas_reference",
    trust_level: str = "unverified",
    version_group_id: str | None = None,
    analysis_status: str = "indexed",
    metadata: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Index an external NAS/local file by reference without copying the original file."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return add_file_reference(
        FileReferenceCreate(
            uri=uri,
            title=title,
            media_type=media_type,
            asset_kind=asset_kind,
            asset_key=asset_key,
            size_bytes=size_bytes,
            checksum=checksum,
            summary=summary,
            tags=tags or [],
            storage_mode="referenced",
            status=status,
            source_kind=source_kind,
            trust_level=trust_level,
            version_group_id=version_group_id,
            analysis_status=analysis_status,
            metadata=metadata or {},
        )
    )


@mcp.tool()
def gcd_list_file_references(
    limit: int = 100,
    status: str | None = None,
    media_type: str | None = None,
    asset_kind: str | None = None,
    trust_level: str | None = None,
) -> list[dict[str, Any]]:
    """List external files indexed by reference."""
    bootstrap(settings)
    return list_file_references(
        limit,
        status=status,
        media_type=media_type,
        asset_kind=asset_kind,
        trust_level=trust_level,
    )


@mcp.tool()
def gcd_update_file_reference(
    file_reference_id: str,
    title: str | None = None,
    media_type: str | None = None,
    asset_kind: str | None = None,
    asset_key: str | None = None,
    size_bytes: int | None = None,
    checksum: str | None = None,
    summary: str | None = None,
    tags: list[str] | None = None,
    status: str | None = None,
    source_kind: str | None = None,
    trust_level: str | None = None,
    version_group_id: str | None = None,
    analysis_status: str | None = None,
    derived_artifacts: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Update an indexed external file reference, including asset governance status."""
    bootstrap(settings)
    require_mcp_write_key(api_key)
    return update_file_reference(
        file_reference_id,
        FileReferenceUpdate(
            title=title,
            media_type=media_type,
            asset_kind=asset_kind,
            asset_key=asset_key,
            size_bytes=size_bytes,
            checksum=checksum,
            summary=summary,
            tags=tags,
            status=status,
            source_kind=source_kind,
            trust_level=trust_level,
            version_group_id=version_group_id,
            analysis_status=analysis_status,
            derived_artifacts=derived_artifacts,
            metadata=metadata,
        ),
    )


@mcp.tool()
def gcd_search_context(
    query: str,
    top_k: int = 5,
    cube_id: str | None = None,
    cube_ids: list[str] | None = None,
    context_domain: str | None = None,
    kind: str | None = None,
    mode: str = "context_search",
    legacy_flat: bool = False,
    context_budget_chars: int = 12000,
) -> dict[str, Any]:
    """Search all stored context, including memories and document chunks."""
    bootstrap(settings)
    return search_context(
        query,
        top_k,
        cube_id=cube_id,
        cube_ids=cube_ids or [],
        context_domain=context_domain,
        kind=kind,
        mode=mode,
        legacy_flat=legacy_flat,
        context_budget_chars=context_budget_chars,
    )


def main() -> None:
    bootstrap(settings)
    mcp.run()


def http_main() -> None:
    bootstrap(settings)
    configure_http_transport()
    app = mcp.streamable_http_app()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["mcp-session-id"],
    )
    uvicorn.run(
        app,
        host=settings.mcp_host,
        port=settings.mcp_port,
        log_level=mcp.settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
