from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from app.core.config import settings
from app.core.schemas import (
    AssetAnalysisManifest,
    AssetArtifactCreate,
    AssetArtifactUpdate,
    AssetCreate,
    AssetScanRunCreate,
    AssetSearchRequest,
    AssetUpdate,
    ImprovementTaskCreate,
    FileReferenceCreate,
    FileReferenceUpdate,
)
from app.improvements.service import create_improvement_task
from app.reader.service import read_asset_manifest_fast
from app.retrieval.embedding import embed_text
from app.storage.repo import (
    asset_artifacts_repo,
    asset_locations_repo,
    asset_scan_runs_repo,
    asset_versions_repo,
    assets_repo,
    audit_logs_repo,
)
from app.storage.vector_store import delete_item, delete_items_by_kind, list_items, search_items, upsert_items

ASSET_STATUSES = {"draft", "active", "stale", "missing", "deprecated", "archived"}
LOCATION_STATUSES = {"active", "missing", "moved", "forbidden"}
VERSION_STATUSES = {"current", "superseded", "stale", "failed"}
ARTIFACT_STATUSES = {"pending", "ready", "stale", "failed", "skipped"}
TRUST_LEVELS = {"unverified", "verified", "trusted"}
ANALYSIS_STATUSES = {"pending", "indexed", "needs_reindex", "failed", "skipped"}
ARTIFACT_KINDS = {
    "thumbnail",
    "keyframe",
    "ocr_text",
    "asr_text",
    "scene_summary",
    "embedding_text",
    "embedding_visual",
    "probe_metadata",
}


class AssetPermissionError(ValueError):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _normalize_uri(uri: str) -> str:
    return uri.strip().replace("\\", "/")


def _normalize_asset_key(asset_key: str) -> str:
    return asset_key.strip().lower()


def _prefixes(value: str) -> list[str]:
    return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]


def permission_policy() -> dict[str, Any]:
    allow = _prefixes(settings.asset_allow_prefixes)
    deny = _prefixes(settings.asset_deny_prefixes)
    return {
        "mode": "restricted" if allow else "open",
        "allow_prefixes": allow,
        "deny_prefixes": deny,
    }


def _is_data_artifact_uri(uri: str) -> bool:
    normalized = _normalize_uri(uri)
    artifact_dir = _normalize_uri(str(settings.data_dir / "artifacts"))
    return normalized.startswith("/data/artifacts") or normalized.startswith(artifact_dir)


def _check_uri_allowed(uri: str, actor: str | None = None) -> None:
    normalized = _normalize_uri(uri)
    allow = _prefixes(settings.asset_allow_prefixes)
    deny = _prefixes(settings.asset_deny_prefixes)
    if any(normalized.startswith(prefix) for prefix in deny):
        _audit("asset.forbidden", _hash(f"forbidden:{normalized}"), actor or "unknown", {"uri": uri, "reason": "deny_prefix"})
        raise AssetPermissionError("asset uri is denied by GCD_ASSET_DENY_PREFIXES")
    if allow and not _is_data_artifact_uri(normalized) and not any(normalized.startswith(prefix) for prefix in allow):
        _audit("asset.forbidden", _hash(f"forbidden:{normalized}"), actor or "unknown", {"uri": uri, "reason": "not_allowed"})
        raise AssetPermissionError("asset uri is not allowed by GCD_ASSET_ALLOW_PREFIXES")


def _audit(action: str, target_id: str, actor: str, metadata: dict | None = None) -> None:
    now = _now()
    payload = metadata or {}
    audit_logs_repo().insert(
        {
            "id": _hash(f"{now}:{actor}:{action}:{target_id}:{payload}"),
            "actor": actor,
            "action": action,
            "target_type": "asset",
            "target_id": target_id,
            "created_at": now,
            "metadata": payload,
        }
    )


def _queue_improvement(task_kind: str, asset_id: str, reason: str, actor: str, metadata: dict | None = None) -> None:
    create_improvement_task(
        ImprovementTaskCreate(
            task_kind=task_kind,
            target_domain="asset",
            target_id=asset_id,
            priority=25 if task_kind in {"reindex_asset", "resolve_missing_asset"} else 50,
            reason=reason,
            created_by=actor,
            metadata=metadata or {},
        )
    )


def _validate(value: str, allowed: set[str], field: str) -> str:
    if value not in allowed:
        raise ValueError(f"{field} must be one of: {', '.join(sorted(allowed))}")
    return value


