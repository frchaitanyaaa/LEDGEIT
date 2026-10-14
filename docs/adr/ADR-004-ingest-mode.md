# ADR-004: Ingest mode — edge-first

**Status:** Accepted · 2026-10-14

## Context
Option 1 (sync): API receives an image, calls `/infer`, builds the record, returns the hash for the device to sign (two round trips). Option 2 (edge-first): the device calls `/infer`, builds and signs the full record, then posts image + heatmap + record + signature in one request.

## Decision
Edge-first. Real AI cameras (e.g. Cognex) run inference on the edge, so the device attesting to "what the AI saw and decided" matches reality. The API **re-validates everything** it can: evidence and heatmap SHA-256 against uploaded bytes, pHash recomputed, model registered and approved with matching `weights_sha256`, device registered and active, signature valid, `prev_record_hash` equal to the device's last record.

## Consequences
One request per inspection; ingest is idempotent on `record_hash`. The device keeps a per-device record chain (`prev_record_hash`) and can resync via `GET /devices/{code}/head`.
