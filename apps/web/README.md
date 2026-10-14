# web — LEDGEIT dashboard

React 18 + Vite + TypeScript + Tailwind + TanStack Query + Recharts.

```bash
npm ci --prefix ../../packages/proof-core/ts && npm ci
npm run dev          # http://localhost:5173 (proxies /api to :8000, incl. the WebSocket feed)
npx vitest run       # unit tests (in-browser verifier, key store, components)
npm run build
```

| Route | Page | Roles |
|---|---|---|
| `/` | Executive dashboard | all |
| `/feed` | Live feed (WebSocket) | all |
| `/inspections`, `/inspections/:id` | List + detail: evidence/boxes/heatmap, sealed record, timeline, verify, **signed review/override/approval/dispute** | all (actions by role) |
| `/overrides` | Override center (approve/reject, signed) | QE, QM, Auditor, Admin |
| `/explorer` | Blockchain explorer (batches, leaves, txs) | all |
| `/verification` | Verification center (bulk verify + history) | all |
| `/risk` | Risk & tampering (alerts) | QE, QM, Auditor, Admin |
| `/models` | Model registry (approve/retire) | all (actions QM/Admin) |
| `/reports` | Compliance reports (PDF + QR) | QM, Auditor, Admin |
| `/economics` | Fees, cost per inspection, batching savings | QM, Auditor, Admin |
| `/integrations` | Devices, line chains, roadmap | QM, Admin |
| `/verify/:code` | **Public** verification (no login) with an independent in-browser check against the chain | public |

Signing: on first login the browser creates an Ed25519 key in IndexedDB (`src/lib/keys.ts`) and registers the
public key. Every human action signs `SHA256(JCS(payload))` using the shared `packages/proof-core/ts`.