class AssetIdentityResolver:
    @staticmethod
    def resolve(uri: str, asset_key: str | None = None, checksum: str | None = None) -> dict:
        normalized_uri = _normalize_uri(uri)
        if not normalized_uri:
            raise ValueError("uri is required")
        if asset_key:
            normalized_key = _normalize_asset_key(asset_key)
            return {
                "asset_id": _hash(f"asset_key:{normalized_key}"),
                "asset_key": normalized_key,
                "identity_source": "asset_key",
                "uri_normalized": normalized_uri,
            }
        if checksum:
            normalized_checksum = checksum.strip().lower()
            return {
                "asset_id": _hash(f"checksum:{normalized_checksum}"),
                "asset_key": normalized_checksum,
                "identity_source": "checksum",
                "uri_normalized": normalized_uri,
            }
        return {
            "asset_id": _hash(f"uri:{normalized_uri.lower()}"),
            "asset_key": _hash(f"uri:{normalized_uri.lower()}"),
            "identity_source": "uri",
            "uri_normalized": normalized_uri,
        }


def _search_text(asset: dict, location: dict | None = None, version: dict | None = None) -> str:
    parts = [
        asset.get("title") or "",
        asset.get("summary") or "",
        asset.get("asset_kind") or "",
        asset.get("asset_key") or "",
        asset.get("media_type") or "",
        " ".join(asset.get("tags") or []),
        location.get("uri") if location else "",
        version.get("checksum") if version else "",
    ]
    return "\n".join(str(part) for part in parts if part)


def _upsert_asset_vector(asset_id: str) -> None:
    asset = assets_repo().get(asset_id)
    if not asset:
        delete_item(asset_id)
        return
    locations = asset_locations_repo().list_by_asset(asset_id)
    versions = asset_versions_repo().list_by_asset(asset_id)
    current_version = next((version for version in versions if version.get("is_current")), None)
    primary_location = locations[0] if locations else None
    if asset["status"] == "archived":
        delete_item(asset_id)
        return
    reader_item = read_asset_manifest_fast(
        asset_id=asset_id,
        asset_key=asset.get("asset_key"),
        summary=asset.get("summary") or "",
        uri=primary_location.get("uri") if primary_location else None,
        cube_id=asset.get("cube_id"),
        tags=asset.get("tags", []),
        title=asset.get("title"),
        asset_kind=asset.get("asset_kind"),
        media_type=asset.get("media_type"),
        metadata={"analysis_status": asset.get("analysis_status")},
    )
    text = reader_item.content or _search_text(asset, primary_location, current_version)
    if not text.strip():
        delete_item(asset_id)
        return
    upsert_items(
        [
            {
                "id": asset_id,
                "kind": "asset",
                "text": reader_item.content,
                "vector": embed_text(reader_item.content).tolist(),
                "cube_id": asset.get("cube_id"),
                "source": primary_location.get("uri") if primary_location else "",
                "doc_id": asset_id,
                "chunk_index": 0,
                "tags": reader_item.tags,
                "context_domain": "asset",
                "status": asset.get("status"),
                "source_kind": asset.get("source_kind"),
                "trust_level": asset.get("trust_level"),
                "asset_id": asset_id,
                "version_id": current_version.get("id") if current_version else "",
                "artifact_id": "",
                "analysis_status": asset.get("analysis_status"),
                "metadata": {
                    "domain": "asset",
                    "cube_id": asset.get("cube_id"),
                    "asset_id": asset_id,
                    "asset_key": asset.get("asset_key"),
                    "asset_kind": asset.get("asset_kind"),
                    "media_type": asset.get("media_type"),
                    "analysis_status": asset.get("analysis_status"),
                    "version_id": current_version.get("id") if current_version else None,
                    "location_status": primary_location.get("location_status") if primary_location else None,
                    "reader": {
                        "source_domain": reader_item.source_domain,
                        "source_id": reader_item.source_id,
                        "content_kind": reader_item.content_kind,
                        "provenance": reader_item.provenance,
                    },
                },
            }
        ]
    )


