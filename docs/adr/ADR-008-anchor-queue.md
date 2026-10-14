# ADR-008: Durable anchor queue in PostgreSQL

**Status:** Accepted · 2026-10-14

## Context
The original plan used Redis + Celery to hand events from the API to the anchor worker. A Redis message can be lost between the DB commit and the enqueue, leaving an event that is never anchored.

## Decision
The API inserts into `anchor_queue` **in the same transaction** as the event. The anchor worker polls `anchor_queue` (`FOR UPDATE SKIP LOCKED`), applies the risk-window flush rules and writes `anchor_batches`/`anchor_items`. Redis is not required for the MVP.

## Consequences
Exactly-once enqueue, one fewer service, simpler demo. Throughput is far above MVP needs. The live feed is served by the API's in-process WebSocket hub.
