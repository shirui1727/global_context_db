
from dataclasses import dataclass

from app.core.schemas import MemoryCreate, MemoryEvidenceCreate, MemoryUpdate, ReaderItem
from app.memory import service as memory_service
from app.runtime.components import RuntimeComponents


@dataclass(frozen=True)
class MemoryHandler:
    components: RuntimeComponents

    def add_memory(self, payload: MemoryCreate) -> dict:
        return memory_service.add_memory(payload)

    def update_memory(self, memory_id: str, payload: MemoryUpdate) -> dict:
        return memory_service.update_memory(memory_id, payload)

    def list_memories(self, user_id: str | None = None, agent_id: str | None = None, memory_type: str | None = None, limit: int = 100) -> list[dict]:
        return memory_service.list_memories(user_id=user_id, agent_id=agent_id, memory_type=memory_type, limit=limit)

    def search_memory(self, query: str, top_k: int = 5, **filters) -> dict:
        return memory_service.search_memory(query, top_k, **filters)

    def add_evidence(self, memory_id: str, payload: MemoryEvidenceCreate) -> dict:
        return memory_service.add_memory_evidence(memory_id, payload)

    def list_lifecycle_events(self, memory_id: str, limit: int = 50) -> list[dict]:
        return memory_service.list_memory_lifecycle_events(memory_id, limit)

    def create_candidate(self, payload: ReaderItem, created_by: str | None = None) -> dict:
        return memory_service.create_memory_candidate_from_reader(payload, created_by=created_by)

    def list_candidates(self, limit: int = 100, status: str | None = None, source_domain: str | None = None) -> list[dict]:
        return memory_service.list_memory_candidates(limit=limit, status=status, source_domain=source_domain)

    def promote_candidate(
        self,
        candidate_id: str,
        reviewed_by: str | None = None,
        trust_level: str = "verified",
        status_on_memory: str = "active",
    ) -> dict:
        return memory_service.promote_memory_candidate(
            candidate_id,
            reviewed_by=reviewed_by,
            trust_level=trust_level,
            status_on_memory=status_on_memory,
        )