def _upsert_artifact_text_vector(asset: dict, artifact: dict, text: str) -> None:
    if not text.strip():
        return
    reader_item = read_asset_manifest_fast(
        asset_id=asset["id"],
        asset_key=asset.get("asset_key"),
        summary=asset.get("summary") or "",
        uri=artifact.get("artifact_uri"),
        cube_id=asset.get("cube_id"),
        tags=asset.get("tags", []),
        title=asset.get("title"),
        asset_kind=asset.get("asset_kind"),
        media_type=asset.get("media_type"),
        artifact_text=text,
        artifact_id=artifact["id"],
        metadata={"artifact_kind": artifact.get("artifact_kind")},
    )
    vector_id = _hash(f"artifact-vector:{artifact['id']}")
    upsert_items(
        [
            {
                "id": vector_id,
                "kind": "asset_artifact",
                "text": reader_item.content,
                "vector": embed_text(reader_item.content).tolist(),
                "cube_id": asset.get("cube_id"),
                "source": artifact.get("artifact_uri") or "",
                "doc_id": asset["id"],
                "chunk_index": 0,
                "tags": asset.get("tags", []),
                "context_domain": "asset",
                "status": asset.get("status"),
                "source_kind": asset.get("source_kind"),
                "trust_level": asset.get("trust_level"),
                "asset_id": asset["id"],
                "version_id": artifact.get("version_id") or "",
                "artifact_id": artifact["id"],
                "analysis_status": asset.get("analysis_status"),
                "metadata": {
                    "domain": "asset",
                    "cube_id": asset.get("cube_id"),
                    "asset_id": asset["id"],
                    "asset_key": asset.get("asset_key"),
                    "asset_kind": asset.get("asset_kind"),
                    "artifact_id": artifact["id"],
                    "artifact_kind": artifact.get("artifact_kind"),
                    "artifact_uri": artifact.get("artifact_uri"),
                    "reader": {
                        "source_domain": reader_item.source_domain,
                        "source_id": reader_item.source_id,
                        "content_kind": reader_item.content_kind,
                        "provenance": reader_item.provenance,
                    },
                },
            }
        ]
    )


def _version_signature(asset_id: str, checksum: str | None, uri_normalized: str) -> str:
    return (checksum.strip().lower() if checksum else f"uri:{uri_normalized.lower()}")


def _ensure_version(payload: AssetCreate, asset_id: str, uri_normalized: str, now: str) -> tuple[dict, bool]:
    signature = _version_signature(asset_id, payload.checksum, uri_normalized)
    version_id = _hash(f"version:{asset_id}:{signature}")
    current = asset_versions_repo().get_current(asset_id)
    changed = current is not None and current.get("id") != version_id
    if changed:
        asset_versions_repo().supersede_current(asset_id)
        asset_artifacts_repo().stale_for_old_versions(asset_id, version_id, now)
    row = {
        "id": version_id,
        "asset_id": asset_id,
        "version_group_id": payload.version_group_id or payload.asset_key or payload.checksum or asset_id,
        "checksum": payload.checksum,
        "size_bytes": payload.size_bytes,
        "modified_at": payload.modified_at,
        "content_signature": signature,
        "version_status": "current",
        "is_current": True,
        "created_at": now,
        "metadata": payload.metadata,
    }
    asset_versions_repo().upsert(row)
    return row, changed


def create_asset(payload: AssetCreate) -> dict:
    actor = payload.created_by or payload.source_kind or "asset_writer"
    _check_uri_allowed(payload.uri, actor)
    _validate(payload.status, ASSET_STATUSES, "status")
    _validate(payload.trust_level, TRUST_LEVELS, "trust_level")
    _validate(payload.analysis_status, ANALYSIS_STATUSES, "analysis_status")
    if payload.storage_mode != "referenced":
        raise ValueError("v0.2 only supports storage_mode='referenced'")

    now = _now()
    identity = AssetIdentityResolver.resolve(payload.uri, payload.asset_key, payload.checksum)
    asset_id = identity["asset_id"]
    existing = assets_repo().get(asset_id)
    trust_level = "unverified" if identity["identity_source"] == "uri" else payload.trust_level
    if existing and existing.get("trust_level") in {"verified", "trusted"} and trust_level == "unverified":
        trust_level = existing["trust_level"]

    title = payload.title or identity["uri_normalized"].rsplit("/", 1)[-1]
    version, version_changed = _ensure_version(payload, asset_id, identity["uri_normalized"], now)
    status = "stale" if version_changed else payload.status
    analysis_status = "needs_reindex" if version_changed else payload.analysis_status
    assets_repo().upsert(
        {
            "id": asset_id,
            "cube_id": payload.cube_id,
            "asset_key": identity["asset_key"],
            "asset_kind": payload.asset_kind or "generic_asset",
            "title": title,
            "summary": payload.summary,
            "tags": payload.tags,
            "media_type": payload.media_type,
            "status": status,
            "trust_level": trust_level,
            "source_kind": payload.source_kind,
            "analysis_status": analysis_status,
            "created_by": actor,
            "updated_by": actor,
            "confirmed_by": payload.confirmed_by,
            "created_at": existing.get("created_at") if existing else now,
            "updated_at": now,
            "metadata": {**payload.metadata, "identity_source": identity["identity_source"]},
        }
    )
    location_id = _hash(f"location:{identity['uri_normalized'].lower()}")
    asset_locations_repo().upsert(
        {
            "id": location_id,
            "asset_id": asset_id,
            "uri": payload.uri.strip(),
            "uri_normalized": identity["uri_normalized"],
            "storage_mode": payload.storage_mode,
            "location_status": "active",
            "last_seen_at": now,
            "missing_since": None,
            "forbidden_since": None,
            "created_at": now,
            "updated_at": now,
            "metadata": {},
        }
    )
    _upsert_asset_vector(asset_id)
    _audit(
        "asset.updated" if existing else "asset.created",
        asset_id,
        actor,
        {
            "uri": payload.uri,
            "asset_key": identity["asset_key"],
            "identity_source": identity["identity_source"],
            "version_id": version["id"],
            "version_changed": version_changed,
        },
    )
    if version_changed:
        _queue_improvement("reindex_asset", asset_id, "asset version changed", actor, {"version_id": version["id"]})
        _queue_improvement("refresh_asset_artifacts", asset_id, "asset artifacts became stale after version change", actor, {"version_id": version["id"]})
    return get_asset(asset_id) | {"version_changed": version_changed}


