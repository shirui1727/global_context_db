from pathlib import Path

import pytest

from app.assets.service import (
    AssetPermissionError,
    create_asset,
    file_reference_create,
    file_reference_list,
    file_reference_update,
    fresh_install_preflight,
    register_asset_artifact,
    rebuild_asset_vectors,
    run_asset_scan,
    register_asset_analysis_manifest,
    search_assets,
)
from app.core.config import settings
from app.core.schemas import (
    AssetArtifactCreate,
    AssetCreate,
    AssetAnalysisArtifact,
    AssetAnalysisManifest,
    AssetObservedItem,
    AssetScanRunCreate,
    AssetSearchRequest,
    FileReferenceCreate,
    FileReferenceUpdate,
    ImproveRequest,
)
from app.improvements.service import list_improvement_tasks, run_improve
from app.storage.bootstrap import bootstrap, reset_bootstrap
from app.storage.vector_store import list_items, upsert_items


@pytest.fixture()
def asset_env(tmp_path: Path):
    original = {
        "data_dir": settings.data_dir,
        "sqlite_path": settings.sqlite_path,
        "lancedb_dir": settings.lancedb_dir,
        "asset_allow_prefixes": settings.asset_allow_prefixes,
        "asset_deny_prefixes": settings.asset_deny_prefixes,
    }
    settings.data_dir = tmp_path / "data"
    settings.sqlite_path = settings.data_dir / "gcd.sqlite3"
    settings.lancedb_dir = settings.data_dir / "lancedb"
    settings.asset_allow_prefixes = ""
    settings.asset_deny_prefixes = ""
    reset_bootstrap()
    bootstrap(settings)
    yield
    for key, value in original.items():
        setattr(settings, key, value)
    reset_bootstrap()


def test_asset_key_move_and_version_stales_artifact(asset_env):
    first = create_asset(
        AssetCreate(
            uri="smb://NAS/photos/a.jpg",
            asset_key="photo:a",
            checksum="sha-a",
            title="Photo A",
            summary="first version",
            asset_kind="photo",
            trust_level="verified",
        )
    )
    artifact = register_asset_artifact(
        first["id"],
        AssetArtifactCreate(artifact_kind="thumbnail", artifact_uri="/data/artifacts/a.jpg", status="ready"),
    )
    moved = create_asset(
        AssetCreate(
            uri="smb://NAS/photos/moved/a.jpg",
            asset_key="photo:a",
            checksum="sha-a",
            title="Photo A moved",
            asset_kind="photo",
            trust_level="verified",
        )
    )
    assert moved["id"] == first["id"]
    assert len(moved["locations"]) == 2
    assert len(moved["versions"]) == 1

    changed = create_asset(
        AssetCreate(
            uri="smb://NAS/photos/moved/a.jpg",
            asset_key="photo:a",
            checksum="sha-b",
            title="Photo A v2",
            asset_kind="photo",
            trust_level="verified",
        )
    )
    assert changed["version_changed"] is True
    assert changed["status"] == "stale"
    assert changed["analysis_status"] == "needs_reindex"
    assert len(changed["versions"]) == 2
    assert changed["artifacts"][0]["id"] == artifact["id"]
    assert changed["artifacts"][0]["status"] == "stale"


def test_scan_marks_missing_and_recovers(asset_env):
    asset = create_asset(
        AssetCreate(uri="smb://NAS/photos/a.jpg", asset_key="photo:a", checksum="sha-a", asset_kind="photo")
    )
    run_asset_scan(
        AssetScanRunCreate(
            scope_prefix="smb://NAS/photos",
            mark_missing=True,
            observed=[
                AssetObservedItem(uri="smb://NAS/photos/other.jpg", asset_key="photo:other", checksum="sha-other")
            ],
        )
    )
    search = search_assets(AssetSearchRequest(query="Photo", top_k=10, status=["missing", "active", "stale"]))
    missing = [item for item in search["results"] if item["id"] == asset["id"]]
    assert missing == []

    recovered = create_asset(
        AssetCreate(uri="smb://NAS/photos/a.jpg", asset_key="photo:a", checksum="sha-a", asset_kind="photo")
    )
    assert recovered["locations"][0]["location_status"] == "active"


def test_deny_prefix_blocks_write(asset_env):
    settings.asset_deny_prefixes = "smb://NAS/private"
    with pytest.raises(AssetPermissionError):
        create_asset(AssetCreate(uri="smb://NAS/private/a.jpg", asset_key="secret:a"))


