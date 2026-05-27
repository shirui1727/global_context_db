from app.assets.service import create_asset, update_asset
from app.core.schemas import (
    AssetCreate,
    AssetUpdate,
    ForgetRequest,
    ImproveRequest,
    IngestRequest,
    MemoryCreate,
    MemoryUpdate,
    RecallRequest,
    RememberRequest,
    ResumeContextRequest,
    SessionEventCreate,
)
from app.improvements.service import run_improve
from app.ingest.pipeline import ingest_text
from app.memory.service import add_memory, update_memory
from app.retrieval.service import search_context
from app.sessions.service import add_session_event, get_resume_context


def remember(payload: RememberRequest) -> dict:
    content_type = payload.content_type
    if content_type == "memory":
        return {
            "content_type": content_type,
            "result": add_memory(
                MemoryCreate(
                    cube_id=payload.cube_id,
                    content=payload.content,
                    tags=payload.tags,
                    user_id=payload.user_id,
                    agent_id=payload.agent_id,
                    session_id=payload.session_id,
                    memory_type=payload.memory_type,
                    source_kind=payload.source,
                    metadata={**payload.metadata, "project_path": payload.project_path},
                )
            ),
        }
    if content_type == "document":
        return {"content_type": content_type, "result": ingest_text(IngestRequest(source=payload.source, text=payload.content))}
    if content_type == "asset":
        asset_payload = payload.asset or {}
        return {
            "content_type": content_type,
            "result": create_asset(AssetCreate(**asset_payload)),
        }
    if content_type == "session_event":
        if not payload.session_id:
            raise ValueError("session_id is required for content_type=session_event")
        return {
            "content_type": content_type,
            "result": add_session_event(
                payload.session_id,
                SessionEventCreate(content=payload.content, metadata=payload.metadata),
            ),
        }
    raise ValueError("content_type must be one of: memory, document, asset, session_event")


def recall(payload: RecallRequest) -> dict:
    result = search_context(
        payload.query,
        payload.top_k,
        cube_id=payload.cube_id,
        cube_ids=payload.cube_ids,
        mode=payload.mode,
        context_budget_chars=payload.context_budget_chars,
    )
    if payload.include_resume or payload.session_id or payload.project_path:
        result["resume_context"] = get_resume_context(
            ResumeContextRequest(
                query=payload.query,
                session_id=payload.session_id,
                project_path=payload.project_path,
                top_k=payload.top_k,
                include_raw_events=payload.include_raw_events,
                context_budget_chars=payload.context_budget_chars,
            )
        )
    return result


def forget(payload: ForgetRequest) -> dict:
    if payload.target_domain == "memory":
        return {
            "target_domain": "memory",
            "target_id": payload.target_id,
            "result": update_memory(payload.target_id, MemoryUpdate(status="archived", metadata={"forget_reason": payload.reason})),
        }
    if payload.target_domain == "asset":
        return {
            "target_domain": "asset",
            "target_id": payload.target_id,
            "result": update_asset(
                payload.target_id,
                AssetUpdate(status="archived", updated_by=payload.actor, metadata={"forget_reason": payload.reason}),
            ),
        }
    raise ValueError("target_domain must be one of: memory, asset")


def improve(payload: ImproveRequest) -> dict:
    return run_improve(payload)
