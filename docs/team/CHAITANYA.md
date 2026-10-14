# LEDGEIT — MVP Development Plan

> **Owner of this doc:** Chaitanya Pagare (repo maintainer)
> **Team:** Ishan Shrivastava · Chaitanya Pagare · Aryan Kale
> **Faculty Guide:** Dr. Shraddha Phansalkar · **Group ID:** LYBCC51 · MIT-ADT University, Dept. of CSE
> **Repo:** https://github.com/frchaitanyaaa/LEDGEIT
> **Location:** `docs/team/CHAITANYA.md` · **Implementation status:** [`docs/STATUS.md`](../STATUS.md) (decisions that changed this plan are in `docs/adr/`)

---

## Table of Contents

1. [Where we are (project recap)](#1-where-we-are-project-recap)
2. [MVP scope — what we build vs. what we defer](#2-mvp-scope)
3. [Tech stack options (choose one)](#3-tech-stack-options)
4. [System architecture](#4-system-architecture)
5. [Core approach — how integrity actually works](#5-core-approach)
6. [Flow diagrams](#6-flow-diagrams)
7. [Database schema](#7-database-schema)
8. [ER diagram](#8-er-diagram)
9. [Canonical record format + smart contract](#9-canonical-record-format--smart-contract)
10. [API contract](#10-api-contract)
11. [Folder structure](#11-folder-structure)
12. [Work division — Ishan / Chaitanya / Aryan](#12-work-division)
13. [Sprint plan](#13-sprint-plan)
14. [Git workflow + exact commands (devs run these, NOT Claude Code)](#14-git-workflow)
15. [Rules for Claude Code sessions](#15-rules-for-claude-code-sessions)
16. ["Serious development" checklist](#16-serious-development-checklist)
17. [Final demo script](#17-final-demo-script)
18. [Open decisions](#18-open-decisions)

---

## 1. Where we are (project recap)

**Problem.** Factories let AI inspect every product, but the *record* of what the AI saw and decided is a normal database row. Anyone with DB access can change it later. This has already happened: Kobe Steel (falsified inspection data across 23 plants, 200+ customers), Mitsubishi Materials ("rewriting inspection records data"), Global Calcium (FDA 2024, fabricated batch records and deleted evidence) and Nidec (2026, 1,000+ alleged unauthorized changes).

**One-line pitch.** *A cryptographically verifiable chain of custody for every AI manufacturing decision.* We bind **Evidence + Model + Decision + Explanation + Human Response + Timestamp** into one tamper-evident record.

**The 6 stages (from the poster), mapped to software modules:**

| Stage | What it means | Module we build | Owner |
|---|---|---|---|
| 1. Detect | AI inspects the product image and gives a decision and a confidence score | `services/ai-inspector` + `services/edge-simulator` | Ishan |
| 2. Bind | Image hash, model version, explanation and confidence are sealed into one record | `packages/proof-core` + ingest API | Chaitanya |
| 3. Anchor | The record fingerprint goes on a public ledger. Routine records are batched (Merkle), critical ones go immediately | `services/anchor-worker` + `contracts/` + risk engine | Chaitanya (anchor), Ishan (risk rules) |
| 4. Respond | A human override (who, why, which evidence) is signed and sealed the same way | Override API + signing UI | Aryan (UI + API), Chaitanya (signing core) |
| 5. Verify | Anyone can re-check a record. One changed byte means a flagged mismatch | Verification engine + Verification Center + public verify page | Chaitanya (engine), Aryan (UI) |
| 6. Report | Audit-ready reports with a QR/verification code | Reports service + Compliance page | Aryan |

**Key positioning:** we are a **verification layer on top of existing AI inspection systems**, not a replacement camera system. For the MVP we simulate the factory side ourselves: an edge simulator streams real defect images through our own YOLO model.

**What "lost track" means in practice:** the repo has one commit containing only the 4 reference docs. No code, no structure, no decisions recorded yet. This doc fixes that.

---

## 2. MVP scope

### ✅ In the MVP (must work end-to-end in the demo)

| # | Feature | Why it matters for the demo |
|---|---|---|
| 1 | Edge simulator streams images, which go to AI inference (YOLO trained on the NEU steel-defect dataset) | Real AI and real images, not hardcoded JSON |
| 2 | Inspection Proof Record: canonical JSON, then SHA-256, then device Ed25519 signature | The "Bind" stage |
| 3 | Per-production-line **hash chain** of events (each event stores `prev_event_hash`) | Catches deletions and re-ordering |
| 4 | **Risk engine** (LOW / MEDIUM / HIGH) feeding a **Merkle batch** or **immediate anchor** | Risk-adaptive anchoring is our differentiator |
| 5 | Solidity anchor contract on a **local Hardhat node and the Polygon Amoy testnet** | Real public, tamper-evident ledger |
| 6 | Human **override** flow with reason, reviewed evidence and an Ed25519 signature in the browser | The "Respond" stage |
| 7 | **Verification engine** with 5 independent checks (evidence, model, signature, event chain, Merkle/chain) | The "Verify" stage, the core of the demo |
| 8 | **Replay detection** (exact SHA-256 + perceptual hash) | Shows we thought about real attacks |
| 9 | **Tamper Lab** scripts that edit the DB, swap an image or delete an event, after which verification FAILS | The "wow" moment |
| 10 | Dashboards: Executive, Live Feed, Inspection Detail + Timeline, Blockchain Explorer, Verification Center, Model Registry, Override Center, Risk & Tampering, Compliance Reports, Economics | 10 of the 12 pages from the platform doc |
| 11 | RBAC with 5 roles (Operator, Quality Engineer, Quality Manager, Auditor, Admin) | Access control section of the doc |
| 12 | PDF compliance report with a QR code that opens the public verify page | The "Report" stage |

### ⏸ Deferred (mention in the presentation as roadmap)

- Real MES/ERP/SCADA/PLC integrations. The **System Integrations** page shows only the edge simulator as "connected".
- Multi-plant tenancy, SSO, HSM-backed keys.
- Mainnet deployment, Kafka-scale ingestion, Kubernetes.
- Model drift detection with statistical tests. The MVP shows override rate and confidence trends per model version.

---

## 3. Tech stack options

All three options share the same **architecture, schemas, contract and crypto spec** (sections 4–9). Only the implementation languages change. **Vote in Week 0 and record the result in `docs/adr/ADR-001-tech-stack.md`.**

### Option A — "Python Core" (FastAPI + React)

| Layer | Choice |
|---|---|
| Frontend | React 18 + Vite + TypeScript + Tailwind CSS + shadcn/ui + TanStack Query + Recharts |
| Backend API | **FastAPI** (Python 3.11) + SQLAlchemy 2 + Alembic + Pydantic v2 |
| AI / CV | Ultralytics YOLOv8 (or YOLO11) + OpenCV + EigenCAM heatmaps + `imagehash` (pHash) |
| Background jobs | Redis + **Celery** (or RQ) for anchoring batches and async inference |
| Database | PostgreSQL 16 |
| Evidence storage | **MinIO** (S3-compatible) with Object Lock/retention on the evidence bucket |
| Blockchain | Solidity + **Hardhat** (local) to Polygon Amoy testnet, accessed via **web3.py** |
| Crypto | `hashlib` (SHA-256), `rfc8785` (JSON canonicalization), **PyNaCl** (Ed25519) |
| Reports | WeasyPrint (HTML to PDF) + `qrcode` |
| Auth | JWT (access + refresh) + role checks via FastAPI dependencies |

**Pros**
- AI and backend share one language, so there is no glue service and model hashing, inference and API all live in Python.
- FastAPI generates Swagger/OpenAPI docs automatically, which looks professional to examiners.
- Pydantic gives strict validation of the canonical record.
- It is the fastest path for a 3-person team, and probably the stack the team knows best.

**Cons**
- There are still two languages (Python + TS frontend), so the browser-side verifier needs a TS copy of the hashing/Merkle code. Shared test vectors solve this.
- web3.py is less polished than ethers.js.
- Celery has some setup overhead (RQ is simpler if Celery feels heavy).
- Python is slower than Go/Node for very high ingestion volume. That does not matter at MVP scale.

---

### Option B — "TypeScript Full-stack" (NestJS + Next.js + Python AI microservice)

| Layer | Choice |
|---|---|
| Frontend | **Next.js 14** (App Router) + Tailwind + shadcn/ui + Recharts |
| Backend API | **NestJS** + Prisma ORM + class-validator |
| AI / CV | Separate **FastAPI** microservice (YOLOv8 + EigenCAM + imagehash) |
| Background jobs | Redis + **BullMQ** |
| Database | PostgreSQL 16 (append-only triggers via raw SQL migrations) |
| Evidence storage | MinIO |
| Blockchain | Solidity + Hardhat + **ethers.js v6** |
| Crypto | `node:crypto` (SHA-256 + Ed25519 built in), `canonicalize` (RFC 8785) |
| Reports | `pdfkit` or Puppeteer + `qrcode` |
| Auth | NestJS Passport JWT + Guards for RBAC |

**Pros**
- Frontend and backend share types and share the **same hashing/Merkle code**, so the public in-browser verifier reuses `proof-core` directly.
- ethers.js and the Hardhat toolchain are the best-documented in the Ethereum ecosystem.
- The NestJS module structure (controllers, services, guards) reads as "enterprise" in a review.
- Built-in Ed25519 in Node removes a dependency.

**Cons**
- It is still polyglot, because the AI must be Python. That means one extra service, one extra network hop and an extra Dockerfile.
- NestJS has a lot of boilerplate and a learning curve if the team is not comfortable with decorators/DI.
- Prisma does not express DB triggers, so the append-only rules need hand-written SQL migrations.
- Next.js server components add complexity we do not need for a dashboard.

---

### Option C — "Permissioned Enterprise" (Spring Boot + Hyperledger Fabric)

| Layer | Choice |
|---|---|
| Frontend | React + Vite + TypeScript + Ant Design |
| Backend API | **Spring Boot 3** (Java 21) + Spring Security + JPA + Flyway |
| AI / CV | Separate FastAPI microservice (YOLOv8) |
| Messaging | RabbitMQ (or Kafka) |
| Database | PostgreSQL 16 |
| Evidence storage | MinIO |
| Ledger | **Hyperledger Fabric 2.5** (test-network) with chaincode in Go, via the Fabric Gateway SDK |
| Crypto / identity | Fabric CA X.509 certificates (identities and signatures are built into the ledger) + Java `MessageDigest` |
| Reports | JasperReports or OpenPDF + ZXing (QR) |

**Pros**
- It is realistic for factories: private, permissioned, **no gas fees**, and confidential data never touches a public network.
- Every transaction is signed by an enrolled identity (MSP), so the "who did it" signatures come almost for free.
- Spring Boot carries strong enterprise credibility and is commonly known from coursework.
- Fabric's endorsement policies can model "regulator node must co-sign".

**Cons**
- The **setup is heaviest**: peers, orderers, CAs and channels in Docker, plus chaincode lifecycle. Expect a week lost to infra.
- There are three languages (Java + Go + Python) for a 3-person team.
- It **contradicts our poster's "public, tamper-evident ledger" claim**. If the operator controls all Fabric nodes, "not even us can rewrite it" is weaker, so we would have to reword Stage 3.
- It is hard to host for free for a live demo, and there is no public explorer like Polygonscan to show examiners.

---

### Decision matrix (score 1–5, higher is better)

| Criteria (weight) | A: Python Core | B: TS Full-stack | C: Fabric Enterprise |
|---|---|---|---|
| Speed to working MVP (×3) | **5** | 4 | 2 |
| Fit with AI/CV work (×2) | **5** | 3 | 3 |
| Matches poster claims (public ledger, independent verify) (×2) | **5** | **5** | 2 |
| Learning curve for 3 people (×2) | **4** | 3 | 2 |
| Industry/enterprise realism (×1) | 3 | 4 | **5** |
| Free hosting for live demo (×1) | **4** | **4** | 2 |
| **Weighted total** (max 55) | **50** | 42 | 27 |

**Lean:** Option A gives the most features per week for a 3-person team and keeps the public-ledger claim intact. Option B is the right pick if Aryan and Chaitanya are much stronger in TypeScript than Python. Option C is worth naming in the report as the **"production roadmap for private deployments"** even if we do not build it.

> The rest of this doc uses **Option A names** where a concrete library is needed. Everything else is stack-neutral.

---

## 4. System architecture

The architecture follows the 7 layers on the poster's block diagram.

```mermaid
flowchart TB
    subgraph L1["1 - Factory / Edge layer (simulated)"]
        CAM["Edge Simulator<br/>images from NEU-DET dataset<br/>device Ed25519 key"]
    end

    subgraph L2["2 - AI layer"]
        AI["AI Inspector service<br/>YOLOv8 + EigenCAM<br/>returns decision, class, severity, confidence, boxes, heatmap"]
        REG["Model Registry<br/>weights SHA-256, version, approval"]
    end

    subgraph L3["3 - Proof and integrity layer"]
        ING["Ingest API"]
        PC["proof-core<br/>canonicalize RFC 8785, SHA-256,<br/>Ed25519 verify, hash chain, Merkle"]
        RISK["Risk Engine<br/>LOW / MEDIUM / HIGH"]
        REPLAY["Replay Detector<br/>SHA-256 + pHash"]
    end

    subgraph L4["4 - Storage layer"]
        PG[("PostgreSQL<br/>append-only events")]
        S3[("MinIO<br/>evidence + heatmaps<br/>Object Lock")]
        RD[("Redis<br/>queues")]
    end

    subgraph L5["5 - Anchoring layer"]
        AW["Anchor Worker<br/>Merkle batching + immediate anchor"]
        SC["LedgeitAnchor.sol<br/>Hardhat local / Polygon Amoy"]
    end

    subgraph L6["6 - Human decision and verification layer"]
        OVR["Review / Override API<br/>user Ed25519 signatures"]
        VER["Verification Engine<br/>5 independent checks"]
        ALR["Alerts"]
    end

    subgraph L7["7 - Application layer"]
        WEB["Web Dashboard<br/>10 pages, RBAC"]
        PUB["Public Verify Page<br/>no login, QR target"]
        RPT["Reports PDF + QR"]
    end

    CAM -->|"image + signed metadata"| ING
    ING --> AI
    AI --> REG
    ING --> PC
    ING --> REPLAY
    PC --> PG
    ING --> S3
    PC --> RISK
    RISK -->|"enqueue"| RD
    RD --> AW
    AW --> SC
    AW --> PG
    REPLAY --> ALR
    WEB --> OVR
    OVR --> PC
    WEB --> VER
    PUB --> VER
    VER --> PG
    VER --> S3
    VER --> SC
    VER --> ALR
    WEB --> RPT
    RPT --> PG
```

### Deployment view (MVP)

```mermaid
flowchart LR
    subgraph DC["docker compose up"]
        web["web :5173"]
        api["api :8000"]
        ai["ai-inspector :8001"]
        worker["anchor-worker"]
        sim["edge-simulator"]
        pg[("postgres :5432")]
        redis[("redis :6379")]
        minio[("minio :9000")]
        chain["hardhat node :8545"]
    end
    amoy["Polygon Amoy testnet<br/>public RPC"]
    web --> api
    sim --> api
    api --> ai
    api --> pg
    api --> minio
    api --> redis
    worker --> redis
    worker --> pg
    worker --> chain
    worker -.->|"CHAIN=amoy"| amoy
```

`CHAIN=local` uses the Hardhat node (fast dev, free). `CHAIN=amoy` uses the public testnet for the final demo, so examiners can open the transaction on Polygonscan.

---

## 5. Core approach

This section is the technical heart of the project. Everyone should read it, and **`packages/proof-core/SPEC.md` should copy it verbatim** so it becomes the contract between all services.

### 5.1 Canonicalization

The same record must always produce the same bytes, otherwise hashes will not match across Python and TypeScript.
- Use **RFC 8785 JSON Canonicalization Scheme (JCS)**: sorted keys, no whitespace, fixed number format.
- **Store decimals as strings** (`"confidence": "0.9640"`, 4 decimal places) so float formatting never differs between languages.
- Timestamps are **UTC ISO-8601 with milliseconds and a `Z` suffix**: `2026-10-20T10:31:02.120Z`.
- Every payload carries a `schema` field (`ledgeit.inspection.v1`) so formats can evolve.

### 5.2 Hashes

| Hash | Formula |
|---|---|
| `evidence_sha256` | `SHA256(raw image bytes exactly as uploaded)`. **Never re-encode or resize before hashing.** |
| `heatmap_sha256` | `SHA256(heatmap PNG bytes)` |
| `weights_sha256` | `SHA256(model .pt file)`, stored in the Model Registry |
| `record_hash` | `SHA256(JCS(inspection proof record))`, which includes all of the above |
| `event_hash` | `SHA256(JCS({line_id, seq, event_type, actor, payload_hash, prev_event_hash, created_at}))` |

### 5.3 Hash chain (per production line)

Every event on a line points to the previous event's hash, so deleting or reordering any event breaks the chain from that point on.

```
GENESIS(line) <- e1 <- e2 <- e3 <- ...     (each e_n stores prev_event_hash = e_{n-1}.event_hash)
```

`seq` is strictly increasing per line with no gaps. A gap means a deleted event.

### 5.4 Signatures (Ed25519)

- **Device signature:** each edge device (simulator instance) has a keypair, and its public key is registered in `devices`. The device signs `record_hash`. An insider who edits the DB **does not have the device key**, so they cannot forge a new valid record. This closes the "before anchoring" window.
- **Human signature:** on first login the browser generates an Ed25519 keypair (`@noble/ed25519`) and registers the public key. Overrides and approvals are signed **in the browser** over the JCS of the override payload.
- *MVP honesty note:* the private key lives in browser IndexedDB. In production this would be a smart card or HSM. Say this in the presentation; it shows maturity.

### 5.5 Merkle tree (domain-separated, RFC 6962 style)

```
leaf  = SHA256(0x00 || event_hash_bytes)
node  = SHA256(0x01 || left || right)
odd number of nodes at a level -> the last node is promoted unchanged to the next level
proof = [{ "hash": "<hex>", "side": "L" | "R" }, ...]   (stored per leaf in anchor_items)
```
The `0x00`/`0x01` prefixes prevent second-preimage attacks, where an inner node is passed off as a leaf.

### 5.6 Risk-adaptive anchoring

| Risk | Rule (any one triggers) | Anchoring |
|---|---|---|
| **HIGH** | `severity = CRITICAL` · any human **override** · product **rejection** · `confidence < 0.60` · product `is_regulated = true` · replay/tamper alert raised | **Immediate**: a single-leaf Merkle root goes on-chain right away |
| **MEDIUM** | `severity = MINOR or MAJOR` · `0.60 ≤ confidence < 0.85` | Batch every **10 records or 60 s**, whichever comes first |
| **LOW** | `decision = PASS` and `confidence ≥ 0.85` | Batch every **100 records or 10 min** (configurable; the doc's production figure is 1 tx per 1,000) |

Thresholds live in `config/risk.yaml`, not in code, so they can be tuned live during the demo.

### 5.7 Verification engine — 5 independent checks

Each check reports `PASS / FAIL / PENDING` separately in the UI (matching the poster's verification layer):

1. **Evidence check:** re-download the image from MinIO and check that `SHA256(bytes) == record.evidence.sha256` (same for the heatmap).
2. **Model check:** `record.model.weights_sha256 == ai_models.weights_sha256` for that version, and the model was `APPROVED` at `inspected_at`.
3. **Signature check:** the device signature over `record_hash` is valid, and every override/approval signature is valid against that user's registered key.
4. **Event-chain check:** recompute every `event_hash` for the inspection's line segment, check that the `prev_event_hash` links and that `seq` has no gaps.
5. **Anchor check:** walk the Merkle proof from the leaf to the root, then call `anchors(root)` on the contract. The root must exist on-chain, and its block time must be after `inspected_at`. If the record is still waiting in a batch window, the result is `PENDING` rather than `FAIL`.

**Result:** `VERIFIED` if all pass · `FAILED — Record mismatch detected` if any fail · `PENDING_ANCHOR` if 1–4 pass and 5 is waiting.

**Why the blockchain matters, explained with the "smart insider" scenario:** if an insider edits the decision **and** recomputes `record_hash` and `event_hash` so the DB looks internally consistent, checks 1–4 might pass. But the recomputed leaf no longer matches the root already anchored on-chain, so check 5 fails. The DB can be rewritten; the chain cannot.

### 5.8 Replay detection

- **Exact replay:** the same `evidence_sha256` appears in two inspections with different unit serials. Raise a **HIGH** `DUPLICATE_EVIDENCE` alert.
- **Near replay** (re-compressed, cropped or brightened copy): compute a 64-bit **pHash**. Hamming distance ≤ 6 to any image from the last N days raises a **MEDIUM** `POSSIBLE_REPLAY` alert. Tune the threshold on the dataset, since images from a fixed camera of similar products can look alike.
- Store pHash in an indexed column. For the MVP a linear scan over recent rows is fine.

### 5.9 Append-only enforcement in the DB (defense in depth)

- A PostgreSQL trigger blocks `UPDATE` and `DELETE` on every proof table: `inspections`, `inspection_events`, `overrides`, `override_approvals`, `evidence`, `anchor_items`, `blockchain_txs` and `verifications` (see section 7).
- The application DB user has only `INSERT` and `SELECT` on those tables.
- Mutable things like the current status live in **projection tables** (`inspection_status`) that are **never hashed**. They are caches derived from events.
- The **Tamper Lab** connects as the Postgres superuser and disables the trigger, simulating a malicious DBA. The proof still catches it.

### 5.10 Economics

- For each anchor transaction, record `gas_used × effective_gas_price`, which gives the fee in POL. Convert to INR using a rate from `config/economics.yaml` (fixed rate for the MVP).
- Show **cost per inspection = total chain fees / inspections covered**. This proves the batching claim with real numbers instead of the doc's assumed ₹2 per transaction.

---

## 6. Flow diagrams

### 6.1 Inspection ingestion (Detect, then Bind)

```mermaid
sequenceDiagram
    autonumber
    participant SIM as Edge Simulator
    participant API as Ingest API
    participant AI as AI Inspector
    participant S3 as MinIO
    participant PC as proof-core
    participant DB as PostgreSQL
    participant RK as Risk Engine
    participant Q as Redis queue

    SIM->>API: POST /inspections (image, unit_serial, batch, device_id)
    API->>S3: store raw bytes (evidence bucket)
    API->>PC: sha256(image), pHash(image)
    API->>AI: POST /infer (image)
    AI-->>API: decision, class, severity, confidence, boxes, heatmap, model{version, weights_sha256}
    API->>S3: store heatmap PNG
    API->>PC: build record, canonicalize, record_hash
    API-->>SIM: record_hash (to sign)
    SIM->>API: Ed25519 signature over record_hash
    API->>PC: verify device signature
    API->>DB: INSERT inspection + events (INSPECTED, EVIDENCE_HASHED, RECORD_CREATED) with prev_event_hash
    API->>RK: classify risk
    RK->>Q: enqueue (event_hash, risk)
    API-->>SIM: 201 Created (inspection_id, risk)
```

> **Simplification allowed in Week 2:** the simulator can call `/infer` itself, build the record and sign it in one shot, then send everything to the API. Both are valid. Pick one and record it in an ADR.

### 6.2 Risk-adaptive anchoring (Anchor)

```mermaid
flowchart TD
    A["Event enqueued with risk level"] --> B{"Risk?"}
    B -->|HIGH| C["Build single-leaf tree"]
    B -->|MEDIUM| D["Add to MEDIUM buffer"]
    B -->|LOW| E["Add to LOW buffer"]
    D --> F{"10 records or 60 s?"}
    E --> G{"100 records or 10 min?"}
    F -->|no| D
    G -->|no| E
    F -->|yes| H["Build Merkle tree"]
    G -->|yes| H
    C --> I["INSERT anchor_batch PENDING + anchor_items with proofs"]
    H --> I
    I --> J["Send tx: LedgeitAnchor.anchor(root, batchId, leafCount, risk)"]
    J --> K{"Receipt OK?"}
    K -->|yes| L["INSERT blockchain_tx, batch CONFIRMED, event ANCHORED"]
    K -->|no / timeout| M["Retry with backoff, max 5"]
    M --> J
    M -->|"gave up"| N["batch FAILED + alert MISSING_ANCHOR"]
```

### 6.3 Human review and override (Respond)

```mermaid
sequenceDiagram
    autonumber
    actor QE as Quality Engineer
    participant WEB as Web App
    participant API as API
    participant PC as proof-core
    participant DB as PostgreSQL
    participant Q as Anchor queue
    actor QM as Quality Manager

    QE->>WEB: open inspection (AI said FAIL, 0.62)
    WEB->>API: GET inspection + evidence + heatmap
    QE->>WEB: Override to PASS, reason code, comment, evidence reviewed
    WEB->>WEB: build override payload, JCS, Ed25519 sign (browser key)
    WEB->>API: POST /inspections/id/override (payload + signature)
    API->>PC: verify signature against user public key
    API->>DB: INSERT override + event OVERRIDDEN (chained)
    API->>Q: enqueue HIGH (immediate anchor)
    API-->>WEB: status PENDING_APPROVAL
    QM->>WEB: review override
    WEB->>WEB: sign approval
    WEB->>API: POST /overrides/id/approve
    API->>DB: event APPROVED (chained) + enqueue HIGH
```

### 6.4 Verification (Verify)

```mermaid
flowchart LR
    S["Verify request<br/>inspection id or QR code"] --> C1["1 Evidence hash"]
    S --> C2["2 Model hash + approval"]
    S --> C3["3 Device + human signatures"]
    S --> C4["4 Event chain links + seq gaps"]
    S --> C5["5 Merkle proof to on-chain root"]
    C1 --> R{"All PASS?"}
    C2 --> R
    C3 --> R
    C4 --> R
    C5 --> R
    R -->|yes| V["VERIFIED - record has not changed"]
    R -->|"any FAIL"| F["FAILED - mismatch detected<br/>alert TAMPER_DETECTED"]
    R -->|"only 5 pending"| P["PENDING_ANCHOR"]
```

### 6.5 Inspection lifecycle (status projection)

```mermaid
stateDiagram-v2
    [*] --> RECORDED
    RECORDED --> AUTO_ACCEPTED: LOW risk PASS
    RECORDED --> PENDING_REVIEW: MEDIUM or HIGH risk
    PENDING_REVIEW --> ACCEPTED: QE agrees with AI
    PENDING_REVIEW --> OVERRIDDEN: QE disagrees
    OVERRIDDEN --> PENDING_APPROVAL: needs QM sign-off
    PENDING_APPROVAL --> RELEASED: QM approves PASS
    PENDING_APPROVAL --> REJECTED: QM approves FAIL
    ACCEPTED --> RELEASED: AI said PASS
    ACCEPTED --> REJECTED: AI said FAIL
    RELEASED --> DISPUTED: customer or auditor raises dispute
    REJECTED --> DISPUTED
    DISPUTED --> RELEASED
    DISPUTED --> REJECTED
```

Every arrow is an **event appended to the chain**. Nothing is edited.

### 6.6 Tamper demo flow

```mermaid
flowchart LR
    T1["Tamper Lab: change FAIL to PASS in DB<br/>as superuser, trigger disabled"] --> V1["Verify"] --> X1["Check 4 + 5 FAIL"]
    T2["Tamper Lab: swap image in MinIO"] --> V2["Verify"] --> X2["Check 1 FAIL"]
    T3["Tamper Lab: delete a REJECTED event"] --> V3["Verify"] --> X3["Check 4 FAIL - seq gap"]
    T4["Edge sim: --replay old good image"] --> D4["Ingest"] --> X4["DUPLICATE_EVIDENCE alert"]
    T5["Smart insider: edit + recompute all hashes"] --> V5["Verify"] --> X5["Check 5 FAIL - root not on chain"]
```

---

## 7. Database schema

PostgreSQL 16. File: `apps/api/migrations/` (Alembic) or `infra/db/schema.sql` as the reference copy.

```sql
-- ============ EXTENSIONS & ENUMS ============
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid()

CREATE TYPE user_role        AS ENUM ('OPERATOR','QUALITY_ENGINEER','QUALITY_MANAGER','AUDITOR','ADMIN');
CREATE TYPE decision_t       AS ENUM ('PASS','FAIL');
CREATE TYPE severity_t       AS ENUM ('NONE','MINOR','MAJOR','CRITICAL');
CREATE TYPE risk_t           AS ENUM ('LOW','MEDIUM','HIGH');
CREATE TYPE model_status_t   AS ENUM ('DRAFT','APPROVED','RETIRED');
CREATE TYPE actor_t          AS ENUM ('DEVICE','USER','SYSTEM');
CREATE TYPE event_t          AS ENUM ('INSPECTED','EVIDENCE_HASHED','RECORD_CREATED','ANCHOR_QUEUED','ANCHORED',
                                      'REVIEWED','OVERRIDDEN','APPROVED','RELEASED','REJECTED',
                                      'DISPUTE_RAISED','DISPUTE_RESOLVED','VERIFIED','TAMPER_DETECTED');
CREATE TYPE anchor_status_t  AS ENUM ('PENDING','SUBMITTED','CONFIRMED','FAILED');
CREATE TYPE verify_result_t  AS ENUM ('VERIFIED','FAILED','PENDING_ANCHOR');
CREATE TYPE alert_t          AS ENUM ('HASH_MISMATCH','DUPLICATE_EVIDENCE','POSSIBLE_REPLAY','MODEL_MISMATCH',
                                      'HIGH_OVERRIDE_RATE','LOW_CONFIDENCE','MISSING_ANCHOR','DELETION_ATTEMPT',
                                      'DELAYED_APPROVAL','SIGNATURE_INVALID','TAMPER_DETECTED');
CREATE TYPE alert_status_t   AS ENUM ('OPEN','ACKNOWLEDGED','RESOLVED');

-- ============ IDENTITY ============
CREATE TABLE users (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_code  TEXT UNIQUE NOT NULL,          -- e.g. QA-1028
  full_name      TEXT NOT NULL,
  email          TEXT UNIQUE NOT NULL,
  password_hash  TEXT NOT NULL,                 -- argon2/bcrypt
  role           user_role NOT NULL,
  public_key     TEXT,                          -- Ed25519 public key, base64
  is_active      BOOLEAN NOT NULL DEFAULT TRUE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============ FACTORY MASTER DATA ============
CREATE TABLE plants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL, location TEXT
);

CREATE TABLE production_lines (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  plant_id UUID NOT NULL REFERENCES plants(id),
  code TEXT UNIQUE NOT NULL,                    -- e.g. LINE-A
  name TEXT NOT NULL,
  genesis_hash CHAR(64) NOT NULL                -- first prev_event_hash for this line
);

CREATE TABLE devices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  line_id UUID NOT NULL REFERENCES production_lines(id),
  device_code TEXT UNIQUE NOT NULL,             -- e.g. CAM-A-01
  device_type TEXT NOT NULL DEFAULT 'CAMERA',
  public_key TEXT NOT NULL,                     -- Ed25519, base64
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  registered_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sku TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  is_regulated BOOLEAN NOT NULL DEFAULT FALSE   -- regulated => HIGH risk
);

CREATE TABLE batches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_code TEXT UNIQUE NOT NULL,
  product_id UUID NOT NULL REFERENCES products(id),
  line_id UUID NOT NULL REFERENCES production_lines(id),
  started_at TIMESTAMPTZ NOT NULL,
  ended_at TIMESTAMPTZ
);

-- ============ AI MODEL REGISTRY ============
CREATE TABLE ai_models (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,                           -- ledgeit-defect-yolo
  version TEXT NOT NULL,                        -- 1.2.0
  weights_sha256 CHAR(64) NOT NULL,
  framework TEXT NOT NULL,                      -- ultralytics-8.x
  dataset_version TEXT NOT NULL,                -- neu-det-v1
  training_date DATE,
  metrics JSONB NOT NULL DEFAULT '{}',          -- {"mAP50":0.74,"precision":...}
  status model_status_t NOT NULL DEFAULT 'DRAFT',
  approved_by UUID REFERENCES users(id),
  approved_at TIMESTAMPTZ,
  deployed_at TIMESTAMPTZ,
  environment TEXT NOT NULL DEFAULT 'demo',
  UNIQUE (name, version)
);

-- ============ EVIDENCE ============
CREATE TABLE evidence (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  kind TEXT NOT NULL,                           -- 'IMAGE' | 'HEATMAP'
  sha256 CHAR(64) NOT NULL,                     -- NOT unique: duplicates = replay signal
  phash CHAR(16),                               -- 64-bit perceptual hash, hex
  storage_uri TEXT NOT NULL,                    -- s3://evidence/2026/10/20/<sha256>.png
  mime_type TEXT NOT NULL,
  size_bytes BIGINT NOT NULL,
  width INT, height INT,
  device_id UUID REFERENCES devices(id),
  captured_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_evidence_sha ON evidence(sha256);
CREATE INDEX idx_evidence_phash ON evidence(phash);

-- ============ INSPECTION PROOF RECORD (immutable) ============
CREATE TABLE inspections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  inspection_code TEXT UNIQUE NOT NULL,         -- INS-20261020-000123
  unit_serial TEXT NOT NULL,
  batch_id UUID NOT NULL REFERENCES batches(id),
  line_id UUID NOT NULL REFERENCES production_lines(id),
  device_id UUID NOT NULL REFERENCES devices(id),
  model_id UUID NOT NULL REFERENCES ai_models(id),
  evidence_id UUID NOT NULL REFERENCES evidence(id),
  heatmap_evidence_id UUID REFERENCES evidence(id),
  decision decision_t NOT NULL,
  defect_class TEXT,                            -- crazing|inclusion|patches|pitted_surface|rolled-in_scale|scratches
  severity severity_t NOT NULL,
  confidence NUMERIC(5,4) NOT NULL,
  explanation JSONB NOT NULL,                   -- boxes, method, summary
  risk_level risk_t NOT NULL,
  canonical_record JSONB NOT NULL,              -- exact JSON that was hashed
  record_hash CHAR(64) UNIQUE NOT NULL,
  device_signature TEXT NOT NULL,               -- base64 Ed25519 over record_hash
  inspected_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_insp_batch ON inspections(batch_id);
CREATE INDEX idx_insp_line_time ON inspections(line_id, inspected_at DESC);

-- ============ EVENT HASH CHAIN (append-only) ============
CREATE TABLE inspection_events (
  id BIGSERIAL PRIMARY KEY,
  inspection_id UUID NOT NULL REFERENCES inspections(id),
  line_id UUID NOT NULL REFERENCES production_lines(id),
  seq BIGINT NOT NULL,                          -- per-line, gapless
  event_type event_t NOT NULL,
  actor_type actor_t NOT NULL,
  actor_id UUID,                                -- user or device
  payload JSONB NOT NULL,
  payload_hash CHAR(64) NOT NULL,
  prev_event_hash CHAR(64) NOT NULL,
  event_hash CHAR(64) UNIQUE NOT NULL,
  signature TEXT,                               -- for USER/DEVICE actors
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (line_id, seq)
);
CREATE INDEX idx_events_insp ON inspection_events(inspection_id, seq);

-- ============ HUMAN OVERRIDES ============
CREATE TABLE overrides (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  inspection_id UUID NOT NULL REFERENCES inspections(id),
  original_decision decision_t NOT NULL,
  original_confidence NUMERIC(5,4) NOT NULL,
  new_decision decision_t NOT NULL,
  reason_code TEXT NOT NULL,                    -- FALSE_POSITIVE | FALSE_NEGATIVE | LIGHTING | OTHER
  reason_text TEXT NOT NULL,
  reviewed_evidence_ids UUID[] NOT NULL,
  operator_id UUID NOT NULL REFERENCES users(id),
  operator_signature TEXT NOT NULL,
  event_id BIGINT NOT NULL REFERENCES inspection_events(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE override_approvals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  override_id UUID NOT NULL REFERENCES overrides(id),
  approver_id UUID NOT NULL REFERENCES users(id),
  approved BOOLEAN NOT NULL,
  comment TEXT,
  signature TEXT NOT NULL,
  event_id BIGINT NOT NULL REFERENCES inspection_events(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============ ANCHORING ============
CREATE TABLE anchor_batches (
  id BIGSERIAL PRIMARY KEY,
  merkle_root CHAR(64) UNIQUE NOT NULL,
  leaf_count INT NOT NULL,
  risk_level risk_t NOT NULL,
  status anchor_status_t NOT NULL DEFAULT 'PENDING',  -- mutable: updated by anchor worker (root itself never changes)
  attempts INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  confirmed_at TIMESTAMPTZ
);

CREATE TABLE anchor_items (
  id BIGSERIAL PRIMARY KEY,
  batch_id BIGINT NOT NULL REFERENCES anchor_batches(id),
  event_id BIGINT UNIQUE NOT NULL REFERENCES inspection_events(id),
  leaf_index INT NOT NULL,
  leaf_hash CHAR(64) NOT NULL,
  merkle_proof JSONB NOT NULL                   -- [{"hash":"..","side":"L"}, ...]
);

CREATE TABLE blockchain_txs (
  id BIGSERIAL PRIMARY KEY,
  batch_id BIGINT NOT NULL REFERENCES anchor_batches(id),
  network TEXT NOT NULL,                        -- hardhat-local | polygon-amoy
  chain_id INT NOT NULL,                        -- 31337 | 80002
  contract_address CHAR(42) NOT NULL,
  tx_hash CHAR(66) UNIQUE NOT NULL,
  block_number BIGINT,
  block_timestamp TIMESTAMPTZ,
  gas_used BIGINT,
  effective_gas_price_wei NUMERIC(38,0),
  fee_native NUMERIC(38,18),
  fee_inr NUMERIC(12,4),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============ VERIFICATION, ALERTS, REPORTS, COSTS ============
CREATE TABLE verifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  inspection_id UUID NOT NULL REFERENCES inspections(id),
  requested_by UUID REFERENCES users(id),       -- NULL = public verify
  result verify_result_t NOT NULL,
  checks JSONB NOT NULL,                        -- {"evidence":"PASS","model":"PASS","signature":"PASS","chain":"FAIL","anchor":"PASS","details":{...}}
  verified_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  alert_type alert_t NOT NULL,
  severity risk_t NOT NULL,
  inspection_id UUID REFERENCES inspections(id),
  details JSONB NOT NULL DEFAULT '{}',
  status alert_status_t NOT NULL DEFAULT 'OPEN',
  resolved_by UUID REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at TIMESTAMPTZ
);

CREATE TABLE reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  report_type TEXT NOT NULL,                    -- BATCH | DEFECT | OVERRIDE | MODEL_HISTORY | TAMPER | CHAIN_VERIFICATION
  params JSONB NOT NULL,
  file_uri TEXT NOT NULL,
  file_sha256 CHAR(64) NOT NULL,
  verification_code TEXT UNIQUE NOT NULL,       -- encoded in the QR
  generated_by UUID NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE cost_entries (
  id BIGSERIAL PRIMARY KEY,
  category TEXT NOT NULL,                       -- BLOCKCHAIN | STORAGE | COMPUTE | INFERENCE | DATABASE
  amount_inr NUMERIC(12,4) NOT NULL,
  period_start TIMESTAMPTZ NOT NULL,
  period_end TIMESTAMPTZ NOT NULL,
  source TEXT NOT NULL                          -- 'tx_receipt' | 'estimate'
);

-- ============ MUTABLE PROJECTION (never hashed) ============
CREATE TABLE inspection_status (
  inspection_id UUID PRIMARY KEY REFERENCES inspections(id),
  status TEXT NOT NULL,                         -- RECORDED | PENDING_REVIEW | ... (see state diagram)
  anchor_status anchor_status_t NOT NULL DEFAULT 'PENDING',
  last_event_id BIGINT REFERENCES inspection_events(id),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============ APPEND-ONLY ENFORCEMENT ============
CREATE OR REPLACE FUNCTION ledgeit_forbid_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'LEDGEIT: % on % is forbidden (append-only table)', TG_OP, TG_TABLE_NAME;
END; $$ LANGUAGE plpgsql;

DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['inspections','inspection_events','overrides','override_approvals',
                           'anchor_items','blockchain_txs','evidence','verifications']
  LOOP
    EXECUTE format('CREATE TRIGGER %I_append_only BEFORE UPDATE OR DELETE ON %I
                    FOR EACH ROW EXECUTE FUNCTION ledgeit_forbid_mutation()', t, t);
  END LOOP;
END $$;

-- App role: insert + select only on proof tables
-- CREATE ROLE ledgeit_app LOGIN PASSWORD '...';
-- GRANT SELECT, INSERT ON inspections, inspection_events, overrides, override_approvals,
--       anchor_items, blockchain_txs, evidence, verifications TO ledgeit_app;
-- GRANT SELECT, INSERT, UPDATE ON inspection_status, anchor_batches, alerts TO ledgeit_app;
```

---

## 8. ER diagram

```mermaid
erDiagram
    PLANT ||--o{ PRODUCTION_LINE : has
    PRODUCTION_LINE ||--o{ DEVICE : hosts
    PRODUCTION_LINE ||--o{ BATCH : runs
    PRODUCT ||--o{ BATCH : "produced as"
    BATCH ||--o{ INSPECTION : contains
    DEVICE ||--o{ INSPECTION : captures
    DEVICE ||--o{ EVIDENCE : uploads
    AI_MODEL ||--o{ INSPECTION : decides
    USER ||--o{ AI_MODEL : approves
    INSPECTION ||--|| EVIDENCE : "image"
    INSPECTION ||--o| EVIDENCE : "heatmap"
    INSPECTION ||--|{ INSPECTION_EVENT : "timeline"
    PRODUCTION_LINE ||--o{ INSPECTION_EVENT : "hash chain"
    INSPECTION ||--o{ OVERRIDE : "may have"
    USER ||--o{ OVERRIDE : performs
    OVERRIDE ||--o{ OVERRIDE_APPROVAL : "approved by"
    USER ||--o{ OVERRIDE_APPROVAL : signs
    INSPECTION_EVENT ||--o| ANCHOR_ITEM : "leaf of"
    ANCHOR_BATCH ||--|{ ANCHOR_ITEM : groups
    ANCHOR_BATCH ||--o{ BLOCKCHAIN_TX : "submitted as"
    INSPECTION ||--o{ VERIFICATION : "checked by"
    INSPECTION ||--o{ ALERT : raises
    INSPECTION ||--|| INSPECTION_STATUS : "projected to"
    USER ||--o{ REPORT : generates

    INSPECTION {
        uuid id PK
        string inspection_code UK
        string unit_serial
        uuid batch_id FK
        uuid model_id FK
        uuid evidence_id FK
        enum decision
        enum severity
        decimal confidence
        enum risk_level
        json canonical_record
        string record_hash UK
        string device_signature
        timestamp inspected_at
    }
    INSPECTION_EVENT {
        bigint id PK
        uuid inspection_id FK
        uuid line_id FK
        bigint seq
        enum event_type
        enum actor_type
        string payload_hash
        string prev_event_hash
        string event_hash UK
        string signature
    }
    EVIDENCE {
        uuid id PK
        string kind
        string sha256
        string phash
        string storage_uri
    }
    AI_MODEL {
        uuid id PK
        string name
        string version
        string weights_sha256
        enum status
    }
    OVERRIDE {
        uuid id PK
        enum original_decision
        enum new_decision
        string reason_code
        string operator_signature
    }
    ANCHOR_BATCH {
        bigint id PK
        string merkle_root UK
        int leaf_count
        enum risk_level
        enum status
    }
    ANCHOR_ITEM {
        bigint id PK
        bigint event_id FK
        int leaf_index
        json merkle_proof
    }
    BLOCKCHAIN_TX {
        bigint id PK
        string tx_hash UK
        int chain_id
        bigint block_number
        bigint gas_used
        decimal fee_inr
    }
    USER {
        uuid id PK
        string employee_code UK
        enum role
        string public_key
    }
```

---

## 9. Canonical record format + smart contract

### 9.1 Inspection Proof Record (`ledgeit.inspection.v1`)

This exact JSON (after RFC 8785 canonicalization) is what gets hashed into `record_hash`:

```json
{
  "schema": "ledgeit.inspection.v1",
  "inspection_id": "8f0e7c1a-5b2d-4d1e-9a77-3c2f1e0b9d44",
  "inspection_code": "INS-20261020-000123",
  "unit_serial": "UNIT-A-000123",
  "batch_id": "BATCH-2026-10-20-A",
  "line_id": "LINE-A",
  "device_id": "CAM-A-01",
  "inspected_at": "2026-10-20T10:31:02.120Z",
  "evidence": {
    "sha256": "a34df8...e1",
    "phash": "c3d1e0f0a8b4c2d1",
    "mime": "image/jpeg",
    "bytes": 48211
  },
  "model": {
    "name": "ledgeit-defect-yolo",
    "version": "1.2.0",
    "weights_sha256": "9b1c...7f"
  },
  "result": {
    "decision": "FAIL",
    "defect_class": "scratches",
    "severity": "MAJOR",
    "confidence": "0.9640",
    "boxes": [{"x1": 34, "y1": 80, "x2": 120, "y2": 140, "cls": "scratches", "conf": "0.9640"}]
  },
  "explanation": {
    "method": "EigenCAM",
    "heatmap_sha256": "51ac...0d",
    "summary": "Linear high-contrast streak in upper-left region"
  },
  "prev_record_hash": "0000...00"
}
```

### 9.2 Override payload (`ledgeit.override.v1`), signed in the browser

```json
{
  "schema": "ledgeit.override.v1",
  "inspection_id": "8f0e7c1a-...",
  "record_hash": "e2b7...",
  "original": {"decision": "FAIL", "confidence": "0.6200"},
  "new_decision": "PASS",
  "reason_code": "FALSE_POSITIVE",
  "reason_text": "Reflection from lighting, not a crack; checked under alternate angle",
  "reviewed_evidence": ["a34df8...e1", "51ac...0d"],
  "operator": {"employee_code": "QE-0042", "public_key": "base64..."},
  "signed_at": "2026-10-20T10:32:14.502Z"
}
```

### 9.3 Smart contract (`contracts/src/LedgeitAnchor.sol`)

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title LedgeitAnchor - append-only registry of Merkle roots for inspection events
/// @notice There is intentionally NO function to update or delete an anchor.
contract LedgeitAnchor {
    struct Anchor {
        uint64 timestamp;
        uint32 leafCount;
        uint8 riskLevel; // 0 LOW, 1 MEDIUM, 2 HIGH
    }

    address public immutable owner;
    mapping(address => bool) public isAnchorer;
    mapping(bytes32 => Anchor) public anchors;

    event RootAnchored(
        bytes32 indexed root,
        uint256 indexed batchId,
        uint32 leafCount,
        uint8 riskLevel,
        uint64 timestamp
    );
    event AnchorerSet(address indexed who, bool allowed);

    error NotOwner();
    error NotAnchorer();
    error AlreadyAnchored(bytes32 root);
    error EmptyBatch();

    constructor() {
        owner = msg.sender;
        isAnchorer[msg.sender] = true;
    }

    function setAnchorer(address who, bool allowed) external {
        if (msg.sender != owner) revert NotOwner();
        isAnchorer[who] = allowed;
        emit AnchorerSet(who, allowed);
    }

    function anchor(bytes32 root, uint256 batchId, uint32 leafCount, uint8 riskLevel) external {
        if (!isAnchorer[msg.sender]) revert NotAnchorer();
        if (leafCount == 0) revert EmptyBatch();
        if (anchors[root].timestamp != 0) revert AlreadyAnchored(root);
        anchors[root] = Anchor(uint64(block.timestamp), leafCount, riskLevel);
        emit RootAnchored(root, batchId, leafCount, riskLevel, uint64(block.timestamp));
    }

    function isAnchored(bytes32 root) external view returns (bool) {
        return anchors[root].timestamp != 0;
    }
}
```

**Contract tests to write (Hardhat):** anchor succeeds and emits the event · a duplicate root reverts · a non-anchorer reverts · `leafCount = 0` reverts · there is no way to overwrite an anchor · gas snapshot for one anchor call (feeds the Economics page).

---

## 10. API contract

Base: `/api/v1` · Auth: `Authorization: Bearer <JWT>` · Errors: `{ "error": { "code": "...", "message": "..." } }`

| Method | Path | Role(s) | Purpose |
|---|---|---|---|
| POST | `/auth/login` | public | Email + password, returns access/refresh tokens |
| POST | `/auth/keys` | any | Register the browser's Ed25519 public key |
| GET | `/auth/me` | any | Current user + role |
| POST | `/inspections` | device | Ingest image + metadata + device signature |
| GET | `/inspections` | all | Filter by `line, batch, decision, risk, status, from, to` |
| GET | `/inspections/{id}` | all | Full record + status + anchor status |
| GET | `/inspections/{id}/timeline` | all | Ordered event chain |
| GET | `/inspections/{id}/evidence` | all | Presigned URLs (image, heatmap) |
| POST | `/inspections/{id}/review` | QE | Accept the AI decision (signed) |
| POST | `/inspections/{id}/override` | QE | Override (signed payload) |
| POST | `/overrides/{id}/approve` | QM | Approve/reject override (signed) |
| POST | `/inspections/{id}/dispute` | QM, Auditor | Raise dispute (event) |
| POST | `/inspections/{id}/verify` | all | Run 5 checks, returns `verifications` row |
| GET | `/public/verify/{code}` | **public** | QR target. Read-only verification result with no confidential image |
| GET/POST | `/models`, `PATCH /models/{id}/approve` | Admin, QM | Model registry |
| GET | `/anchors`, `/anchors/{id}` | all | Batches + Merkle info |
| GET | `/chain/txs` | all | Blockchain explorer data |
| GET | `/alerts`, `PATCH /alerts/{id}` | QE, QM, Admin | List/ack/resolve |
| POST | `/reports`, `GET /reports/{id}/download` | QM, Auditor | Generate/download PDF |
| GET | `/dashboard/summary` | all | KPIs for the executive dashboard |
| GET | `/economics` | QM, Admin | Fees, cost per inspection, batching savings |
| WS | `/ws/feed` | all | Live inspection feed |

**AI Inspector service** (internal): `POST /infer` (multipart image) returns `{decision, defect_class, severity, confidence, boxes[], heatmap_png_b64, model:{name,version,weights_sha256}, latency_ms}` · `GET /health` · `GET /model`.

---

## 11. Folder structure

Stack-neutral monorepo. **Chaitanya creates this skeleton on `main` in Week 0.** Everyone then branches from it.

```
LEDGEIT/
├── .github/
│   ├── workflows/
│   │   └── ci.yml                    # lint + test for api, web, ai, contracts, proof-core
│   ├── ISSUE_TEMPLATE/
│   │   ├── feature.md
│   │   └── bug.md
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── CODEOWNERS                    # auto-request reviews per folder
├── apps/
│   ├── api/                          # Backend API (FastAPI | NestJS | Spring Boot)
│   │   ├── src/
│   │   │   ├── auth/                 # JWT, RBAC, key registration
│   │   │   ├── inspections/          # ingest, list, detail, timeline
│   │   │   ├── overrides/            # review, override, approval
│   │   │   ├── verification/         # 5-check engine
│   │   │   ├── anchoring/            # risk engine + queue producer
│   │   │   ├── models_registry/
│   │   │   ├── alerts/
│   │   │   ├── reports/              # PDF + QR
│   │   │   ├── economics/
│   │   │   ├── dashboard/
│   │   │   ├── chain/                # contract client (web3.py / ethers)
│   │   │   ├── storage/              # MinIO client
│   │   │   ├── db/                   # models/entities, session
│   │   │   └── core/                 # config, logging, errors
│   │   ├── migrations/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── README.md
│   └── web/                          # Frontend dashboard
│       ├── src/
│       │   ├── pages/                # executive, feed, inspection, explorer, verify,
│       │   │                         # models, overrides, risk, reports, economics, public-verify
│       │   ├── components/           # Timeline, HashBadge, VerifyChecklist, EvidenceViewer...
│       │   ├── lib/                  # api client, crypto (noble-ed25519), proof-core TS port
│       │   ├── hooks/
│       │   └── styles/
│       ├── public/
│       ├── tests/
│       ├── Dockerfile
│       └── README.md
├── services/
│   ├── ai-inspector/                 # Python: YOLO inference + EigenCAM
│   │   ├── app/                      # FastAPI /infer, /health
│   │   ├── training/                 # train.py, data.yaml, notebooks/
│   │   ├── models/                   # .pt weights (git-ignored, see README)
│   │   ├── tests/
│   │   └── Dockerfile
│   ├── edge-simulator/               # streams images, signs records, --replay mode
│   │   ├── simulator/
│   │   ├── keys/                     # dev device keys (git-ignored)
│   │   └── README.md
│   └── anchor-worker/                # consumes queue, builds Merkle, sends tx
│       ├── worker/
│       └── tests/
├── packages/
│   └── proof-core/                   # THE integrity spec + implementations
│       ├── SPEC.md                   # canonicalization, hashes, chain, Merkle, signatures
│       ├── python/                   # used by api, worker, simulator
│       ├── ts/                       # used by web (public verifier)
│       └── test-vectors/             # shared JSON vectors, both impls must pass
├── contracts/
│   ├── src/LedgeitAnchor.sol
│   ├── test/
│   ├── scripts/deploy.ts
│   ├── hardhat.config.ts
│   └── deployments/                  # addresses per network (committed)
├── config/
│   ├── risk.yaml                     # thresholds + batch sizes
│   └── economics.yaml                # POL to INR rate, storage cost estimates
├── infra/
│   ├── docker-compose.yml            # postgres, redis, minio, hardhat, all services
│   ├── db/
│   │   ├── schema.sql                # reference schema (section 7)
│   │   └── seed.sql                  # plants, lines, devices, users, models
│   └── minio/                        # bucket + object-lock setup
├── scripts/
│   ├── tamper-lab/                   # edit_record.sql, swap_evidence.py, delete_event.sql, smart_insider.py
│   ├── seed_demo.py
│   └── gen_device_keys.py
├── datasets/                         # git-ignored, README explains download (NEU-DET)
│   └── README.md
├── docs/
│   ├── adr/                          # ADR-001-tech-stack.md, ADR-002-chain-choice.md, ...
│   ├── architecture/                 # diagrams (mermaid sources + exported PNG)
│   ├── api/                          # exported OpenAPI json
│   ├── progress/                     # weekly-YYYY-MM-DD.md logs
│   ├── references/                   # the original PDFs/DOCX/poster (moved here)
│   └── team/
│       └── CHAITANYA.md              # this file
├── .env.example
├── .gitignore
├── .editorconfig
├── CLAUDE.md                         # rules for Claude Code (section 15)
├── CONTRIBUTING.md                   # branch + commit rules (section 14)
├── CHANGELOG.md
├── LICENSE
├── Makefile                          # make up | make test | make seed | make demo
└── README.md
```

**Ownership (`.github/CODEOWNERS`):**
```
/apps/api/                 @frchaitanyaaa
/packages/proof-core/      @frchaitanyaaa
/contracts/                @frchaitanyaaa
/services/anchor-worker/   @frchaitanyaaa
/services/ai-inspector/    @<ishan-github>
/services/edge-simulator/  @<ishan-github>
/scripts/tamper-lab/       @<ishan-github>
/apps/web/                 @<aryan-github>
/apps/api/src/reports/     @<aryan-github>
/apps/api/src/economics/   @<aryan-github>
/docs/                     @frchaitanyaaa @<ishan-github> @<aryan-github>
```

---

## 12. Work division

The split is by **vertical ownership**: each person owns whole modules end-to-end, including their tests and docs. That way all three have visible commits in every week.

### 👤 Chaitanya Pagare — Lead · Backend Core · Integrity & Blockchain

**Owns:** `apps/api` (core), `packages/proof-core`, `contracts/`, `services/anchor-worker`, `infra/`, CI, repo governance.

- Repo scaffold, branch protection, CI pipeline, `docker-compose`, `.env.example`, Makefile
- DB schema + migrations + append-only triggers + seed data
- Auth (JWT) + RBAC + public-key registration
- `proof-core`: JCS canonicalization, SHA-256, hash chain, Merkle tree + proofs, Ed25519 verify, **with shared test vectors** (Python + TS)
- Ingest API (`POST /inspections`), event chain writer
- `LedgeitAnchor.sol` + Hardhat tests + deploy scripts (local + Amoy)
- Anchor worker: Merkle batching, tx submission, retries, receipt to `blockchain_txs`
- **Verification engine (5 checks)** + `/public/verify/{code}`
- ADRs, weekly progress log, release tags

### 👤 Ishan Shrivastava — AI / Computer Vision · Edge · Risk & Security

**Owns:** `services/ai-inspector`, `services/edge-simulator`, risk engine rules, replay detection, alerts, `scripts/tamper-lab`.

- Dataset: **NEU-DET** (NEU surface defect database, 6 classes of steel defects with bounding boxes; ties directly to the Kobe Steel case). Train/val split, `data.yaml`.
- Train a YOLOv8n/s baseline, then report mAP@50, precision and recall per class in the Model Registry `metrics`
- `/infer` endpoint: decision, class, **severity mapping** (class + box area to MINOR/MAJOR/CRITICAL), confidence, boxes
- **EigenCAM heatmap** explanation + text summary
- Model weights hashing + register 2 versions (e.g., v1.0.0 nano and v1.1.0 small) to demo "which model decided"
- Edge simulator: streams images at N/sec, signs records with the device key, `--replay` and `--burst` modes
- Risk engine (`config/risk.yaml` + classifier function)
- Replay detection: exact SHA-256 + pHash with a tuned threshold
- Alert rules: high override rate, low confidence, model mismatch, missing anchor, delayed approval
- **Tamper Lab** scripts (all 5 attacks in section 6.6)
- Model KPIs: false positive/negative rates derived from overrides

### 👤 Aryan Kale — Frontend · UX · Reports & Economics

**Owns:** `apps/web`, `apps/api/src/reports`, `apps/api/src/economics`, `apps/api/src/dashboard`, override UX.

- Frontend shell: routing, auth pages, layout, role-based navigation, design tokens
- Pages: **Executive Dashboard, Live Feed (WebSocket), Inspection Detail + Event Timeline, Blockchain Explorer, Verification Center, Model Registry, Override Center, Risk & Tampering, Compliance Reports, Economics**
- Browser key generation + **Ed25519 signing** for review/override/approval (`@noble/ed25519`)
- Public Verify page (QR target), runs check 5 **in the browser** against a public RPC using the TS `proof-core`, so the user doesn't have to trust our server
- Reports API: Batch, Defect, Override, Model History, Tamper, Chain Verification PDFs with a QR `verification_code`
- Economics API + page: fees from tx receipts, cost per inspection, "without batching vs with batching" comparison
- Dashboard summary API (KPIs from section 23 of the platform doc)
- UI polish, empty/loading/error states, demo video recording

### Shared responsibilities

| Responsibility | How |
|---|---|
| Code review | Every PR needs **1 approval from someone other than the author** |
| Integration testing | Friday "integration hour": everyone pulls `main`, runs `make up && make demo` |
| Docs | Each owner keeps their module `README.md` current |
| Progress log | Rotating: Week 1 Chaitanya, Week 2 Ishan, Week 3 Aryan, ... |

### Interface contracts (agree in Week 1 so nobody blocks anybody)

| Producer to Consumer | Contract | Mock until ready |
|---|---|---|
| Ishan to Chaitanya | `/infer` response JSON (section 10) | Chaitanya uses a stub that returns random results |
| Chaitanya to Aryan | OpenAPI spec at `docs/api/openapi.json` | Aryan uses MSW / JSON fixtures |
| Chaitanya to Aryan | `proof-core/test-vectors/*.json` | Aryan's TS port must pass the same vectors |
| Ishan to Chaitanya | `risk.yaml` schema + `classify(record) -> risk` | Default: everything LOW |

---

## 13. Sprint plan

Six 1-week sprints after a setup week. Fill in real dates once the submission deadline is confirmed with the guide.

| Week | Chaitanya | Ishan | Aryan | Milestone / Tag |
|---|---|---|---|---|
| **W0 Setup** | Scaffold on `main`, CI skeleton, docker-compose (pg, redis, minio, hardhat), branch protection, stack vote then ADR-001 | Download NEU-DET, explore classes, write `datasets/README.md` | Frontend shell + routing + auth page mock, choose UI kit | `v0.0.1` "Skeleton" |
| **W1 Foundations** | DB schema + migrations + triggers + seed, JWT + RBAC, `proof-core` SPEC + Python impl + test vectors | Train YOLO baseline, `/infer` stub, then real | Layout, nav by role, Executive dashboard with fixtures, TS `proof-core` port passing vectors | `v0.1.0` "Foundations" |
| **W2 Bind** | Ingest API + event chain writer + device signature verify, `LedgeitAnchor.sol` + tests | EigenCAM heatmaps, severity mapping, edge simulator (signing), weights hash + model register | Live Feed (WS), Inspection Detail + Timeline, Evidence viewer with boxes + heatmap overlay | `v0.2.0` "First sealed inspection" |
| **W3 Anchor + Respond** | Anchor worker (Merkle + batching + retries), deploy to Amoy | Risk engine + `risk.yaml`, replay detection (SHA + pHash), alerts | Browser key gen + signed override/approval flow, Override Center, Model Registry page | `v0.3.0` "On-chain" |
| **W4 Verify** | Verification engine (5 checks), public verify endpoint | Tamper Lab scripts (5 attacks), alert rules round 2 | Verification Center (per-check UI), Blockchain Explorer (Polygonscan links), Risk & Tampering page | `v0.4.0` "Tamper detected" |
| **W5 Report** | E2E tests, hardening, deploy (Render/Railway + Vercel), OpenAPI export | Model KPIs (FP/FN from overrides), 2nd model version, perf numbers | Reports PDF + QR, Public Verify page with in-browser check, Economics page | `v0.5.0` "Audit-ready" |
| **W6 Polish** | Final docs, architecture PNGs, README, release | Demo dataset curation, attack demo rehearsal | UI polish, demo video, screenshots for report/PPT | `v1.0.0` "MVP" |

---

## 14. Git workflow

### Branching model

- **`main`**: protected, always runnable, holds the folder structure. **Nobody pushes directly** after the Week 0 scaffold.
- **Feature branches**: `<name>/<type>/<short-description>`
  - Examples: `chaitanya/feat/proof-core-merkle`, `ishan/feat/yolo-inference`, `aryan/feat/override-center`, `aryan/fix/timeline-sorting`
  - Types: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`
- Merge into `main` only through a **Pull Request** with 1 approval and green CI.
- Keep branches **small and short-lived** (1–3 days). Many small PRs look far more like real development than one giant PR per person.

### Commit messages: Conventional Commits

```
<type>(<scope>): <what changed, imperative>

feat(proof-core): add RFC 6962 style Merkle tree with proofs
fix(web): sort timeline events by seq not timestamp
test(contracts): revert on duplicate root
docs(adr): record tech stack decision
chore(infra): add minio object-lock bucket init
```
Scopes: `api, web, ai, sim, worker, proof-core, contracts, infra, docs, tamper`.

---

### 14.1 One-time setup — Chaitanya only (Week 0)

**Step 1. Add teammates as collaborators** (GitHub UI): Repo → *Settings* → *Collaborators* → *Add people* → Ishan, Aryan (Write access).

**Step 2. Clone and create the skeleton on `main`:**

```bash
git clone https://github.com/frchaitanyaaa/LEDGEIT.git
cd LEDGEIT
git switch main
git pull origin main

# create folder skeleton (empty folders need a .gitkeep to be tracked)
mkdir -p .github/workflows .github/ISSUE_TEMPLATE \
  apps/api/src apps/api/migrations apps/api/tests \
  apps/web/src apps/web/public apps/web/tests \
  services/ai-inspector/app services/ai-inspector/training services/ai-inspector/tests \
  services/edge-simulator/simulator services/anchor-worker/worker services/anchor-worker/tests \
  packages/proof-core/python packages/proof-core/ts packages/proof-core/test-vectors \
  contracts/src contracts/test contracts/scripts contracts/deployments \
  config infra/db infra/minio scripts/tamper-lab datasets \
  docs/adr docs/architecture docs/api docs/progress docs/references docs/team

find . -type d -empty -not -path "./.git/*" -exec touch {}/.gitkeep \;

# move existing reference docs into docs/references
git mv "AI Inspection Integrity & Tamper-Proof Audit Platform.pdf" docs/references/
git mv LEDGEIT.docx LEDGEIT.pdf poster.pdf docs/references/

# put this file in place (copy it from wherever you downloaded it)
cp ~/Downloads/CHAITANYA.md docs/team/CHAITANYA.md
```

**Step 3. Create the root files** (`README.md`, `.gitignore`, `.env.example`, `CLAUDE.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `.github/CODEOWNERS`, `.github/PULL_REQUEST_TEMPLATE.md`). Templates are in sections 15 and 16. Then:

```bash
git status
git add .
git commit -m "chore: scaffold monorepo structure and move reference docs"
git push origin main
git tag -a v0.0.1 -m "Skeleton: folder structure + docs"
git push origin v0.0.1
```

**Step 4. Protect `main`** (GitHub UI): *Settings* → *Branches* (or *Rules → Rulesets*) → add rule for `main`:
- ✅ Require a pull request before merging, with 1 required approval
- ✅ Require status checks to pass (select the CI job after the first CI run)
- ✅ Require conversation resolution
- ✅ Block force pushes · ✅ Restrict deletions
- *Settings → General → Pull Requests*: ✅ Automatically delete head branches

**Step 5. Project board:** *Projects* → *New project* → *Board* → columns `Backlog / This Week / In Progress / In Review / Done`. Create one issue per task from section 13 and set milestones `v0.1.0` … `v1.0.0`.

---

### 14.2 First time — Ishan and Aryan

```bash
git clone https://github.com/frchaitanyaaa/LEDGEIT.git
cd LEDGEIT
git config user.name  "Your Name"
git config user.email "your-github-email@example.com"
git switch main
git pull origin main
```

---

### 14.3 Daily feature workflow (everyone)

```bash
# 1. always start from an up-to-date main
git switch main
git pull origin main

# 2. create your feature branch
git switch -c ishan/feat/yolo-inference

# 3. work... then check what changed
git status
git diff

# 4. stage only your files and commit (small commits, often)
git add services/ai-inspector/
git commit -m "feat(ai): add /infer endpoint returning boxes and confidence"

# 5. push the branch (first push sets upstream)
git push -u origin ishan/feat/yolo-inference
# later pushes on the same branch:
git push
```

**6. Open a Pull Request:** either on GitHub (*Compare & pull request* button) or with the GitHub CLI:

```bash
gh pr create --base main \
  --title "feat(ai): YOLO inference endpoint" \
  --body "Closes #12. Adds /infer with boxes, confidence, severity. Tests: pytest services/ai-inspector/tests"
```

---

### 14.4 Keep your branch up to date with `main`

Do this when `main` moved ahead, or GitHub says "This branch is out-of-date".

**Recommended (safe, no force-push):**
```bash
git switch ishan/feat/yolo-inference
git fetch origin
git merge origin/main
# if conflicts: open the files, fix the <<<<<<< ======= >>>>>>> blocks, then
git add <fixed-file>
git commit
git push
```

**Alternative (cleaner history, only if comfortable):**
```bash
git fetch origin
git rebase origin/main
# on conflict: fix file, then
git add <fixed-file>
git rebase --continue
git push --force-with-lease
```

---

### 14.5 Reviewing a teammate's PR locally

```bash
gh pr checkout 15          # or:
git fetch origin
git switch aryan/feat/override-center

make up                    # run it
# review on GitHub: Files changed -> comment -> Approve / Request changes
git switch main
```

---

### 14.6 After your PR is merged

```bash
git switch main
git pull origin main
git branch -d ishan/feat/yolo-inference          # delete local branch
git push origin --delete ishan/feat/yolo-inference   # only if GitHub didn't auto-delete
git fetch --prune                                # clean stale remote refs
```

---

### 14.7 Release tag at the end of each sprint (Chaitanya)

```bash
git switch main
git pull origin main
git tag -a v0.2.0 -m "Sprint 2: first sealed inspection (ingest + hash chain + heatmaps + live feed)"
git push origin v0.2.0
gh release create v0.2.0 --title "v0.2.0 - First sealed inspection" --notes-file CHANGELOG.md
```

---

### 14.8 "Oops" commands

| Situation | Command |
|---|---|
| Discard changes in one file (not committed) | `git restore path/to/file` |
| Unstage a file | `git restore --staged path/to/file` |
| Undo last commit but keep the changes | `git reset --soft HEAD~1` |
| Fix last commit message (not yet pushed) | `git commit --amend -m "new message"` |
| Park work to switch branches | `git stash push -m "wip"` then later `git stash pop` |
| Committed on `main` by mistake (not pushed) | `git switch -c yourname/feat/x` then `git switch main` then `git reset --hard origin/main` |
| See history | `git log --oneline --graph --all -20` |

> ⚠️ Never `git push --force` to `main`. Never commit `.env`, private keys, dataset images or model weights.

---

## 15. Rules for Claude Code sessions

**Claude Code must NOT run any git or gh commands.** It writes code and then *prints* the exact git commands for the developer to run.

### 15.1 `CLAUDE.md` (put in repo root)

```markdown
# CLAUDE.md — Rules for Claude Code in LEDGEIT

## Hard rules
- NEVER execute git commands (add, commit, push, pull, fetch, checkout, switch, merge, rebase, reset, stash, tag, branch).
- NEVER execute `gh` commands that change anything (pr create/merge, release, issue edit).
- When a change is ready, PRINT the git commands for the developer to run, using:
  - branch: `<name>/<type>/<short-desc>` (e.g. `ishan/feat/replay-detection`)
  - commit: Conventional Commits, e.g. `feat(ai): add pHash replay detection`
  - `git add` only the paths that were changed
- Never commit or create `.env`, private keys, dataset images or model weights.

## Project context
- Read `docs/team/CHAITANYA.md` for architecture, schemas and ownership.
- Integrity rules live in `packages/proof-core/SPEC.md`. Any hashing/canonicalization change
  must update SPEC.md AND `test-vectors/`, and both Python and TS implementations must pass.
- Proof tables are append-only. Never write UPDATE/DELETE against inspections, inspection_events,
  overrides, override_approvals, anchor_items, blockchain_txs, evidence, verifications.
- Decimals in hashed payloads are strings with 4 decimals; timestamps are UTC ISO-8601 with ms + 'Z'.

## Ownership (stay inside your area unless asked)
- Chaitanya: apps/api (core), packages/proof-core, contracts, services/anchor-worker, infra
- Ishan: services/ai-inspector, services/edge-simulator, scripts/tamper-lab, risk + alerts
- Aryan: apps/web, apps/api/src/reports, apps/api/src/economics, apps/api/src/dashboard

## Before finishing a task
- Run the module's tests and linter and show results.
- Update the module README if behavior changed.
- Print: (1) summary of changes, (2) the git commands to run, (3) suggested PR title + body.
```

### 15.2 Hard-block git in Claude Code (`.claude/settings.json`, committed)

```json
{
  "permissions": {
    "deny": [
      "Bash(git:*)",
      "Bash(gh:*)"
    ]
  }
}
```

### 15.3 What a correct Claude Code ending looks like

```
✅ Added pHash replay detection + 6 tests (all passing).

Run these yourself:
  git switch -c ishan/feat/replay-detection
  git add services/ai-inspector/app/replay.py services/ai-inspector/tests/test_replay.py config/risk.yaml
  git commit -m "feat(ai): add pHash-based near-duplicate replay detection"
  git push -u origin ishan/feat/replay-detection

PR title: feat(ai): pHash replay detection
PR body:  Closes #21. Hamming threshold 6 (tuned on NEU-DET val). Raises POSSIBLE_REPLAY alert.
```

---

## 16. "Serious development" checklist

These are the signals a guide or examiner looks at on GitHub to judge whether a project is really being built:

- [ ] **Commit history from all 3 members, spread across weeks.** Small, frequent, Conventional Commits.
- [ ] **PRs with reviews**: every merge has a description, a linked issue and an approving review from a teammate.
- [ ] **Issues + Project board + Milestones** (`v0.1.0` … `v1.0.0`) showing planned vs done.
- [ ] **CI badge green** on README: lint + tests for api, web, ai, contracts, proof-core.
- [ ] **ADRs** in `docs/adr/` (stack choice, chain choice, Merkle spec, key custody, sync vs async ingest).
- [ ] **Shared test vectors** proving Python and TS hashing agree (a strong signal for examiners).
- [ ] **Contract tests + deployed address** on Polygon Amoy in `contracts/deployments/amoy.json` and the README.
- [ ] **One-command run:** `make up && make seed && make demo`.
- [ ] **Weekly progress logs** in `docs/progress/` (what was done, blockers, next).
- [ ] **CHANGELOG.md + tagged releases** each sprint.
- [ ] **Model card**: dataset, metrics, versions, limitations in `services/ai-inspector/MODEL_CARD.md`.
- [ ] **Threat model** in `docs/architecture/threat-model.md` (5 attacks + mitigations + known limits).
- [ ] **Live deployment** link + **demo video** in the README.

### PR template (`.github/PULL_REQUEST_TEMPLATE.md`)

```markdown
## What
<!-- one paragraph -->

## Why
Closes #

## How to test
- [ ] `make up`
- [ ] steps...

## Checklist
- [ ] Tests added/updated and passing
- [ ] No secrets, weights or dataset files committed
- [ ] Docs/README updated if behavior changed
- [ ] If proof-core changed: SPEC.md + test-vectors updated, Python & TS both pass
```

### Minimal CI (`.github/workflows/ci.yml`, Option A flavour)

```yaml
name: CI
on:
  pull_request:
  push:
    branches: [main]

jobs:
  api:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_PASSWORD: postgres, POSTGRES_DB: ledgeit_test }
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U postgres" --health-interval 5s --health-retries 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r apps/api/requirements.txt -r apps/api/requirements-dev.txt
      - run: ruff check apps/api packages/proof-core/python
      - run: pytest apps/api/tests packages/proof-core/python -q
        env: { DATABASE_URL: postgresql://postgres:postgres@localhost:5432/ledgeit_test }

  web:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: npm ci --prefix apps/web
      - run: npm run lint --prefix apps/web
      - run: npm test --prefix apps/web -- --run
      - run: npm run build --prefix apps/web

  contracts:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: npm ci --prefix contracts
      - run: npx --prefix contracts hardhat test

  ai:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r services/ai-inspector/requirements.txt pytest
      - run: pytest services/ai-inspector/tests -q
```

### `infra/docker-compose.yml` starter

```yaml
services:
  postgres:
    image: postgres:16
    environment: { POSTGRES_USER: ledgeit, POSTGRES_PASSWORD: ledgeit, POSTGRES_DB: ledgeit }
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data", "./db/schema.sql:/docker-entrypoint-initdb.d/01-schema.sql"]
  redis:
    image: redis:7
    ports: ["6379:6379"]
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment: { MINIO_ROOT_USER: ledgeit, MINIO_ROOT_PASSWORD: ledgeit123 }
    ports: ["9000:9000", "9001:9001"]
    volumes: ["miniodata:/data"]
  hardhat:
    build: ../contracts
    command: npx hardhat node --hostname 0.0.0.0
    ports: ["8545:8545"]
volumes:
  pgdata:
  miniodata:
```

### `.gitignore` essentials

```
.env
*.pem
**/keys/
datasets/*
!datasets/README.md
services/ai-inspector/models/*.pt
runs/
node_modules/
__pycache__/
.venv/
dist/
build/
contracts/artifacts/
contracts/cache/
```

---

## 17. Final demo script

Roughly 8 minutes, and it tells a story:

1. **Problem (30 s):** show the Kobe Steel / Mitsubishi slide. "Inspection records are just DB rows."
2. **Live line (1 min):** start the edge simulator. The Live Feed fills, cards show PASS/FAIL, confidence and heatmap.
3. **Inspection detail (1 min):** open a FAIL. Show the image with boxes, the EigenCAM heatmap, the model version + weights hash, and the **event timeline** ticking.
4. **Anchoring (1 min):** Blockchain Explorer. LOW records wait in a batch; a CRITICAL one is anchored immediately. Click through to **Polygonscan**.
5. **Override (1 min):** QE overrides FAIL to PASS with a reason, the browser signs it, and it is immediately anchored (HIGH). QM approves.
6. **Attack (2 min):** run the Tamper Lab and flip that FAIL to PASS directly in the database as superuser. Verify: **Check 4 and 5 FAIL. "Verification Failed — Record mismatch detected."** Then run the "smart insider" variant that recomputes all hashes: **check 5 still fails**.
7. **Replay (30 s):** `edge-simulator --replay` sends an old good image and raises a DUPLICATE_EVIDENCE alert.
8. **Report (30 s):** generate a Batch Report PDF, scan the QR with a phone, and the public verify page shows VERIFIED.
9. **Economics (30 s):** real tx fees, cost per inspection, batching vs no batching.

---

## 18. Open decisions

Decide these in the Week 0 meeting and record each as an ADR:

| # | Decision | Options | Default if no consensus |
|---|---|---|---|
| ADR-001 | Tech stack | A / B / C (section 3) | A |
| ADR-002 | Public chain for demo | Polygon Amoy · Ethereum Sepolia | Amoy (lower fees, faster blocks) |
| ADR-003 | Who signs the record | Edge simulator signs vs API signs on behalf of device | Edge simulator signs |
| ADR-004 | Ingest mode | Sync (API calls `/infer`) vs simulator calls `/infer` then posts full record | Sync |
| ADR-005 | Human key custody | Browser IndexedDB vs server-held per-user keys | Browser IndexedDB |
| ADR-006 | Dataset | NEU-DET · GC10-DET · MVTec AD | NEU-DET |
| ADR-007 | Batch sizes/timeouts | Values in `risk.yaml` | 10/60 s MEDIUM · 100/10 min LOW |

---

*Last updated: 12 Oct 2026 · Maintainer: Chaitanya Pagare · Changes to this file go through a PR like everything else.*