def list_assets(limit: int = 100, status: str | None = None, asset_kind: str | None = None, trust_level: str | None = None) -> list[dict]:
    return [hydrate_asset(row["id"]) for row in assets_repo().list_recent(limit, status=status, asset_kind=asset_kind, trust_level=trust_level)]


def hydrate_asset(asset_id: str) -> dict:
    asset = assets_repo().get(asset_id)
    if not asset:
        raise ValueError("asset not found")
    asset["locations"] = asset_locations_repo().list_by_asset(asset_id)
    asset["versions"] = asset_versions_repo().list_by_asset(asset_id)
    asset["artifacts"] = asset_artifacts_repo().list_by_asset(asset_id)
    return asset


def get_asset(asset_id: str) -> dict:
    return hydrate_asset(asset_id)


def update_asset(asset_id: str, payload: AssetUpdate) -> dict:
    current = assets_repo().get(asset_id)
    if not current:
        raise ValueError("asset not found")
    changes = payload.model_dump(exclude_unset=True)
    status = changes.get("status") or current["status"]
    trust_level = changes.get("trust_level") or current["trust_level"]
    analysis_status = changes.get("analysis_status") or current.get("analysis_status", "indexed")
    _validate(status, ASSET_STATUSES, "status")
    _validate(trust_level, TRUST_LEVELS, "trust_level")
    _validate(analysis_status, ANALYSIS_STATUSES, "analysis_status")
    if current["trust_level"] in {"verified", "trusted"} and trust_level == "unverified":
        trust_level = current["trust_level"]
    now = _now()
    updated = {
        **current,
        **{key: value for key, value in changes.items() if value is not None and key != "metadata"},
        "status": status,
        "trust_level": trust_level,
        "analysis_status": analysis_status,
        "updated_at": now,
        "metadata": payload.metadata if payload.metadata is not None else current.get("metadata", {}),
    }
    assets_repo().upsert(updated)
    _upsert_asset_vector(asset_id)
    actor = payload.updated_by or updated.get("source_kind") or "asset_writer"
    _audit("asset.status_changed" if status in {"deprecated", "archived"} else "asset.updated", asset_id, actor, {"changed_fields": sorted(changes)})
    return hydrate_asset(asset_id)


def register_asset_artifact(asset_id: str, payload: AssetArtifactCreate) -> dict:
    asset = assets_repo().get(asset_id)
    if not asset:
        raise ValueError("asset not found")
    _validate(payload.status, ARTIFACT_STATUSES, "artifact.status")
    _validate(payload.artifact_kind, ARTIFACT_KINDS, "artifact_kind")
    _check_uri_allowed(payload.artifact_uri, payload.generated_by)
    now = _now()
    version_id = payload.version_id or (asset_versions_repo().get_current(asset_id) or {}).get("id")
    artifact_id = _hash(f"artifact:{asset_id}:{version_id or ''}:{payload.artifact_kind}:{_normalize_uri(payload.artifact_uri).lower()}")
    row = {
        "id": artifact_id,
        "asset_id": asset_id,
        "version_id": version_id,
        "artifact_kind": payload.artifact_kind,
        "artifact_uri": payload.artifact_uri,
        "media_type": payload.media_type,
        "checksum": payload.checksum,
        "status": payload.status,
        "generated_by": payload.generated_by,
        "created_at": now,
        "updated_at": now,
        "metadata": payload.metadata,
    }
    asset_artifacts_repo().upsert(row)
    _audit("asset_artifact.registered", asset_id, payload.generated_by or "artifact_writer", {"artifact_id": artifact_id, "artifact_kind": payload.artifact_kind})
    return asset_artifacts_repo().get(artifact_id)


