# Architecture Decision Records

| ADR | Decision | Status |
|---|---|---|
| [001](ADR-001-tech-stack.md) | Tech stack: Option A (FastAPI + React) | Accepted |
| [002](ADR-002-chain-choice.md) | Public chain: Polygon Amoy (+ local Hardhat) | Accepted |
| [003](ADR-003-record-signer.md) | Edge device signs the inspection record | Accepted |
| [004](ADR-004-ingest-mode.md) | Edge-first ingest (device runs inference, posts sealed record) | Accepted |
| [005](ADR-005-human-key-custody.md) | Human keys in browser IndexedDB, append-only key history | Accepted |
| [006](ADR-006-dataset.md) | Dataset: NEU-DET | Accepted |
| [007](ADR-007-batch-sizes.md) | Batch sizes/timeouts in `config/risk.yaml` | Accepted |
| [008](ADR-008-anchor-queue.md) | Durable anchor queue in PostgreSQL instead of Redis | Accepted |
| [009](ADR-009-migrations.md) | Plain-SQL numbered migrations | Accepted |

Template: Context → Decision → Consequences.
