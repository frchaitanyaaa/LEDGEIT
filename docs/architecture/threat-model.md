# Threat model

**Asset:** the truth of "what the AI saw, which model decided, what it decided, and what humans did about it".
**Adversaries:** a malicious insider with database access (DBA), a storage administrator, a compromised edge
device, someone replaying old images, a forger of human approvals, and LEDGEIT's own operators.

## Controls (defence in depth)

| Layer | Control | Where |
|---|---|---|
| Edge | Device Ed25519 key signs `record_hash`; API holds only public keys | `simulator/device.py`, ingest |
| Ingest | Re-hashes evidence + heatmap, recomputes pHash, checks model weights hash + approval, device signature, per-device `prev_record_hash` | `inspections/ingest.py` |
| Record | RFC 8785 canonical JSON, decimals as strings, timestamps with ms + Z | `packages/proof-core/SPEC.md` |
| History | Per-line hash chain (`prev_event_hash`, gapless `seq`), `line_heads` | `services/events.py` |
| DB | Append-only + no-truncate triggers on proof tables; least-privilege `ledgeit_app` role; immutable model identity | migrations 0001/0002 |
| Storage | Content-addressed keys; MinIO Object Lock (GOVERNANCE, 365 d) keeps original versions | `infra/minio/init.sh` |
| Ledger | Merkle roots on `LedgeitAnchor` (no update/delete function); risk-adaptive batching | `contracts/`, anchor worker |
| Humans | Browser-held Ed25519 keys, append-only key history, signed JCS payloads, signed_at skew window, separation of duties | `human/router.py`, `web/src/lib/keys.ts` |
| Detection | 5-check verification that recomputes instead of trusting stored hashes; replay detection; alert rules | `verification/engine.py` |
| Independence | Public page re-verifies proofs and queries the chain directly from the browser | `web/src/lib/chainVerify.ts` |

## Attacks and outcomes (all exercised by tests and `make demo`)

| # | Attack | Needs | Detected by |
|---|---|---|---|
| T1 | Edit decision in DB row + stored JSON | DB superuser | Check 3 (device signature) + check 4 (row ≠ record, `RECORD_CREATED` mismatch) |
| T2 | Swap evidence image in storage | storage admin (and bypassing Object Lock) | Check 1 |
| T3 | Delete an event (e.g. `REJECTED`) | DB superuser | Check 4 (seq gap, or line-head mismatch for the newest event) |
| T4 | Replay an old good image for a new unit | any device | Ingest: `DUPLICATE_EVIDENCE` (exact) / `POSSIBLE_REPLAY` (pHash ≤ 6) → HIGH risk |
| T5 | Smart insider: edit, re-sign with a stolen device key, recompute every hash, chain link, Merkle proof and root | DB superuser + device key | **Check 5 only** — the rebuilt root is not on-chain |
| T6 | Forge a human override | DB access | Check 3: no valid signature from a registered user key |
| T7 | Backdate a decision with an unapproved model | device | Check 2 (model not APPROVED at `inspected_at`) + `MODEL_MISMATCH` alert |
| T8 | Hide anchoring (drop queue rows / batches) | DB superuser | Check 5: "not anchored and not queued"; `MISSING_ANCHOR` alert rule |

## Known limits (say these in the viva)

1. **Before-anchor window.** Between ingest and anchoring (≤ 60 s MEDIUM, ≤ 10 min LOW by default) a superuser
   who *also* holds the device key could rewrite a record undetectably. HIGH-risk events close this to ~1 s.
   Production: shorter LOW windows or a signed receipt returned to the device.
2. **Key custody.** Browser IndexedDB keys and file-based device keys are MVP choices (ADR-005); production
   would use WebAuthn / smart cards and TPM/HSM-backed device keys.
3. **Device public-key substitution.** A DBA could swap a device's public key and re-sign; checks 1–4 pass,
   but check 5 still fails because the record hash changed. Registering device keys on-chain would also fix it.
4. **Deletion of whole inspections** including all their events leaves a seq gap that is detected only when a
   neighbouring record or the whole line is verified (`POST /verify/batch`). A periodic full-line audit job is a
   cheap addition.
5. **Local chain.** `CHAIN=local` (Hardhat) is controlled by the operator and is reset on restart; the
   tamper-evidence claim holds only on a public chain (`CHAIN=amoy`).
6. **Garbage in.** LEDGEIT proves a record was not changed after capture; it cannot prove the camera or model
   were right. Model approval, drift monitoring and human review address that separately.
