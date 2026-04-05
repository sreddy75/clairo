# Data Model: Onboarding & Core Hardening

**Branch**: `054-onboarding-hardening` | **Date**: 2026-04-05

## No New Tables or Columns

This spec does not create new tables or modify existing schemas. The work is:
1. Adding RLS policies to 16 existing tables
2. Writing integration tests
3. Improving frontend empty states

## RLS Policy Additions

Single Alembic migration adding Row-Level Security to all tenant-scoped tables created after February 2026.

### Tables Receiving RLS Policies

| Table | Source Migration | tenant_id nullable? |
|---|---|---|
| `portal_invitations` | 033_spec_030_client_portal | No |
| `portal_sessions` | 033_spec_030_client_portal | No |
| `document_request_templates` | 033_spec_030_client_portal | Yes (NULL = system templates) |
| `bulk_requests` | 033_spec_030_client_portal | No |
| `document_requests` | 033_spec_030_client_portal | No |
| `portal_documents` | 033_spec_030_client_portal | No |
| `tax_code_suggestions` | 20260314_add_tax_code_resolution | No |
| `tax_code_overrides` | 20260314_add_tax_code_resolution | No |
| `classification_requests` | 20260315_spec_047_client_classification | No |
| `client_classifications` | 20260315_spec_047_client_classification | No |
| `feedback_submissions` | 20260315_add_feedback_tables | No |
| `tax_plans` | 20260330_049_add_tax_planning_tables | No |
| `tax_scenarios` | 20260330_049_add_tax_planning_tables | No |
| `tax_plan_messages` | 20260330_049_add_tax_planning_tables | No |
| `tax_plan_analyses` | 20260403_add_tax_plan_analyses | No |
| `implementation_items` | 20260403_add_tax_plan_analyses | No |

### Special Case: document_request_templates

This table has a nullable `tenant_id` — NULL rows are system-provided templates. Two policies needed:
1. Standard tenant isolation for tenant-owned templates
2. Allow-read policy for system templates (`tenant_id IS NULL`)

### Policy SQL Pattern (per table)

```sql
ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;

CREATE POLICY <table>_tenant_isolation ON <table>
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
```

### RLS Verification Checklist

After migration, every table with `tenant_id` should satisfy:
- `SELECT * FROM <table>` with no tenant context returns 0 rows
- `SELECT * FROM <table>` with tenant A context returns only tenant A rows
- `INSERT INTO <table>` with tenant A context and tenant B's `tenant_id` is blocked by `WITH CHECK`
