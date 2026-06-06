# Asset Manifest Schema

Global Context DB registers asset references, scan results, and derived artifacts. It does not copy original NAS media into the database.

## Versions

| Payload | Version |
| --- | --- |
| Scan item metadata | `asset-manifest/v1` |
| Scan run metadata | `asset-scan-run/v1` |
| Analysis manifest metadata | `asset-analysis-manifest/v1` |
| Worker contract | `external-worker/v1` |

## Scan item

Required fields:

- `uri`: stable NAS or external URI.
- `asset_key`: deterministic key for upsert.
- `checksum`: SHA-256 of the observed file.
- `size_bytes`: file size.
- `modified_at`: file modified timestamp.
- `asset_kind`: `image`, `video`, `document`, or `generic_asset`.
- `metadata.manifest_version`: `asset-manifest/v1`.
- `metadata.worker_contract`: `external-worker/v1`.

## Scan run

Required fields:

- `scope_prefix`: scanned NAS scope.
- `mark_missing`: whether missing observed files should mark existing assets missing.
- `observed`: bounded list of scan items.
- `created_by`: worker identity.
- `metadata.manifest_version`: `asset-scan-run/v1`.
- `metadata.worker_contract`: `external-worker/v1`.

## Analysis manifest

Required fields:

- `asset_id`: registered asset id.
- `payload.analysis_status`: usually `indexed` after artifact registration.
- `payload.generated_by`: worker identity.
- `payload.artifacts`: derived artifacts such as `embedding_text`, `probe_metadata`, `ocr_text`, or `asr_text`.
- `payload.metadata.manifest_version`: `asset-analysis-manifest/v1`.
- `payload.metadata.worker_contract`: `external-worker/v1`.

## Artifact rule

Artifacts may include derived text, probe JSON, thumbnails, OCR, ASR, or keyframe references. Original NAS files remain external and must not be copied into `global_context_db/data` or the SQLite database.
