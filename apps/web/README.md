# web — LEDGEIT dashboard

React 18 + Vite + TypeScript + Tailwind + TanStack Query + Recharts.

```bash
npm ci --prefix ../../packages/proof-core/ts && npm ci
npm run dev          # http://localhost:5173 (proxies /api to :8000, incl. the WebSocket feed)
npx vitest run       # unit tests (in-browser verifier, key store, components)
npm run build
npm run screenshots  # report/PPT screenshots → docs/screenshots/ (stack running + seeded; see below)
```

**Screenshots.** `scripts/screenshots.mjs` signs in as the demo roles and saves one full-page PNG per route to
`docs/screenshots/` (login, every dashboard page, an inspection detail, and the public verify page of the newest
report). Run `npx playwright install chromium` once, or set `BROWSER_CHANNEL=chrome` (or `msedge`) to use an installed
browser. Other env: `BASE_URL` (default `http://localhost:5173`), `LEDGEIT_PASSWORD`, `OUT_DIR`. Stream some
inspections and generate a report first so the pages have data.

**Single-screen workspace.** After login everything happens on one screen (`/`, no page scrolling, no tab switching):
a KPI bar on top, the **live line** (WebSocket) in the middle, a glance column (activity, alerts, anchoring) on the
right and a **dock** of tools at the bottom. Each tool opens as a bottom sheet over the live view; an inspection opens
as a second sheet on top of it (Esc / backdrop / ✕ closes the top-most one). State lives in the URL
(`/?panel=risk&inspection=<id>`), so links, refresh and the back button work. Old URLs (`/risk`, `/inspections/:id`, …)
redirect to the matching panel. Code: `pages/Workspace.tsx`, `components/Sheet.tsx`, `lib/workspace.ts`.

| Dock panel (`?panel=`) | Content | Roles |
|---|---|---|
| (main screen) | KPIs + live feed + overview | all |
| `inspections` / `?inspection=<id>` | List; detail: evidence/boxes/heatmap, sealed record, timeline, verify, **signed review/override/approval/dispute** | all (actions by role) |
| `overrides` | Override center (approve/reject, signed) | QE, QM, Auditor, Admin |
| `explorer` | Blockchain explorer (batches, leaves, txs) | all |
| `verification` | Verification center (bulk verify + history) | all |
| `risk` | Risk & tampering (alerts) | QE, QM, Auditor, Admin |
| `models` | Model registry (approve/retire) | all (actions QM/Admin) |
| `reports` | Compliance reports (PDF + QR) | QM, Auditor, Admin |
| `economics` | Fees, cost per inspection, batching savings | QM, Auditor, Admin |
| `integrations` | Devices, line chains, roadmap | QM, Admin |
| `analytics` | Full executive charts | all |
| `/verify/:code` | **Public** verification (no login) with an independent in-browser check against the chain | public |

Signing: on first login the browser creates an Ed25519 key in IndexedDB (`src/lib/keys.ts`) and registers the
public key. Every human action signs `SHA256(JCS(payload))` using the shared `packages/proof-core/ts`.
