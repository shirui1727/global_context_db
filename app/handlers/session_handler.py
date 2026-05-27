
from dataclasses import dataclass

from app.core.schemas import SessionCreate, SessionEventCreate, SessionSummaryCreate, SessionTraceCreate, SessionUpdate
from app.runtime.components import RuntimeComponents
from app.sessions import service as session_service


@dataclass(frozen=True)
class SessionHandler:
    components: RuntimeComponents

    def create_session(self, payload: SessionCreate) -> dict:
        return session_service.create_session(payload)

    def get_session(self, session_id: str) -> dict:
        return session_service.get_session(session_id)

    def list_sessions(self, limit: int = 100, status: str | None = None, source_agent: str | None = None, project_path: str | None = None) -> list[dict]:
        return session_service.list_sessions(limit=limit, status=status, source_agent=source_agent, project_path=project_path)

    def update_session(self, session_id: str, payload: SessionUpdate) -> dict:
        return session_service.update_session(session_id, payload)

    def add_event(self, session_id: str, payload: SessionEventCreate) -> dict:
        return session_service.add_session_event(session_id, payload)

    def add_trace(self, session_id: str, payload: SessionTraceCreate) -> dict:
        return session_service.add_session_trace(session_id, payload)

    def add_summary(self, session_id: str, payload: SessionSummaryCreate) -> dict:
        return session_service.add_session_summary(session_id, payload)
