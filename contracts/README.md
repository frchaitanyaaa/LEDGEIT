# contracts — `LedgeitAnchor`

Append-only on-chain registry of Merkle roots. No update or delete function exists (a test asserts this).

```bash
npm install
npx hardhat test            # 7 tests incl. gas snapshot (~72k gas per anchor)
npm run node                # local chain on :8545 (chain id 31337)
npm run deploy:local        # writes deployments/localhost.json
CHAIN=amoy AMOY_PRIVATE_KEY=0x... npm run deploy:amoy   # writes deployments/amoy.json (commit it)
```

- Compiler: `solc` 0.8.24 from npm (solcjs), so no compiler download is needed.
- `abi/LedgeitAnchor.json` holds the ABI + bytecode used by the Python anchor worker and the API
  (which can also self-deploy to a fresh local Hardhat node). Regenerate after changing the contract:
  `node -e '...'` — see `npm run export-abi`.
