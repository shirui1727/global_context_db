# Asset Artifact Policy

Global Context DB registers assets and derived artifacts; it does not ingest original NAS libraries into the database.

## Storage rules

- Original NAS files remain in their source library.
- Small derived artifacts may live under `data/artifacts`.
- Large derived artifacts may live in NAS and be referenced by URI.
- Every artifact should have a stable `artifact_type`, URI, status, and metadata.

## Recommended artifact types

- `probe_metadata`
- `thumbnail`
- `keyframe`
- `ocr_text`
- `asr_text`
- `scene_summary`
- `embedding_text`
- `embedding_visual`

## Snapshot behavior

- Artifacts under `data/artifacts` are part of GCD backup/snapshot scope.
- External NAS artifact URIs are references only and must remain available outside GCD.

## Safety

- Respect asset allow/deny prefixes.
- Do not let the core service invoke heavy OCR/ASR/ffmpeg work.
- External workers produce manifests; GCD registers and governs them.
