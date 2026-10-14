# anchor-worker

Consumes the durable `anchor_queue` (ADR-008), builds domain-separated Merkle batches per risk level
(`config/risk.yaml` → `anchoring`), submits roots to `LedgeitAnchor`, records receipts and fees in
`blockchain_txs`, retries with exponential backoff (FAILED + `MISSING_ANCHOR` alert after `max_attempts`),
and runs periodic alert rules (delayed approval, high override rate, missing anchor).

```bash
python -m worker                 # from this folder (or: python -m ledgeit_api.anchoring.run)
python -m worker --once --flush  # anchor everything pending right now (demo helper)
```

With `CHAIN=local` the worker deploys the contract to the Hardhat node on first start and writes
`contracts/deployments/localhost.json`. A restarted Hardhat node loses its state — old records will then
fail check 5 (anchor). Use `CHAIN=amoy` for anything that must survive.

The code lives in `apps/api/src/ledgeit_api/anchoring/` so it shares DB access and proof-core with the API;
tests are in `apps/api/tests/test_anchoring.py`.
