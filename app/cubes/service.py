from datetime import UTC, datetime
from hashlib import sha256
from pathlib import PurePosixPath

from app.core.schemas import ContextCubeBindingCreate, ContextCubeCreate, ContextCubeUpdate
from app.storage.repo import context_cubes_repo, cube_bindings_repo

CUBE_TYPES = {"user", "agent", "project", "session", "shared", "kb"}
VISIBILITIES = {"private", "shared", "public"}
CUBE_STATUSES = {"active", "archived"}
BINDING_KINDS = {"owns", "references", "derived_from"}
TARGET_DOMAINS = {"memory", "document", "asset", "session", "improvement"}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _validate(value: str, allowed: set[str], field: str) -> str:
    if value not in allowed:
        raise ValueError(f"{field} must be one of: {', '.join(sorted(allowed))}")
    return value


def create_cube(payload: ContextCubeCreate) -> dict:
    cube_type = _validate(payload.cube_type, CUBE_TYPES, "cube_type")
    visibility = _validate(payload.visibility, VISIBILITIES, "visibility")
    status = _validate(payload.status, CUBE_STATUSES, "status")
    now = _now()
    cube_id = payload.id or _hash(f"cube:{cube_type}:{payload.owner_id or ''}:{payload.name}")
    return context_cubes_repo().upsert(
        {
            "id": cube_id,
            "name": payload.name,
            "cube_type": cube_type,
            "owner_id": payload.owner_id,
            "visibility": visibility,
            "status": status,
            "created_by": payload.created_by,
            "created_at": now,
            "updated_at": now,
            "metadata": payload.metadata,
        }
    )


def resolve_default_cube(
    *,
    cube_id: str | None = None,
    session_id: str | None = None,
    project_path: str | None = None,
    agent_id: str | None = None,
    user_id: str | None = None,
    created_by: str | None = None,
) -> str | None:
    if cube_id:
        return cube_id
    if session_id:
        from app.storage.repo import agent_sessions_repo

        session = agent_sessions_repo().get(session_id)
        if session and session.get("cube_id"):
            return session["cube_id"]
        if session and session.get("project_path"):
            return _ensure_default_cube(
                cube_type="project",
                owner_id=_owner("project", session["project_path"]),
                name=_project_name(session["project_path"]),
                created_by=created_by or session.get("created_by") or session.get("source_agent"),
                metadata={"resolver": "session_project", "project_path": session["project_path"], "session_id": session_id},
            )
    if project_path:
        return _ensure_default_cube(
            cube_type="project",
            owner_id=_owner("project", project_path),
            name=_project_name(project_path),
            created_by=created_by or agent_id,
            metadata={"resolver": "project_path", "project_path": project_path},
        )
    if agent_id:
        return _ensure_default_cube(
            cube_type="agent",
            owner_id=_owner("agent", agent_id),
            name=f"Agent: {agent_id}",
            created_by=created_by or agent_id,
            metadata={"resolver": "agent_id", "agent_id": agent_id},
        )
    if user_id:
        return _ensure_default_cube(
            cube_type="user",
            owner_id=_owner("user", user_id),
            name=f"User: {user_id}",
            created_by=created_by or user_id,
            metadata={"resolver": "user_id", "user_id": user_id},
        )
    return None


def _ensure_default_cube(
    *,
    cube_type: str,
    owner_id: str,
    name: str,
    created_by: str | None,
    metadata: dict,
) -> str:
    cube_id = _hash(f"cube:{cube_type}:{owner_id}:{name}")
    existing = context_cubes_repo().get(cube_id)
    if existing:
        return cube_id
    create_cube(
        ContextCubeCreate(
            id=cube_id,
            name=name,
            cube_type=cube_type,
            owner_id=owner_id,
            visibility="private",
            created_by=created_by,
            metadata={**metadata, "auto_resolved": True},
        )
    )
    return cube_id


def _owner(kind: str, value: str) -> str:
    return f"{kind}:{value.strip().replace(chr(92), '/')}"


def _project_name(project_path: str) -> str:
    normalized = project_path.strip().replace("\\", "/").rstrip("/")
    if not normalized:
        return "Project: unknown"
    return f"Project: {PurePosixPath(normalized).name or normalized}"


def get_cube(cube_id: str) -> dict:
    cube = context_cubes_repo().get(cube_id)
    if not cube:
        raise ValueError("context cube not found")
    return cube


def list_cubes(
    limit: int = 100,
    cube_type: str | None = None,
    owner_id: str | None = None,
    status: str | None = None,
) -> list[dict]:
    return context_cubes_repo().list_recent(limit=limit, cube_type=cube_type, owner_id=owner_id, status=status)


def update_cube(cube_id: str, payload: ContextCubeUpdate) -> dict:
    current = get_cube(cube_id)
    changes = payload.model_dump(exclude_unset=True)
    cube_type = _validate(changes.get("cube_type") or current["cube_type"], CUBE_TYPES, "cube_type")
    visibility = _validate(changes.get("visibility") or current["visibility"], VISIBILITIES, "visibility")
    status = _validate(changes.get("status") or current["status"], CUBE_STATUSES, "status")
    return context_cubes_repo().upsert(
        {
            **current,
            **{key: value for key, value in changes.items() if value is not None and key != "metadata"},
            "cube_type": cube_type,
            "visibility": visibility,
            "status": status,
            "updated_at": _now(),
            "metadata": changes.get("metadata") if changes.get("metadata") is not None else current.get("metadata", {}),
        }
    )


def bind_to_cube(cube_id: str, payload: ContextCubeBindingCreate) -> dict:
    get_cube(cube_id)
    target_domain = _validate(payload.target_domain, TARGET_DOMAINS, "target_domain")
    binding_kind = _validate(payload.binding_kind, BINDING_KINDS, "binding_kind")
    binding_id = _hash(f"cube-binding:{cube_id}:{target_domain}:{payload.target_id}:{binding_kind}")
    return cube_bindings_repo().upsert(
        {
            "id": binding_id,
            "cube_id": cube_id,
            "target_domain": target_domain,
            "target_id": payload.target_id,
            "binding_kind": binding_kind,
            "created_at": _now(),
            "metadata": payload.metadata,
        }
    )


def list_cube_bindings(cube_id: str, limit: int = 100) -> list[dict]:
    get_cube(cube_id)
    return cube_bindings_repo().list_by_cube(cube_id, limit)
