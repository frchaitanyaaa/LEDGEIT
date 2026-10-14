# ADR-001: Tech stack — Option A "Python Core"

**Status:** Accepted · 2026-10-14

## Context
Three options were compared in `docs/team/CHAITANYA.md` §3 (A: FastAPI + React, B: NestJS + Next.js, C: Spring Boot + Hyperledger Fabric). The weighted matrix scored A 50/55, B 42, C 27.

## Decision
Option A:
- Backend: FastAPI (Python 3.11+), SQLAlchemy 2 Core, Pydantic v2.
- AI: Ultralytics YOLOv8 + EigenCAM, `imagehash` for pHash. A deterministic `stub` backend exists so the system runs without weights.
- Frontend: React 18 + Vite + TypeScript + Tailwind + TanStack Query + Recharts.
- Chain: Solidity + Hardhat, accessed from Python via web3.py.
- Crypto: `hashlib`, `rfc8785`, PyNaCl (Python); `@noble/hashes`, `@noble/ed25519` (TypeScript).
- Reports: ReportLab + `qrcode` (pure Python, no system deps — chosen over WeasyPrint for easy Docker/CI).

## Consequences
- AI, API, worker and simulator share one language and one `proof-core` package.
- The browser verifier needs a TS port of `proof-core`; shared test vectors keep the two in lock-step.
- Option C is named in the report as the production roadmap for private deployments.