def register_asset_analysis_manifest(asset_id: str, payload: AssetAnalysisManifest) -> dict:
    asset = assets_repo().get(asset_id)
    if not asset:
        raise ValueError("asset not found")
    _validate(payload.analysis_status, ANALYSIS_STATUSES, "analysis_status")
    current = asset_versions_repo().get_current(asset_id)
    version_id = payload.version_id or (current or {}).get("id")
    registered = []
    for item in payload.artifacts:
        artifact = register_asset_artifact(
            asset_id,
            AssetArtifactCreate(
                version_id=version_id,
                artifact_kind=item.artifact_kind,
                artifact_uri=item.artifact_uri,
                media_type=item.media_type,
                checksum=item.checksum,
                status=item.status,
                generated_by=payload.generated_by,
                metadata={**item.metadata, "text_preview": item.text[:500] if item.text else ""},
            ),
        )
        if item.text:
            _upsert_artifact_text_vector(asset, artifact, item.text)
        registered.append(artifact)
    merged_tags = list(dict.fromkeys([*(asset.get("tags") or []), *payload.tags]))
    updated_asset = update_asset(
        asset_id,
        AssetUpdate(
            summary=payload.summary if payload.summary is not None else asset.get("summary", ""),
            tags=merged_tags,
            analysis_status=payload.analysis_status,
            updated_by=payload.generated_by or "asset_analysis",
            metadata={
                **asset.get("metadata", {}),
                **payload.metadata,
                "last_analysis_manifest": {
                    "generated_by": payload.generated_by,
                    "artifact_count": len(registered),
                    "version_id": version_id,
                },
            },
        ),
    )
    _audit(
        "asset_analysis.registered",
        asset_id,
        payload.generated_by or "asset_analysis",
        {"artifact_count": len(registered), "version_id": version_id},
    )
    if payload.analysis_status in {"failed", "needs_reindex"}:
        _queue_improvement(
            "reindex_asset",
            asset_id,
            f"analysis manifest status is {payload.analysis_status}",
            payload.generated_by or "asset_analysis",
            {"version_id": version_id, "analysis_status": payload.analysis_status},
        )
    if payload.analysis_status == "failed" or any(item.get("status") in {"failed", "stale", "pending"} for item in registered):
        _queue_improvement(
            "refresh_asset_artifacts",
            asset_id,
            "analysis manifest reported failed or stale artifacts",
            payload.generated_by or "asset_analysis",
            {"version_id": version_id, "artifact_count": len(registered)},
        )
    return {"asset": updated_asset, "artifacts": registered}


def list_asset_artifacts(asset_id: str) -> list[dict]:
    if not assets_repo().get(asset_id):
        raise ValueError("asset not found")
    return asset_artifacts_repo().list_by_asset(asset_id)


def update_asset_artifact(artifact_id: str, payload: AssetArtifactUpdate) -> dict:
    current = asset_artifacts_repo().get(artifact_id)
    if not current:
        raise ValueError("artifact not found")
    changes = payload.model_dump(exclude_unset=True)
    status = changes.get("status", current["status"])
    _validate(status, ARTIFACT_STATUSES, "artifact.status")
    artifact_uri = changes.get("artifact_uri", current.get("artifact_uri"))
    if artifact_uri:
        _check_uri_allowed(artifact_uri, payload.generated_by)
    now = _now()
    updated = {
        **current,
        **{key: value for key, value in changes.items() if value is not None and key != "metadata"},
        "status": status,
        "updated_at": now,
        "metadata": payload.metadata if payload.metadata is not None else current.get("metadata", {}),
    }
    asset_artifacts_repo().upsert(updated)
    _audit("asset_artifact.updated", updated["asset_id"], payload.generated_by or "artifact_writer", {"artifact_id": artifact_id, "changed_fields": sorted(changes)})
    if status in {"stale", "failed", "pending"}:
        _queue_improvement(
            "refresh_asset_artifacts",
            updated["asset_id"],
            f"artifact status is {status}",
            payload.generated_by or "artifact_writer",
            {"artifact_id": artifact_id},
        )
    return asset_artifacts_repo().get(artifact_id)


