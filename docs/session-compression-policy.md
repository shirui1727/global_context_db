# Session Compression Policy

Session capture is for recovery, not raw transcript hoarding. The goal is to make interrupted agent work resumable without leaking secrets.

## Keep

- session metadata;
- important user decisions;
- task state;
- tool trace summaries;
- handoff summaries;
- selected raw events when explicitly requested.

## Avoid

- plaintext API keys;
- tokens;
- passwords;
- authorization headers;
- unnecessary full logs;
- huge raw event dumps in default resume context.

## Resume context defaults

- Prefer structured handoff.
- Use `context_budget_chars`.
- Keep `include_raw_events=false` by default.
- Include warnings when query/context is too weak.

## Compression workflow

1. Preserve raw event in session storage if needed.
2. Add summary/handoff after meaningful milestones.
3. Use resume context to recover next actions.
4. Review trace redaction before sharing support snapshots.
