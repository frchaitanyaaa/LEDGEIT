# proof-core

The integrity contract for LEDGEIT. **[SPEC.md](SPEC.md) is normative**; the code implements it.

| Path | What |
|---|---|
| `SPEC.md` | Canonicalization, hashes, hash chain, Merkle tree, signatures, record formats, verification checks |
| `python/ledgeit_proof` | Reference implementation (used by API, anchor worker, simulator, tamper lab) |
| `ts/src` | TypeScript port (used by the web app's in-browser verifier and signer) |
| `test-vectors/` | Shared JSON vectors. Both implementations must reproduce every value |
| `scripts/gen_vectors.py` | Regenerates the vectors from the Python reference |

```bash
# Python
pip install -e packages/proof-core/python && pytest packages/proof-core/python
# TypeScript
cd packages/proof-core/ts && npm install && npx vitest run
```

Changing hashing or canonicalization? Update `SPEC.md` → run `gen_vectors.py` → make both implementations pass → note it in the PR.
