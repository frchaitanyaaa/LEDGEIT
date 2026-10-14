-- What a malicious DBA would type. Run as a superuser: psql "$TAMPER_DATABASE_URL" -v code=INS-... -f edit_record.sql
BEGIN;
SET LOCAL session_replication_role = replica;   -- disables the append-only triggers for this transaction
UPDATE inspections
   SET decision = 'PASS',
       canonical_record = jsonb_set(canonical_record, '{result,decision}', '"PASS"')
 WHERE inspection_code = :'code';
COMMIT;
-- Without replica mode Postgres refuses:  ERROR: LEDGEIT: UPDATE on inspections is forbidden (append-only table)
