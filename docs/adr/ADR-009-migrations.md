# ADR-009: Plain-SQL numbered migrations

**Status:** Accepted · 2026-10-14

Migrations are numbered SQL files in `apps/api/migrations/` applied by `python -m ledgeit_api.db.migrate`, which tracks applied versions in `schema_migrations`. Triggers, enums and grants are expressed directly in SQL (Alembic autogenerate does not handle triggers well). `infra/db/schema.sql` is generated from the migrations as a single reference copy.
