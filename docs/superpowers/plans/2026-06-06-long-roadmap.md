# Global Context DB Long Roadmap

This roadmap is the long-running development direction after the completed MemOS maturity, runtime acceptance, and field acceptance phases.

The current baseline is `6e7e004 docs: add field acceptance first use plan`.

## Principles

- NAS-first: original large files stay in NAS; Global Context DB registers references, manifests, derived artifacts, governance, search, and audit.
- Diagnostics-first: prefer `/diagnostics`, `/scheduler/status`, bounded snapshots, and Markdown/JSON reports before adding dashboard dependencies.
- SQLite-first: keep the SQLite scheduler until real multi-worker pressure or queue-age evidence proves it insufficient.
- Human-review-first: feedback, hygiene, relation, and correction flows produce reviewable proposals before mutating durable memory.
- MCP/REST-first: clients use stable REST and MCP surfaces, not direct database access.
- Evidence-led escalation: Redis, dashboard/subgraph, LLM planner, and ACL require concrete operational evidence.

## Phase 1: NAS field operation

Goal: turn local release acceptance into real NAS evidence.

- Deploy the current package to NAS.
- Run REST smoke against NAS.
- Run MCP smoke from a real client.
- Run first-use workflow once.
- Capture diagnostics baseline.
- Fill NAS acceptance report.

## Phase 2: Ops diagnostics

Goal: make support snapshots comparable and actionable.

- Compare diagnostics snapshots.
- Score a diagnostics snapshot as green/yellow/red.
- Generate weekly operation reports.
- Keep reports bounded and free of raw secret material.

## Phase 3: First-use automation

Goal: make the first real workflow repeatable.

- Run a REST first-use smoke.
- Keep smoke data tagged.
- Avoid destructive cleanup by default.
- Treat explicit cleanup as high-risk and audited.

## Phase 4: Retrieval evaluation

Goal: know whether recall quality is improving or regressing.

- Expand retrieval fixture coverage across memory, document, asset, session, and cube scopes.
- Persist eval runs after the workflow stabilizes.
- Add release gates only after baseline quality is stable.

## Phase 5: Feedback governance

Goal: use real feedback samples to decide whether an LLM planner is justified.

- Track feedback proposal acceptance.
- Record deterministic planner failure modes.
- Require a real sample corpus before implementing LLM planning.

## Phase 6: Asset and media production

Goal: make external workers reliable while keeping heavy media processing outside GCD.

- Version manifests.
- Define external worker contracts.
- Expand media worker acceptance tests.
- Register artifacts without copying original NAS files into the database.

## Phase 7: Session recovery

Goal: make interrupted development sessions recoverable.

- Evaluate resume context quality.
- Report sessions without useful summaries.
- Preserve redaction guarantees for traces.

## Phase 8: Hygiene and relation governance

Goal: make lightweight relation and hygiene workflows usable before building graph UI.

- Report relation index health.
- Report memory hygiene candidates.
- Strengthen apply guardrails and audit.

## Phase 9: Client ecosystem

Goal: make Codex, OpenClaw, and future MCP clients easy to configure and smoke-test.

- Document client profiles.
- Export MCP tool inventory.
- Group tools by risk.

## Phase 10: Dashboard-before-dashboard

Goal: satisfy operations needs through scripts and reports before committing to a UI.

- Generate Markdown operation reports.
- Generate queue pressure reports.
- Require a dashboard trigger review before UI work.

## Heavy dependency trigger gates

Redis is not triggered until queue diagnostics show real multi-worker or remote concurrency pressure.

Dashboard/subgraph is not triggered until JSON/Markdown diagnostics are too slow for a real repeated triage workflow.

LLM planner is not triggered until deterministic feedback proposals fail on real samples with measurable review cost.

ACL/user manager is not triggered until real multi-user sharing needs access isolation.

## Immediate executable slice

The first executable slice after this roadmap is Ops Diagnostics Phase:

- release record for `6e7e004`
- diagnostics snapshot diff script
- diagnostics snapshot score script
- weekly operations report template
- first-use smoke script
- smoke data policy
- Codex MCP client profile
- OpenClaw MCP client profile
- MCP tool inventory

## Roadmap completion executable slice

This slice completes the current no-heavy-dependency roadmap pass by adding:

- retrieval eval fixture validation and reporting;
- feedback governance export/reporting;
- asset manifest schema versioning;
- session recovery reporting;
- memory hygiene/relation governance reporting;
- MCP client smoke hardening;
- release/package gates for the new artifacts.

Redis, dashboard/subgraph, LLM planner, and ACL remain untriggered until evidence records justify them.