def run_asset_scan(payload: AssetScanRunCreate) -> dict:
    actor = payload.created_by or "asset_scan"
    _check_uri_allowed(payload.scope_prefix, actor)
    started = _now()
    observed_uris: set[str] = set()
    created_assets = []
    errors = []
    for item in payload.observed:
        try:
            observed_uris.add(_normalize_uri(item.uri))
            created_assets.append(
                create_asset(
                    AssetCreate(
                        uri=item.uri,
                        asset_key=item.asset_key,
                        checksum=item.checksum,
                        size_bytes=item.size_bytes,
                        modified_at=item.modified_at,
                        media_type=item.media_type,
                        asset_kind=item.asset_kind,
                        title=item.title,
                        summary=item.summary,
                        tags=item.tags,
                        trust_level=item.trust_level,
                        source_kind="asset_scan",
                        created_by=actor,
                        metadata=item.metadata,
                    )
                )["id"]
            )
        except ValueError as error:
            errors.append({"uri": item.uri, "error": str(error)})
    missing_marked = 0
    if payload.mark_missing:
        scoped_locations = asset_locations_repo().list_by_scope(_normalize_uri(payload.scope_prefix))
        affected_asset_ids = {
            location["asset_id"]
            for location in scoped_locations
            if location["uri_normalized"] not in observed_uris
        }
        missing_marked = asset_locations_repo().mark_missing_not_observed(_normalize_uri(payload.scope_prefix), observed_uris, _now())
        for asset_id in affected_asset_ids:
            locations = asset_locations_repo().list_by_asset(asset_id)
            if locations and not any(location["location_status"] == "active" for location in locations):
                asset = assets_repo().get(asset_id)
                if asset and asset.get("status") not in {"archived", "deprecated"}:
                    assets_repo().upsert(
                        {
                            **asset,
                            "status": "missing",
                            "analysis_status": "needs_reindex",
                            "updated_by": actor,
                            "updated_at": _now(),
                        }
                    )
                    _queue_improvement(
                        "resolve_missing_asset",
                        asset_id,
                        "asset location missing after manifest scan",
                        actor,
                        {"scope_prefix": payload.scope_prefix},
                    )
            _upsert_asset_vector(asset_id)
    finished = _now()
    scan_id = _hash(f"scan:{payload.scope_prefix}:{started}:{len(payload.observed)}")
    row = {
        "id": scan_id,
        "scope_prefix": payload.scope_prefix,
        "status": "completed_with_errors" if errors else "completed",
        "observed_count": len(payload.observed),
        "created_by": actor,
        "started_at": started,
        "finished_at": finished,
        "metadata": {
            **payload.metadata,
            "asset_ids": sorted(set(created_assets)),
            "missing_marked": missing_marked,
            "errors": errors,
        },
    }
    asset_scan_runs_repo().upsert(row)
    _audit("asset_scan.completed", scan_id, actor, row["metadata"])
    return asset_scan_runs_repo().get(scan_id)


def get_asset_scan_run(scan_run_id: str) -> dict:
    row = asset_scan_runs_repo().get(scan_run_id)
    if not row:
        raise ValueError("scan run not found")
    return row


def search_assets(payload: AssetSearchRequest) -> dict:
    cube_ids = payload.cube_ids or ([payload.cube_id] if payload.cube_id else None)
    results = search_items(
        payload.query,
        max(payload.top_k * 5, payload.top_k),
        kind="asset",
        context_domain="asset",
        cube_ids=cube_ids,
    )
    allowed_status = set(payload.status or ["active", "stale"])
    cleaned = []
    for row in results:
        asset_id = row.get("id")
        asset = assets_repo().get(asset_id)
        if not asset or asset.get("status") not in allowed_status:
            continue
        if payload.asset_kind and asset.get("asset_kind") != payload.asset_kind:
            continue
        if payload.trust_level and asset.get("trust_level") != payload.trust_level:
            continue
        locations = asset_locations_repo().list_by_asset(asset_id)
        if locations and not any(location.get("location_status") == "active" for location in locations):
            continue
        score = _rank(row, asset)
        cleaned.append({**asset, "score": score, "locations": locations[:3]})
    cleaned.sort(key=lambda item: item["score"], reverse=True)
    return {"query": payload.query, "mode": "asset_search", "results": cleaned[: payload.top_k]}


