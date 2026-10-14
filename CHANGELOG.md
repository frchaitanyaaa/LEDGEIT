# Changelog

All notable changes to this project are documented here. Format: [Keep a Changelog](https://keepachangelog.com/),
versions follow the sprint tags in `docs/team/CHAITANYA.md` §13.

## [Unreleased] — MVP feature-complete

### Added
- **proof-core**: SPEC v1 (RFC 8785, SHA-256, per-line hash chain, RFC 6962-style Merkle, Ed25519); Python + TypeScript
  implementations; shared test vectors checked in CI.
- **contracts**: `LedgeitAnchor.sol` (append-only roots), 7 Hardhat tests, deploy scripts, committed ABI.
- **api**: schema with append-only triggers and least-privilege role; JWT + 5-role RBAC; edge-first ingest with full
  re-validation; risk engine; replay detection; alerts + rules; signed review/override/approval/dispute; 5-check
  verification; public verify (rate-limited); PDF reports with QR; economics; dashboard KPIs; OpenAPI export.
- **anchor worker**: risk-adaptive Merkle batching, retries with backoff, fee accounting, auto-deploy on Hardhat.
- **ai-inspector**: stub (classical CV) and YOLOv8 + EigenCAM backends, severity mapping, heatmaps, model manifest,
  NEU-DET preparation and training scripts, model card.
- **edge-simulator**: synthetic steel frames, device signing, replay / near-replay attacks.
- **tamper lab**: edit-decision, swap-image, delete-event, smart-insider.
- **web**: 11-page dashboard, in-browser signing, live feed, public verification with independent chain check.
- **ops**: docker-compose, `scripts/dev.sh` (no Docker), `make demo`, CI for every package, threat model, ADR-001..009.
