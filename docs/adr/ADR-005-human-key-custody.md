# ADR-005: Human key custody

**Status:** Accepted · 2026-10-14

## Decision
Browser generates an Ed25519 keypair (`@noble/ed25519`) and stores the private key in IndexedDB. The public key is registered via `POST /auth/keys` into the append-only `user_keys` table, so signatures made with an older key remain verifiable after rotation. Signed payloads embed the signer's public key; verification checks it belongs to that user.

## Consequences
MVP honesty note: a browser-held key is weaker than a smart card/HSM. Production would use WebAuthn/HSM. CLI tools (demo scripts) can register their own keys for scripted overrides.
