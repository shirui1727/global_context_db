from app.core.config import Settings
from app.storage.repo import init_sqlite
from app.storage.vector_store import init_vector_store


def bootstrap(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.lancedb_dir.mkdir(parents=True, exist_ok=True)
    init_sqlite(settings.sqlite_path)
    init_vector_store(settings.lancedb_dir)

