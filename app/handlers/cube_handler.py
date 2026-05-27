from dataclasses import dataclass

from app.core.schemas import ContextCubeBindingCreate, ContextCubeCreate, ContextCubeUpdate
from app.cubes import service as cube_service
from app.runtime.components import RuntimeComponents


@dataclass(frozen=True)
class CubeHandler:
    components: RuntimeComponents

    def create_cube(self, payload: ContextCubeCreate) -> dict:
        return cube_service.create_cube(payload)

    def list_cubes(self, limit: int = 100, cube_type: str | None = None, owner_id: str | None = None, status: str | None = None) -> list[dict]:
        return cube_service.list_cubes(limit=limit, cube_type=cube_type, owner_id=owner_id, status=status)

    def get_cube(self, cube_id: str) -> dict:
        return cube_service.get_cube(cube_id)

    def update_cube(self, cube_id: str, payload: ContextCubeUpdate) -> dict:
        return cube_service.update_cube(cube_id, payload)

    def bind_to_cube(self, cube_id: str, payload: ContextCubeBindingCreate) -> dict:
        return cube_service.bind_to_cube(cube_id, payload)

    def list_bindings(self, cube_id: str, limit: int = 100) -> list[dict]:
        return cube_service.list_cube_bindings(cube_id, limit)
