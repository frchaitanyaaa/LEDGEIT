# ADR-002: Public chain for the demo

**Status:** Accepted · 2026-10-14

## Decision
- `CHAIN=local`: Hardhat node (chain id 31337) for development, tests and offline demos.
- `CHAIN=amoy`: Polygon Amoy testnet (chain id 80002) for the final demo so examiners can open transactions on Polygonscan.
- `CHAIN=none`: anchoring disabled (verification reports `PENDING_ANCHOR`).

## Consequences
Amoy needs a funded wallet; the key is provided via `ANCHOR_PRIVATE_KEY` and never committed. Deployed addresses are committed in `contracts/deployments/<network>.json`.
