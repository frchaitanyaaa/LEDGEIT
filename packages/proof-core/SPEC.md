# LEDGEIT proof-core specification (v1)

This document is the **contract** between every LEDGEIT component (API, anchor worker, edge simulator,
web verifier). Implementations live in `python/` and `ts/`; both MUST pass every file in
`test-vectors/`. Changing anything here requires regenerating the vectors
(`python packages/proof-core/scripts/gen_vectors.py`) and updating both implementations.

All hashes are **SHA-256**, encoded as **lowercase hex** (64 chars) unless stated otherwise.

---

## 1. Canonicalization

Canonical bytes = **RFC 8785 JSON Canonicalization Scheme (JCS)** of the value, encoded UTF-8.

- Object keys sorted by UTF-16 code units; no insignificant whitespace.
- **Only integers are allowed as JSON numbers** (and only within ±2^53−1). Fractional values
  (confidence, prices…) MUST be encoded as **decimal strings**. Implementations MUST reject floats
  so formatting never differs between languages.
- Confidence/probability strings have **exactly 4 decimal places**: `"0.9640"`.
- Timestamps are **UTC ISO-8601 with milliseconds and `Z`**: `"2026-10-20T10:31:02.120Z"`.
- `null`, `true`, `false`, arrays and nested objects are allowed.

`hash_json(v) = SHA256(JCS(v))`

## 2. Hashes

| Name | Definition |
|---|---|
| `evidence_sha256` | `SHA256(raw image bytes exactly as uploaded)` — never re-encode before hashing |
| `heatmap_sha256` | `SHA256(heatmap PNG bytes)` |
| `weights_sha256` | `SHA256(model weights file bytes)` |
| `record_hash` | `hash_json(inspection proof record)` (§5) |
| `payload_hash` | `hash_json(event payload)` |
| `event_hash` | `hash_json(event header)` (§3) |

## 3. Event hash chain (per production line)

Event header (exactly these keys):

```json
{
  "line": "LINE-A",
  "seq": 42,
  "event_type": "RECORD_CREATED",
  "actor": {"type": "DEVICE", "id": "CAM-A-01"},
  "payload_hash": "<hex>",
  "prev_event_hash": "<hex>",
  "created_at": "2026-10-20T10:31:02.120Z"
}
```

- `line` is the production line **code**. `actor.type` ∈ `DEVICE | USER | SYSTEM`; `actor.id` is the
  device code, user employee code, or `null` for SYSTEM.
- `event_hash = hash_json(header)`.
- `seq` starts at **1** for each line and increases by exactly 1. A gap means a deleted event.
- The first event's `prev_event_hash` is the line genesis hash:
  `genesis(line) = SHA256(UTF8("LEDGEIT-GENESIS-v1:" + line))`.
- Every later event's `prev_event_hash` equals the previous event's `event_hash`.

Event types: `INSPECTED, EVIDENCE_HASHED, RECORD_CREATED, ANCHOR_QUEUED, ANCHORED, REVIEWED,
OVERRIDDEN, APPROVED, RELEASED, REJECTED, DISPUTE_RAISED, DISPUTE_RESOLVED, VERIFIED, TAMPER_DETECTED`.

## 4. Merkle tree (RFC 6962 style, domain separated)

```
leaf(e)    = SHA256(0x00 || bytes(e.event_hash))      # bytes = 32 raw bytes from hex
node(l, r) = SHA256(0x01 || l || r)
```

- Leaves are in batch order (ascending event id).
- At each level, pair nodes left to right. If a level has an **odd** count, the last node is
  **promoted unchanged** to the next level (no duplication).
- A one-leaf tree's root is the leaf hash itself. Empty trees are invalid.
- Proof for leaf *i*: list of siblings from bottom to top, each `{"hash": "<hex>", "side": "L"|"R"}`
  where `side` is the side **the sibling** sits on. Promoted levels contribute no entry.
- Verification: `h = leaf; for p in proof: h = node(p.hash, h) if p.side == "L" else node(h, p.hash)`;
  valid iff `h == root`.

## 5. Inspection Proof Record — `ledgeit.inspection.v1`

```json
{
  "schema": "ledgeit.inspection.v1",
  "inspection_id": "<uuid>",
  "inspection_code": "INS-20261020-A01-000123",
  "unit_serial": "UNIT-A-000123",
  "batch_code": "BATCH-2026-10-20-A",
  "line": "LINE-A",
  "device": "CAM-A-01",
  "inspected_at": "2026-10-20T10:31:02.120Z",
  "evidence": {"sha256": "<hex>", "phash": "<16 hex>", "mime": "image/jpeg", "bytes": 48211},
  "model": {"name": "ledgeit-defect-yolo", "version": "1.2.0", "weights_sha256": "<hex>"},
  "result": {
    "decision": "PASS|FAIL",
    "defect_class": "scratches|null",
    "severity": "NONE|MINOR|MAJOR|CRITICAL",
    "confidence": "0.9640",
    "boxes": [{"x1": 34, "y1": 80, "x2": 120, "y2": 140, "cls": "scratches", "conf": "0.9640"}]
  },
  "explanation": {"method": "EigenCAM", "heatmap_sha256": "<hex>|null", "summary": "..."},
  "prev_record_hash": "<hex>"
}
```

