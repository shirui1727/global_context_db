from app.assets.service import file_reference_create, file_reference_list, file_reference_update
from app.core.schemas import FileReferenceCreate, FileReferenceUpdate


def add_file_reference(payload: FileReferenceCreate) -> dict:
    return file_reference_create(payload)


def update_file_reference(file_reference_id: str, payload: FileReferenceUpdate) -> dict:
    return file_reference_update(file_reference_id, payload)


def list_file_references(
    limit: int = 100,
    status: str | None = None,
    media_type: str | None = None,
    asset_kind: str | None = None,
    trust_level: str | None = None,
) -> list[dict]:
    return file_reference_list(
        limit,
        status=status,
        media_type=media_type,
        asset_kind=asset_kind,
        trust_level=trust_level,
    )
