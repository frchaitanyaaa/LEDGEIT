-- Retry bookkeeping for the anchor worker (backoff between attempts).
ALTER TABLE anchor_batches ADD COLUMN last_attempt_at TIMESTAMPTZ;
ALTER TABLE anchor_batches ADD COLUMN submitted_tx_hash CHAR(66);
CREATE INDEX idx_anchor_batches_status ON anchor_batches(status, created_at);
