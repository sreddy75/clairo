# Data Model: Infra & Launch Polish

**Date**: 2026-04-06

## No Schema Changes Required

This spec is infrastructure-only. No new database tables, columns, or migrations.

## Database Configuration Change

### Production Role (non-superuser)

A new database role `clairo_app` must be created in the production database. This role has DML privileges but NOT superuser or bypassrls privileges, ensuring Row-Level Security policies are enforced.

| Role | Privileges | RLS | Purpose |
|------|-----------|-----|---------|
| `postgres` (superuser) | ALL | Bypassed | Migrations only (alembic upgrade head) |
| `clairo_app` | SELECT, INSERT, UPDATE, DELETE | Enforced | Application runtime |

The application's `DATABASE_URL` in production must use the `clairo_app` role, not the superuser.
