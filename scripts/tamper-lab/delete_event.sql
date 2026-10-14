-- Delete the newest event of an inspection (e.g. a REJECTED decision). Superuser only.
BEGIN;
SET LOCAL session_replication_role = replica;
WITH ev AS (
  SELECT e.id FROM inspection_events e JOIN inspections i ON i.id = e.inspection_id
   WHERE i.inspection_code = :'code' ORDER BY e.seq DESC LIMIT 1)
, q AS (DELETE FROM anchor_queue WHERE event_id IN (SELECT id FROM ev))
, a AS (DELETE FROM anchor_items WHERE event_id IN (SELECT id FROM ev))
, s AS (UPDATE inspection_status SET last_event_id = NULL WHERE last_event_id IN (SELECT id FROM ev))
DELETE FROM inspection_events WHERE id IN (SELECT id FROM ev);
COMMIT;
