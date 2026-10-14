# ADR-007: Batch sizes and timeouts

**Status:** Accepted · 2026-10-14

Defaults in `config/risk.yaml`: MEDIUM batches at 10 records or 60 s; LOW at 100 records or 10 min; HIGH anchored immediately as a single-leaf tree. The doc's production figure (1 tx per 1,000 routine records) is a config change, not a code change.
