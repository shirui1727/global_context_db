# First-use Workflow

This workflow exercises the first real loop after deployment: memory, asset reference, session trace, retrieval, feedback, scheduler diagnostics, and governance.

## Preconditions

- Release acceptance passed locally.
- REST smoke passed against the running service.
- MCP smoke read-only checks passed.
- Do not put original NAS files into the database. Register stable references and derived manifests only.

## 1. Create or rely on default cube routing

For ordinary use, callers can omit `cube_id`; the default cube resolver will route by project/session/agent/user context.

Expected evidence:

- New memories/assets/sessions have a `cube_id` when created through routed flows.
- Search metadata can report readable cube scope.

## 2. Write a project memory

REST or MCP example:

```text
gcd_add_memory(
  content="First-use workflow: this project uses Global Context DB as NAS-first shared memory.",
  tags=["first-use", "project"],
  agent_id="codex"
)
```

Expected evidence:

- Memory is created.
- `gcd_search_memories(query="NAS-first shared memory")` can retrieve it.

## 3. Register a NAS asset reference

Register only a reference/manifest. Do not copy the source file into GCD.

Example fields:

```text
uri = "smb://NAS/projects/example/brief.md"
title = "Example project brief"
tags = ["first-use", "asset"]
```

Expected evidence:

- Asset search returns the asset.
- The original file remains in the external NAS library.

## 4. Create a session and record events

Capture one agent session with at least:

- session start
- a user instruction summary
- one tool trace or decision note
- session end or handoff

Expected evidence:

- Resume context can include structured handoff.
- Trace fields do not store plaintext `token`, `api_key`, `password`, or `authorization`.

## 5. Recall/search across context

Run a search for terms that should hit the newly created memory and asset.

Expected evidence:

- Memory results stay in memory search.
- Asset results stay in asset search.
- `/search` grouped output keeps domains separated.

## 6. Create feedback and proposal

Create memory feedback for the first-use memory:

```text
gcd_memory_feedback(
  feedback_text="First-use feedback: add evidence that this service is NAS-first and uses diagnostics before heavy dependencies.",
  target_memory_id="<memory id>",
  created_by="codex"
)
```

Then run:

```text
gcd_propose_memory_feedback_actions(feedback_id="<feedback id>", planner="deterministic")
```

Expected evidence:

- Proposal uses `planner=deterministic`.
- Proposal returns reviewable action(s).
- Nothing is applied unless manually confirmed through apply.

## 7. Review diagnostics

Run:

```powershell
Invoke-RestMethod "http://NAS_IP:8000/diagnostics"
Invoke-RestMethod "http://NAS_IP:8000/scheduler/status"
```

Expected evidence:

- `governance.audit.high_risk_actions` includes `mcp.high_risk_write`.
- `governance.improvement.queue_health` exists.
- Scheduler status reports queue health and pending/failed counts.

## 8. Capture support snapshot

```powershell
powershell -ExecutionPolicy Bypass -File scripts\collect-diagnostics-snapshot.ps1 -BaseUrl http://NAS_IP:8000 -OutputDir .\diagnostics-snapshots
```

Expected evidence:

- `health.json`
- `diagnostics.json`
- `scheduler-status.json`
- `manifest.json`

The snapshot is bounded and redacts common secret fields.
