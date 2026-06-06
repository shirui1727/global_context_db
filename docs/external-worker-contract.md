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
