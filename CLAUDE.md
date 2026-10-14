# CLAUDE.md — Rules for Claude Code in LEDGEIT

## Git
- Do not run git or gh commands unless the developer explicitly asks in that session.
  Default: PRINT the commands for the developer to run.
  - branch: `<name>/<type>/<short-desc>` (e.g. `ishan/feat/replay-detection`)
  - commit: Conventional Commits, e.g. `feat(ai): add pHash replay detection`
  - `git add` only the paths that were changed
- Never commit or create `.env`, private keys, dataset images or model weights.

## Project context
- Read `docs/team/CHAITANYA.md` for architecture, schemas and ownership; `docs/adr/` for decisions
  that override it (notably ADR-004 edge-first ingest and ADR-008 Postgres anchor queue).
- Integrity rules live in `packages/proof-core/SPEC.md`. Any hashing/canonicalization change
  must update SPEC.md AND `test-vectors/`, and both Python and TS implementations must pass.
- Proof tables are append-only. Never write UPDATE/DELETE against inspections, inspection_events,
  overrides, override_approvals, anchor_items, blockchain_txs, evidence, verifications, user_keys.
- Decimals in hashed payloads are strings with 4 decimals; timestamps are UTC ISO-8601 with ms + 'Z'.

## Ownership (stay inside your area unless asked)
- Chaitanya: apps/api (core), packages/proof-core, contracts, services/anchor-worker, infra
- Ishan: services/ai-inspector, services/edge-simulator, scripts/tamper-lab, risk + alerts
- Aryan: apps/web, apps/api reports/economics/dashboard

## Commands
- `make install` — create .venv, install Python packages + npm deps
- `make test` — all test suites (proof-core py+ts, api, ai, contracts, web)
- `make dev-start` (native) or `make up` (Docker), then `make seed`, `make demo` — see README

## Before finishing a task
- Run the module's tests and linter and show results.
- Update the module README if behavior changed.
- Print: (1) summary of changes, (2) the git commands to run, (3) suggested PR title + body.
