# Tamper Lab

Attacks a running LEDGEIT database the way a malicious DBA or insider would, so the demo can show
verification catching each one. Requires a **superuser** connection (`TAMPER_DATABASE_URL`) because the
first thing an attacker does is switch off the append-only triggers (`session_replication_role = replica`).

| # | Attack | Command | Expected verification |
|---|---|---|---|
| T1 | Flip FAIL→PASS in the DB | `python scripts/tamper-lab/tamper_lab.py edit-decision INS-…` | **FAILED** — check 3 (device signature no longer matches) + check 4 (row ≠ sealed record, `RECORD_CREATED` mismatch) |
| T2 | Swap the stored image | `… swap-image INS-…` | **FAILED** — check 1 (bytes hash ≠ record) |
| T3 | Delete the newest event (e.g. `REJECTED`) | `… delete-event INS-…` | **FAILED** — check 4 (seq gap / line head mismatch) |
| T4 | Replay an old good image | `python -m simulator --replay N` | `DUPLICATE_EVIDENCE` alert at ingest, record forced to HIGH risk |
| T5 | Smart insider: edit + re-sign (compromised device key) + recompute *every* hash, proof and root | `… smart-insider INS-…` | **FAILED — only check 5**: the rebuilt Merkle root is not on-chain. *The DB can be rewritten; the chain cannot.* |

`edit_record.sql` / `delete_event.sql` show the same attacks as raw SQL for the presentation.

> Defence in depth note: in production the API connects as `ledgeit_app` (INSERT/SELECT only on proof
> tables, see migration 0002) and MinIO Object Lock keeps the original evidence version, so T1–T3 also
> need superuser / storage-admin credentials. Verification does not rely on either control.
