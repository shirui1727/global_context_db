# Asset hardening v0.2

v0.2 turns file references into governed assets. The old `/file-references`
REST endpoints and `gcd_*file_reference*` MCP tools remain compatible, but new
work should use the canonical asset APIs.

## Identity

Asset identity is resolved in this order:

1. `asset_key`: `sha256("asset_key:" + normalized_asset_key)`
2. `checksum`: `sha256("checksum:" + checksum)`
3. `uri`: `sha256("uri:" + normalized_uri)`

The service does not read NAS files to calculate checksums. Callers or scan
manifests provide checksums when content identity matters.

## Tables

- `assets`: logical asset metadata and lifecycle state.
- `asset_locations`: physical or external URIs for the asset.
- `asset_versions`: content versions, keyed by checksum or URI signature.
- `asset_artifacts`: registered derived artifacts such as thumbnails, OCR, ASR,
  keyframes, scene summaries, and embeddings.
- `asset_scan_runs`: manifest-based rescan records.

## Statuses

- Asset: `draft`, `active`, `stale`, `missing`, `deprecated`, `archived`
- Location: `active`, `missing`, `moved`, `forbidden`
- Version: `current`, `superseded`, `stale`, `failed`
- Artifact: `pending`, `ready`, `stale`, `failed`, `skipped`
- Analysis: `pending`, `indexed`, `needs_reindex`, `failed`, `skipped`
- Trust: `unverified`, `verified`, `trusted`

## Permission policy

Use URI prefix controls:

```text
GCD_ASSET_ALLOW_PREFIXES=smb://NAS/documents,smb://NAS/photos,smb://NAS/videos
GCD_ASSET_DENY_PREFIXES=smb://NAS/private,smb://NAS/secrets
```

Deny prefixes win. If allow prefixes are empty, the policy is open for backward
compatibility and `/diagnostics` reports `permission_policy.mode = open`.

## Canonical REST

```text
POST /assets
GET /assets
GET /assets/{asset_id}
PATCH /assets/{asset_id}
POST /assets/search
POST /assets/scan-runs
GET /assets/scan-runs/{scan_run_id}
GET /assets/{asset_id}/versions
GET /assets/{asset_id}/locations
POST /assets/{asset_id}/artifacts
GET /assets/{asset_id}/artifacts
PATCH /asset-artifacts/{artifact_id}
```

`POST /search` now returns grouped `memory`, `document`, and `asset` results by
default. Send `legacy_flat=true` to get the old flat result list.

For a fresh NAS deployment, start with:

```text
GET /assets/maintenance/fresh-install-preflight
POST /assets
POST /assets/search
```

The `/file-references` endpoints remain as aliases for clients that still use
the old names, but new clients should use `/assets`.

If you have local test data or a previous package that wrote legacy vector rows,
run:

```text
POST /assets/maintenance/rebuild-vectors?clean_legacy=true
```

or the MCP tool:

```text
gcd_rebuild_asset_vectors(clean_legacy=true)
```

This rebuilds canonical `kind=asset` vector rows and removes any
`kind=file_reference` vector rows left by local tests or earlier builds.

## Manifest scan

v0.2 does not crawl NAS directories directly. A scanner submits a manifest:

```json
{
  "scope_prefix": "smb://NAS/photos",
  "mark_missing": true,
  "observed": [
    {
      "uri": "smb://NAS/photos/a.jpg",
      "asset_key": "photo:a",
      "checksum": "sha256...",
      "media_type": "image/jpeg",
      "asset_kind": "photo"
    }
  ]
}
```

When checksum changes for the same asset, a new current version is created and
artifacts for old versions become `stale`.
