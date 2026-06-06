# Smoke Data Policy

Smoke data is allowed to remain in Global Context DB when it helps prove that REST/MCP/client flows worked. It must be easy to find, explain, and clean up through audited workflows.

## Required tags

Use at least one of:

- `smoke-test`
- `first-use-smoke`
- `mcp-smoke`

## Required metadata

Recommended:

```json
{
  "smoke_test": true,
  "created_by": "codex",
  "scenario": "first-use-smoke",
  "date": "YYYY-MM-DD"
}
```

## Cleanup

Do not delete smoke data by default. It documents acceptance evidence.

If cleanup is required:

- Prefer hygiene/review flows where possible.
- Record the reason.
- Treat `gcd_delete_memory` and REST `DELETE /memories/{id}` as high-risk writes.
- Confirm audit entries after cleanup.

## Search

Find smoke data with:

```text
smoke-test
first-use-smoke
mcp-smoke
```

## Release notes

When a release uses smoke data as evidence, record created IDs or search terms in the release or ops report.
