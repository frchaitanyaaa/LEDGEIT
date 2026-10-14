# ADR-003: Who signs the inspection record

**Status:** Accepted · 2026-10-14

## Decision
The **edge device** (simulator instance) holds an Ed25519 private key and signs `record_hash`. Its public key is registered in `devices`. The API never holds device private keys.

## Consequences
An insider with DB access cannot forge a new valid record without the device key. The Tamper Lab "smart insider" attack assumes a *compromised device key* to show that even then the on-chain anchor (check 5) catches the edit.