def test_file_reference_compat_and_rebuild_cleans_legacy_vectors(asset_env):
    created = file_reference_create(
        FileReferenceCreate(
            uri="smb://NAS/photos/compat.jpg",
            asset_key="photo:compat",
            checksum="sha-compat",
            title="Compat Photo",
            asset_kind="photo",
            summary="compatibility path",
        )
    )
    rows = file_reference_list()
    assert rows[0]["id"] == created["file_reference_id"]
    assert rows[0]["asset_key"] == "photo:compat"
    updated = file_reference_update(
        created["file_reference_id"],
        FileReferenceUpdate(summary="updated through alias", tags=["alias"]),
    )
    assert updated["file_reference"]["summary"] == "updated through alias"
    assert updated["file_reference"]["tags"] == ["alias"]

    upsert_items(
        [
            {
                "id": "legacy-vector",
                "kind": "file_reference",
                "text": "old vector",
                "vector": [0.0] * 64,
                "context_domain": "asset",
            }
        ]
    )
    assert len(list_items("file_reference")) == 1
    result = rebuild_asset_vectors(clean_legacy=True)
    assert result["after"]["legacy_file_reference_vectors"] == 0
    assert result["after"]["asset_vectors"] >= 1


def test_asset_analysis_manifest_registers_artifacts_and_indexes_text(asset_env):
    asset = create_asset(
        AssetCreate(
            uri="smb://NAS/videos/demo.mp4",
            asset_key="video:demo",
            checksum="sha-demo",
            asset_kind="video",
            media_type="video/mp4",
            summary="raw demo video",
        )
    )
    result = register_asset_analysis_manifest(
        asset["id"],
        AssetAnalysisManifest(
            generated_by="pytest-worker",
            analysis_status="indexed",
            artifacts=[
                AssetAnalysisArtifact(
                    artifact_kind="asr_text",
                    artifact_uri="/data/artifacts/demo.asr.txt",
                    media_type="text/plain",
                    text="speaker explains lobster tool setup and NAS memory workflow",
                    status="ready",
                    metadata={"language": "en"},
                ),
                AssetAnalysisArtifact(
                    artifact_kind="keyframe",
                    artifact_uri="/data/artifacts/demo-001.jpg",
                    media_type="image/jpeg",
                    status="ready",
                    metadata={"timestamp_sec": 12.5},
                ),
            ],
            summary="Demo video about Lobster tool setup and NAS memory workflow.",
            tags=["video-analysis"],
        ),
    )
    search = search_assets(AssetSearchRequest(query="lobster memory workflow", top_k=5))

    assert result["asset"]["analysis_status"] == "indexed"
    assert len(result["artifacts"]) == 2
    assert any(item["id"] == asset["id"] for item in search["results"])


def test_fresh_install_preflight(asset_env):
    preflight = fresh_install_preflight()
    assert preflight["mode"] == "fresh_v0_2"
    assert preflight["asset_tables_ready"] is True
    assert preflight["recommended_first_write"] == "POST /assets"


def test_failed_analysis_manifest_queues_followup_tasks(asset_env):
    asset = create_asset(
        AssetCreate(
            uri="smb://NAS/videos/failure.mp4",
            asset_key="video:failure",
            checksum="sha-failure",
            asset_kind="video",
            media_type="video/mp4",
        )
    )

    result = register_asset_analysis_manifest(
        asset["id"],
        AssetAnalysisManifest(
            generated_by="pytest-worker",
            analysis_status="failed",
            artifacts=[
                AssetAnalysisArtifact(
                    artifact_kind="asr_text",
                    artifact_uri="/data/artifacts/failure.asr.txt",
                    media_type="text/plain",
                    text="partial transcript",
                    status="failed",
                )
            ],
            metadata={"failure_reason": "worker timeout"},
        ),
    )
    tasks = list_improvement_tasks(target_domain="asset", target_id=asset["id"])
    task_kinds = {task["task_kind"] for task in tasks}

    assert result["asset"]["analysis_status"] == "failed"
    assert "refresh_asset_artifacts" in task_kinds
    assert "reindex_asset" in task_kinds


def test_improve_reindex_asset_updates_analysis_status(asset_env):
    asset = create_asset(
        AssetCreate(
            uri="smb://NAS/photos/reindex.jpg",
            asset_key="photo:reindex",
            checksum="sha-old",
            asset_kind="photo",
            title="Reindex Photo",
        )
    )
    changed = create_asset(
        AssetCreate(
            uri="smb://NAS/photos/reindex.jpg",
            asset_key="photo:reindex",
            checksum="sha-new",
            asset_kind="photo",
            title="Reindex Photo v2",
        )
    )

    improved = run_improve(
        ImproveRequest(
            task_kind="reindex_asset",
            target_domain="asset",
            target_id=asset["id"],
            execute=True,
            created_by="tester",
        )
    )

    assert changed["analysis_status"] == "needs_reindex"
    assert improved["ok"] is True
    assert improved["task"]["status"] == "done"
    assert improved["result"]["asset"]["id"] == asset["id"]
    assert improved["result"]["asset"]["analysis_status"] == "indexed"
