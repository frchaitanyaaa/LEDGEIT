-- Least-privilege application role (CHAITANYA.md §5.9). The API/worker should connect as
-- ledgeit_app; migrations and the Tamper Lab use the owner/superuser.
-- Dev password below; override in production with: ALTER ROLE ledgeit_app PASSWORD '...';
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ledgeit_app') THEN
    CREATE ROLE ledgeit_app LOGIN PASSWORD 'ledgeit_app';
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO ledgeit_app;
GRANT SELECT, INSERT ON inspections, inspection_events, overrides, override_approvals,
      anchor_items, blockchain_txs, evidence, verifications, user_keys TO ledgeit_app;
GRANT SELECT, INSERT, UPDATE ON inspection_status, anchor_batches, anchor_queue, alerts, line_heads,
      ai_models, users, devices, batches, reports, cost_entries TO ledgeit_app;
GRANT SELECT, INSERT ON plants, production_lines, products TO ledgeit_app;
GRANT SELECT ON schema_migrations TO ledgeit_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ledgeit_app;