def rebuild_asset_vectors(clean_legacy: bool = True) -> dict:
    before = {
        "asset_vectors": len(list_items("asset")),
        "legacy_file_reference_vectors": len(list_items("file_reference")),
    }
    delete_items_by_kind("asset")
    if clean_legacy:
        delete_items_by_kind("file_reference")
    rebuilt = 0
    skipped = 0
    for asset in assets_repo().list_recent(limit=100000):
        try:
            _upsert_asset_vector(asset["id"])
            rebuilt += 1
        except ValueError:
            skipped += 1
    after = {
        "asset_vectors": len(list_items("asset")),
        "legacy_file_reference_vectors": len(list_items("file_reference")),
    }
    _audit("asset_vectors.rebuilt", "asset_vectors", "maintenance", {"before": before, "after": after, "rebuilt": rebuilt, "skipped": skipped})
    return {
        "ok": True,
        "clean_legacy": clean_legacy,
        "rebuilt": rebuilt,
        "skipped": skipped,
        "before": before,
        "after": after,
    }


def asset_maintenance_preflight() -> dict:
    legacy_vectors = len(list_items("file_reference"))
    asset_vectors = len(list_items("asset"))
    assets = assets_repo().list_recent(limit=100000)
    status_counts: dict[str, int] = {}
    for asset in assets:
        status_counts[asset["status"]] = status_counts.get(asset["status"], 0) + 1
    return {
        "ok": True,
        "permission_policy": permission_policy(),
        "asset_count": len(assets),
        "asset_status_counts": status_counts,
        "asset_vectors": asset_vectors,
        "legacy_file_reference_vectors": legacy_vectors,
        "needs_rebuild": legacy_vectors > 0 or asset_vectors < len([asset for asset in assets if asset["status"] != "archived"]),
        "recommended_after_upgrade": "POST /assets/maintenance/rebuild-vectors?clean_legacy=true",
    }


def fresh_install_preflight() -> dict:
    assets = assets_repo().list_recent(limit=10)
    legacy_vectors = len(list_items("file_reference"))
    return {
        "ok": True,
        "mode": "fresh_v0_2",
        "asset_tables_ready": True,
        "permission_policy": permission_policy(),
        "has_existing_assets": bool(assets),
        "legacy_file_reference_vectors": legacy_vectors,
        "recommended_first_write": "POST /assets",
        "recommended_search": "POST /assets/search",
        "notes": [
            "Use canonical asset IDs returned by POST /assets.",
            "The /file-references endpoints are aliases for clients that still call the old names.",
            "Run rebuild-vectors only if diagnostics or preflight reports legacy vectors.",
        ],
    }


def execute_reindex_asset(asset_id: str, actor: str = "maintenance") -> dict:
    asset = assets_repo().get(asset_id)
    if not asset:
        raise ValueError("asset not found")
    updated = update_asset(
        asset_id,
        AssetUpdate(
            analysis_status="indexed",
            status="active" if asset.get("status") in {"stale", "missing"} else asset.get("status"),
            updated_by=actor,
            metadata={
                **(asset.get("metadata") or {}),
                "last_reindex_by": actor,
                "last_reindex_at": _now(),
            },
        ),
    )
    _upsert_asset_vector(asset_id)
    _audit("asset.reindexed", asset_id, actor, {"analysis_status": "indexed"})
    return {"asset": updated}


def _rank(row: dict, asset: dict) -> float:
    distance_score = float(1.0 / (1.0 + max(row.get("_distance", 0.0), 0.0)))
    status_weight = {"active": 1.0, "stale": 0.75, "draft": 0.45, "missing": 0.2, "deprecated": 0.1, "archived": 0.0}.get(asset.get("status"), 0.2)
    trust_weight = {"trusted": 1.0, "verified": 0.85, "unverified": 0.55}.get(asset.get("trust_level"), 0.55)
    return (status_weight * 0.4) + (trust_weight * 0.25) + (distance_score * 0.35)


def file_reference_create(payload: FileReferenceCreate) -> dict:
    asset = create_asset(
        AssetCreate(
            uri=payload.uri,
            title=payload.title,
            summary=payload.summary,
            tags=payload.tags,
            media_type=payload.media_type,
            asset_kind=payload.asset_kind or "generic_asset",
            asset_key=payload.asset_key,
            checksum=payload.checksum,
            size_bytes=payload.size_bytes,
            storage_mode=payload.storage_mode,
            status=payload.status,
            trust_level=payload.trust_level,
            source_kind=payload.source_kind,
            analysis_status=payload.analysis_status,
            version_group_id=payload.version_group_id,
            created_by=payload.source_kind,
            metadata=payload.metadata,
        )
    )
    version = next((item for item in asset["versions"] if item.get("is_current")), None)
    return {
        "file_reference_id": asset["id"],
        "storage_mode": "referenced",
        "uri": payload.uri,
        "asset_key": asset.get("asset_key"),
        "version_group_id": version.get("version_group_id") if version else asset.get("asset_key"),
        "status": asset.get("status"),
        "analysis_status": asset.get("analysis_status"),
    }


