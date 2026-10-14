# Implementation status

Plan: [`docs/team/CHAITANYA.md`](team/CHAITANYA.md). This page tracks what is built and what the team still owns.

## Done

| Stage | Milestone | Status |
|---|---|---|
| 0 | Scaffold, ADR-001..009, CI, compose, Makefile | ✅ |
| 1 | proof-core SPEC + Python + TS + shared vectors | ✅ both implementations pass identical vectors |
| 2 | Schema + append-only triggers, auth/RBAC, `LedgeitAnchor.sol` + 7 tests | ✅ |
| 3 | AI inspector (stub + YOLO/EigenCAM code), edge simulator, ingest, hash chain | ✅ |
| 4 | Risk engine, anchor worker (Merkle batching, retries), replay detection, alert rules | ✅ real anchoring on Hardhat |
| 5 | Signed review/override/approval/dispute, 5-check verification, public verify, Tamper Lab | ✅ smart insider caught only by check 5 |
| 6 | Web dashboard (11 pages + public verify with in-browser chain check) | ✅ Playwright walkthrough clean |
| 7 | PDF reports + QR, economics, dashboard KPIs | ✅ |
| 8 | `make demo`, threat model, docs, rate limiting | ✅ |

Tests: proof-core py 10 · proof-core ts 6 · api 48 · ai 5 · contracts 7 · web 5. `make demo` asserts 14 outcomes end-to-end.

## Still to do (needs the team / resources this environment did not have)

- [ ] **Ishan** — Download NEU-DET, run `training/prepare_neu_det.py` + `training/train.py` (GPU/Colab), fill
      `MODEL_CARD.md` metrics, set `MODEL_BACKEND=yolo`. Validate EigenCAM layer choice on the trained net.
      Tune `replay.phash_max_distance` on real NEU images (similar textures may collide).
- [ ] **Chaitanya** — Fund an Amoy wallet from the faucet, `CHAIN=amoy AMOY_PRIVATE_KEY=… npm run deploy:amoy`,
      commit `contracts/deployments/amoy.json`, run the demo with `CHAIN=amoy`. Confirm `docker compose up` on a
      machine with Docker (compose files were written but not executed here). Branch protection + project board.
- [ ] **Aryan** — Record the demo video, take screenshots for the report, polish copy; deploy web (Vercel) +
      API (Render/Railway) if a live link is wanted.
- [ ] Everyone — weekly progress logs, tag `v1.0.0` after the Amoy run.

## Deviations from the original plan (all recorded as ADRs)
- Edge-first ingest (ADR-004), Postgres anchor queue instead of Redis/Celery (ADR-008), plain-SQL migrations (ADR-009).
- No `ANCHORED` chain event (would need anchoring itself); anchor state lives in batch tables (SPEC §7).
- ReportLab instead of WeasyPrint (no system dependencies).
- A deterministic classical-CV "stub" model + synthetic steel frames so the whole pipeline runs without the dataset or a GPU.