- `prev_record_hash` is the `record_hash` of the **same device's** previous record, or 64 zeros.
- Box coordinates are integer pixels.

## 6. Signed payloads

### 6.1 What is signed

All signatures are **Ed25519** over the **ASCII bytes of the 64-char lowercase hex digest**:

| Signer | Message |
|---|---|
| Device | `record_hash` |
| Human (review / override / approval / dispute) | `hash_json(payload)` |

Keys and signatures are **standard base64** (with padding). Public key = 32 bytes, signature = 64 bytes,
private key material is the 32-byte seed.

### 6.2 `ledgeit.override.v1`

```json
{
  "schema": "ledgeit.override.v1",
  "inspection_id": "<uuid>",
  "record_hash": "<hex>",
  "original": {"decision": "FAIL", "confidence": "0.6200"},
  "new_decision": "PASS",
  "reason_code": "FALSE_POSITIVE|FALSE_NEGATIVE|LIGHTING|SENSOR_FAULT|OTHER",
  "reason_text": "...",
  "reviewed_evidence": ["<evidence sha256>", "<heatmap sha256>"],
  "operator": {"employee_code": "QE-0042", "public_key": "<base64>"},
  "signed_at": "2026-10-20T10:32:14.502Z"
}
```

### 6.3 `ledgeit.review.v1` (accept AI decision)

```json
{"schema": "ledgeit.review.v1", "inspection_id": "<uuid>", "record_hash": "<hex>",
 "accepted_decision": "FAIL", "comment": "...", "reviewer": {"employee_code": "...", "public_key": "..."},
 "signed_at": "..."}
```

### 6.4 `ledgeit.approval.v1` (QM approves/rejects an override)

```json
{"schema": "ledgeit.approval.v1", "override_payload_hash": "<hex>", "inspection_id": "<uuid>",
 "approved": true, "comment": "...", "approver": {"employee_code": "...", "public_key": "..."},
 "signed_at": "..."}
```

### 6.5 `ledgeit.dispute.v1`

```json
{"schema": "ledgeit.dispute.v1", "inspection_id": "<uuid>", "record_hash": "<hex>",
 "action": "RAISE|RESOLVE", "resolution": "RELEASED|REJECTED|null", "reason_text": "...",
 "actor": {"employee_code": "...", "public_key": "..."}, "signed_at": "..."}
```

## 7. Event payloads written by the API

| Event | Actor | Payload |
|---|---|---|
| `INSPECTED` | DEVICE | `{"inspection_id", "unit_serial", "decision", "confidence"}` |
| `EVIDENCE_HASHED` | DEVICE | `{"inspection_id", "evidence_sha256", "heatmap_sha256"}` |
| `RECORD_CREATED` | DEVICE | `{"inspection_id", "record_hash", "device_signature"}` |
| `REVIEWED` / `OVERRIDDEN` / `APPROVED` / `DISPUTE_*` | USER | `{"inspection_id", "payload": <signed payload>, "payload_hash", "signature"}` |
| `RELEASED` / `REJECTED` | SYSTEM | `{"inspection_id", "final_decision", "cause_event_hash"}` |

Every event is a Merkle leaf and is anchored according to its inspection's risk level (human and SYSTEM
events are always HIGH).

`ANCHORED` and `ANCHOR_QUEUED` exist in the enum but are **never appended to the chain**: an `ANCHORED`
event would itself need anchoring (infinite regress). Anchor state is kept in `anchor_batches`,
`anchor_items` and `blockchain_txs`, which are verified independently by check 5.

## 8. Verification checks

1. **Evidence** — stored image/heatmap bytes hash to the values in the record.
2. **Model** — `record.model.weights_sha256` equals the registry entry and the model was `APPROVED` at `inspected_at`.
3. **Signatures** — device signature over the recomputed `record_hash`; every human signature valid and its key registered to that user.
4. **Event chain** — stored columns match the canonical record; recomputed `record_hash` matches;
   every event of the line segment recomputes to its `event_hash`, links via `prev_event_hash`, and `seq` has no gaps.
5. **Anchor** — for each event, recompute the leaf from the *recomputed* event hash, walk the stored proof
   and require the root to exist on-chain with block time ≥ `inspected_at` − 5 min clock skew.
   Not-yet-anchored ⇒ `PENDING`.

Result: `VERIFIED` (all PASS) · `FAILED` (any FAIL) · `PENDING_ANCHOR` (1–4 PASS, 5 PENDING).
