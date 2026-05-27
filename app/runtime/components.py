from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings, settings as default_settings
from app.storage.bootstrap import bootstrap


@dataclass(frozen=True)
class RuntimeComponents:
    settings: Settings
    sqlite_path: Path
    data_dir: Path
    lancedb_dir: Path


def get_runtime_components(settings: Settings = default_settings) -> RuntimeComponents:
    bootstrap(settings)
    return RuntimeComponents(
        settings=settings,
        sqlite_path=settings.sqlite_path,
        data_dir=settings.data_dir,
        lancedb_dir=settings.lancedb_dir,
    )
