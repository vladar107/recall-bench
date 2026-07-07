---
name: claudescope-history
description: Query the user's AI-coding-agent transcript history (Claude Code, Codex, Junie, pi, opencode, Copilot, Antigravity) with the claudescope CLI — full-text search, session reading, project listings, token/cost analytics. Use whenever a question concerns past sessions, previous errors and fixes, decisions made earlier, or historical usage/cost.
---

# Querying agent history with the claudescope CLI

Claudescope indexes every coding-agent transcript on this machine and answers
queries through read-only CLI subcommands. The background server starts
automatically on first use. All commands support `--json` for machine-readable
output; without it they print human-readable tables/Markdown.

## Commands

Full-text search (BM25) across all transcripts and agent memory:

    claudescope search "<query>" [--project <id>] [--role user|assistant] [--scope sessions|memory|all] [--limit N] [--json]

Hits include a sessionId and a messageUuid — open a hit in context with
`claudescope session <sessionId> --around <messageUuid>`.

List sessions (most recent first by default):

    claudescope sessions [--project <id>] [--agent claude-code|codex|junie|pi|opencode|copilot|antigravity] [--sort recent|oldest|tokens|cost|messages] [--q <title-substring>] [--limit N] [--json]

Read one session as compact Markdown — sessions can be huge, so this returns a
WINDOW of turns (default: the first 20) plus the total count:

    claudescope session <id> [--offset N] [--limit N] [--around <uuid>] [--radius N] [--max-tool-chars N] [--json]

Page forward with `--offset`; anchor on a search hit with `--around <uuid>`.
Tool payloads are truncated (default 2000 chars); raise with --max-tool-chars.

List projects (one per working directory, with sessions/tokens/cost/agents):

    claudescope projects [--json]

Token/cost aggregates (local list-price estimate), grouped and date-bounded:

    claudescope analytics [--group-by project|model|day|agent] [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--json]

## Typical flows

- "Where did I hit this error before?" → `search`, then `session <id> --around <uuid>`.
- "What did we decide about X?" → `search` with topic terms, read the hit windows.
- "How much did project P cost in a date range?" → `analytics --group-by project --from … --to …`.
- "Which sessions touched X in project P?" → `sessions --project P` and/or `search --project P`.

Date bounds are inclusive; dates are YYYY-MM-DD. Project ids come from
`claudescope projects`. Cost figures are list-price estimates, not billing.
