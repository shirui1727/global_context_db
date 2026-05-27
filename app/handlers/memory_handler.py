
from dataclasses import dataclass

from app.core.schemas import MemoryCreate, MemoryEvidenceCreate, MemoryUpdate
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
