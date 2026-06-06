# MCP Tool Inventory

This inventory groups important MCP tools by risk and operational purpose. It is not a complete API reference; use it for smoke testing and governance.

## Read-only diagnostics tools

- `gcd_diagnostics`
- `gcd_scheduler_status`

## Read/search tools

- `gcd_search_memories`
- `gcd_search_assets`

## High-risk write tools

- `gcd_add_memory`
- `gcd_propose_memory_feedback_actions`

## Read-only / low-risk

- `gcd_health`
- `gcd_diagnostics`
- `gcd_scheduler_status`
- `gcd_search_memories`
- `gcd_list_memories`
- `gcd_list_memory_versions`
- `gcd_list_memory_lifecycle_events`
- `gcd_list_memory_evidence`
- `gcd_list_memory_feedback`
- `gcd_list_memory_feedback_actions`
- `gcd_memory_quality_report`
- `gcd_list_memory_relations`
- `gcd_search_assets`
- `gcd_list_assets`
- `gcd_list_asset_versions`
- `gcd_list_asset_artifacts`
- `gcd_list_snapshots`
- `gcd_get_resume_context`

## Normal write

- `gcd_add_memory`
- `gcd_add_memory_evidence`
- `gcd_create_memory_candidate`
- `gcd_promote_memory_candidate`
- `gcd_memory_feedback`
- `gcd_add_memory_feedback_action`
- `gcd_propose_memory_feedback_actions`
- `gcd_create_memory_promotion`
- `gcd_add_asset`
- `gcd_register_asset_artifact`
- `gcd_register_asset_analysis_manifest`
- `gcd_create_cube`
- `gcd_bind_to_cube`
- `gcd_import_cube_snapshot`

## High-risk write / review carefully

These should be paired with audit review:

- `gcd_update_memory`
- `gcd_delete_memory`
- `gcd_apply_memory_feedback`
- `gcd_review_memory_promotion`
- `gcd_update_asset`
- `gcd_update_cube`
- `gcd_restore_snapshot`
- `memory_restore_snapshot`

Expected audit overlay for high-risk MCP writes:

```text
action = mcp.high_risk_write
target_type = mcp_tool
```

## Scheduler / governance operations

- `gcd_scheduler_claim_next`
- `gcd_scheduler_run_pending`
- `gcd_scheduler_release_expired`
- `gcd_scheduler_status`
- `gcd_enqueue_memory_quality_improvements`
- `gcd_enqueue_memory_hygiene`
- `gcd_build_memory_relation_index`

## Snapshot / portability

- `gcd_export_snapshot`
- `gcd_list_snapshots`
- `gcd_restore_snapshot`
- `gcd_export_cube_snapshot`
- `gcd_import_cube_snapshot`

Restore operations are high impact and must not be run casually on NAS production data.
