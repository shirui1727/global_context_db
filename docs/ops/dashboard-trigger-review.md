# Dashboard Trigger Review

Fill this before starting dashboard/subgraph UI work. A dashboard is not justified just because diagnostics has many fields.

## Proposed dashboard need

- Date:
- Operator:
- Incident or recurring workflow:
- Current evidence snapshot:

## Questions

1. Who will look at the dashboard?
2. How often will they look at it?
3. What decision will they make from it?
4. Which current JSON/Markdown report is too slow or insufficient?
5. Which fields must be visualized?
6. What action follows each visual state?

## Existing alternatives tried

- `/diagnostics`:
- `/scheduler/status`:
- `scripts/generate-ops-report.ps1`:
- `scripts/report-queue-pressure.ps1`:
- `memory_relations` REST/MCP:

## Decision

- Dashboard/subgraph triggered: yes / no
- Reason:
- Minimum viable dashboard scope if yes:

Do not proceed to UI work unless this review has concrete repeated triage evidence.
