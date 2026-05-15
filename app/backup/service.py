import json
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import settings
from app.governance.service import diagnostics
from app.storage.bootstrap import bootstrap, reset_bootstrap
from app.storage.repo import sqlite_path


SNAPSHOT_MANIFEST = "manifest.json"


def snapshots_dir() -> Path:
    path = settings.data_dir / "snapshots"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _add_path(zip_file: zipfile.ZipFile, path: Path, arc_prefix: str) -> None:
    if not path.exists():
        return
    if path.is_file():
        zip_file.write(path, arc_prefix)
        return
    for child in path.rglob("*"):
        if child.is_file():
            zip_file.write(child, str(Path(arc_prefix) / child.relative_to(path)))


def export_snapshot(label: str | None = None) -> dict:
    bootstrap(settings)
    name = f"gcd_snapshot_{_utc_stamp()}"
    if label:
        safe_label = "".join(ch for ch in label if ch.isalnum() or ch in ("-", "_"))[:40]
        if safe_label:
            name = f"{name}_{safe_label}"
    snapshot_path = snapshots_dir() / f"{name}.zip"

    manifest = {
        "service": settings.service_name,
        "version": settings.service_version,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "sqlite_path": str(settings.sqlite_path),
        "lancedb_dir": str(settings.lancedb_dir),
        "artifacts_dir": str(settings.data_dir / "artifacts"),
        "diagnostics": diagnostics(),
    }

    with zipfile.ZipFile(snapshot_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr(SNAPSHOT_MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))
        _add_path(zip_file, sqlite_path(), "sqlite/gcd_v2.sqlite3")
        _add_path(zip_file, settings.lancedb_dir, "lancedb")
        _add_path(zip_file, settings.data_dir / "artifacts", "artifacts")

    return {
        "ok": True,
        "snapshot_path": str(snapshot_path),
        "size_bytes": snapshot_path.stat().st_size,
        "manifest": manifest,
    }


def list_snapshots(limit: int = 20) -> list[dict]:
    bootstrap(settings)
    rows = []
    for path in sorted(snapshots_dir().glob("*.zip"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
        rows.append(
            {
                "name": path.name,
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(timespec="seconds"),
            }
        )
    return rows


def _safe_clear_path(path: Path) -> None:
    if not path.exists():
        return
    data_root = settings.data_dir.resolve()
    target = path.resolve()
    if data_root not in target.parents and target != data_root:
        raise ValueError(f"refusing to clear path outside data dir: {target}")
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def restore_snapshot(snapshot_path: str) -> dict:
    source = Path(snapshot_path)
    if not source.exists() or source.suffix.lower() != ".zip":
        raise ValueError("snapshot zip not found")

    restore_root = settings.data_dir / "_restore_tmp"
    _safe_clear_path(restore_root)
    restore_root.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(source, "r") as zip_file:
        names = set(zip_file.namelist())
        if SNAPSHOT_MANIFEST not in names or "sqlite/gcd_v2.sqlite3" not in names:
            raise ValueError("invalid snapshot: missing manifest or sqlite database")
        zip_file.extractall(restore_root)

    sqlite_source = restore_root / "sqlite" / "gcd_v2.sqlite3"
    lancedb_source = restore_root / "lancedb"
    artifacts_source = restore_root / "artifacts"

    _safe_clear_path(settings.sqlite_path)
    settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sqlite_source, settings.sqlite_path)

    if lancedb_source.exists():
        _safe_clear_path(settings.lancedb_dir)
        shutil.copytree(lancedb_source, settings.lancedb_dir)

    artifacts_target = settings.data_dir / "artifacts"
    if artifacts_source.exists():
        _safe_clear_path(artifacts_target)
        shutil.copytree(artifacts_source, artifacts_target)

    _safe_clear_path(restore_root)
    reset_bootstrap()
    bootstrap(settings)
    return {
        "ok": True,
        "restored_from": str(source),
        "diagnostics": diagnostics(),
    }