def file_reference_list(
    limit: int = 100,
    status: str | None = None,
    media_type: str | None = None,
    asset_kind: str | None = None,
    trust_level: str | None = None,
) -> list[dict]:
    rows = list_assets(limit, status=status, asset_kind=asset_kind, trust_level=trust_level)
    result = []
    for asset in rows:
        if media_type and asset.get("media_type") != media_type:
            continue
        location = asset["locations"][0] if asset["locations"] else {}
        version = next((item for item in asset["versions"] if item.get("is_current")), None) or (asset["versions"][0] if asset["versions"] else {})
        result.append(
            {
                "id": asset["id"],
                "uri": location.get("uri"),
                "title": asset.get("title"),
                "media_type": asset.get("media_type"),
                "asset_kind": asset.get("asset_kind"),
                "asset_key": asset.get("asset_key"),
                "size_bytes": version.get("size_bytes"),
                "checksum": version.get("checksum"),
                "summary": asset.get("summary"),
                "tags": asset.get("tags", []),
                "storage_mode": location.get("storage_mode", "referenced"),
                "context_domain": "asset",
                "status": asset.get("status"),
                "source_kind": asset.get("source_kind"),
                "trust_level": asset.get("trust_level"),
                "version_group_id": version.get("version_group_id"),
                "analysis_status": asset.get("analysis_status"),
                "last_seen_at": location.get("last_seen_at"),
                "missing_since": location.get("missing_since"),
                "content_changed_at": version.get("modified_at"),
                "derived_artifacts": {item["artifact_kind"]: item for item in asset.get("artifacts", [])},
                "metadata": asset.get("metadata", {}),
                "created_at": asset.get("created_at"),
                "updated_at": asset.get("updated_at"),
            }
        )
    return result


def _project_file_reference(asset: dict) -> dict:
    location = asset["locations"][0] if asset["locations"] else {}
    version = next((item for item in asset["versions"] if item.get("is_current")), None) or (asset["versions"][0] if asset["versions"] else {})
    return {
        "id": asset["id"],
        "uri": location.get("uri"),
        "title": asset.get("title"),
        "media_type": asset.get("media_type"),
        "asset_kind": asset.get("asset_kind"),
        "asset_key": asset.get("asset_key"),
        "size_bytes": version.get("size_bytes"),
        "checksum": version.get("checksum"),
        "summary": asset.get("summary"),
        "tags": asset.get("tags", []),
        "storage_mode": location.get("storage_mode", "referenced"),
        "context_domain": "asset",
        "status": asset.get("status"),
        "source_kind": asset.get("source_kind"),
        "trust_level": asset.get("trust_level"),
        "version_group_id": version.get("version_group_id"),
        "analysis_status": asset.get("analysis_status"),
        "last_seen_at": location.get("last_seen_at"),
        "missing_since": location.get("missing_since"),
        "content_changed_at": version.get("modified_at"),
        "derived_artifacts": {item["artifact_kind"]: item for item in asset.get("artifacts", [])},
        "metadata": asset.get("metadata", {}),
        "created_at": asset.get("created_at"),
        "updated_at": asset.get("updated_at"),
    }


def file_reference_update(file_reference_id: str, payload: FileReferenceUpdate) -> dict:
    asset = assets_repo().get(file_reference_id)
    if not asset:
        raise ValueError("file reference not found")
    updated = update_asset(
        file_reference_id,
        AssetUpdate(
            title=payload.title,
            summary=payload.summary,
            tags=payload.tags,
            media_type=payload.media_type,
            asset_kind=payload.asset_kind,
            status=payload.status,
            trust_level=payload.trust_level,
            source_kind=payload.source_kind,
            analysis_status=payload.analysis_status,
            metadata=payload.metadata,
        ),
    )
    if payload.derived_artifacts:
        for kind, artifact in payload.derived_artifacts.items():
            artifact_uri = artifact.get("uri") or artifact.get("artifact_uri") if isinstance(artifact, dict) else None
            if artifact_uri:
                register_asset_artifact(
                    file_reference_id,
                    AssetArtifactCreate(
                        artifact_kind=kind,
                        artifact_uri=artifact_uri,
                        status=artifact.get("status", "ready") if isinstance(artifact, dict) else "ready",
                        metadata=artifact if isinstance(artifact, dict) else {},
                    ),
                )
    return {"file_reference_id": file_reference_id, "file_reference": _project_file_reference(updated)}
