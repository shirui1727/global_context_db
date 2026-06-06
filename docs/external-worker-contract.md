# External Worker Contract

External workers do heavy file/media processing. Global Context DB remains the registry, governance, search, and audit service.

## Worker responsibilities

Workers may:

- read allowed NAS files;
- run ffprobe/ffmpeg;
- run OCR;
- run ASR;
- generate thumbnails/keyframes;
- generate scene summaries;
- write derived artifacts;
- POST scan or analysis manifests back to GCD.

Workers must not:

- mutate GCD SQLite directly;
- bypass REST/MCP;
- store API keys or secrets in trace fields;
- delete original NAS files;
- assume GCD owns original media.

## GCD responsibilities

GCD will:

- validate/register assets;
- store locations/versions/artifacts;
- audit important writes;
- index searchable text;
- expose diagnostics;
- keep heavy processing out of the core service.

## Manifest expectations

Recommended top-level fields:

```json
{
  "manifest_version": "1.0",
  "asset_id": "...",
  "artifacts": [],
  "metadata": {}
}
```

Older manifests without `manifest_version` should remain accepted until a migration plan exists.

## Manifest versions

Workers must write versioned payload metadata:

- Scan item: `metadata.manifest_version = asset-manifest/v1`
- Scan run: `metadata.manifest_version = asset-scan-run/v1`
- Analysis manifest: `payload.metadata.manifest_version = asset-analysis-manifest/v1`
- Worker contract: `external-worker/v1`

The schema reference is `docs/asset-manifest-schema.md`. Version fields are operational metadata; they do not authorize copying original NAS files into Global Context DB storage.
