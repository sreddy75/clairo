# Repository Tenant ID Audit

**Date**: 2026-04-05
**Spec**: 054-onboarding-hardening

## Summary

Audited all 16 repository files across the codebase. Found **16 HIGH-risk methods** (PK-only queries on tenant-scoped tables without tenant_id filter) and a systemic pattern of ~100+ MEDIUM-risk methods using `connection_id` as an indirect tenant scope.

## Risk Assessment

### Mitigating Factors

1. **RLS policies now active on all 16 newer tables** (spec 054 migration with FORCE)
2. **RLS policies active on all older tables** (migrations 001-027)
3. **connection_id is globally unique** — if obtained through a tenant-filtered query, downstream queries by connection_id are safe
4. **PK-only queries are typically called from service layer** which received the PK from an already-tenant-filtered list/search

### Residual Risk

RLS enforcement depends on the DB connection NOT being a superuser. In production (non-superuser app role), RLS provides the safety net. In development (superuser role), these gaps could leak data if a connection_id from another tenant is passed.

## HIGH-Risk Findings (16 methods)

| # | Module | Method | Line | Table |
|---|--------|--------|------|-------|
| 1 | bas | `get_period` | 64 | bas_periods |
| 2 | bas | `get_session` | 133 | bas_sessions |
| 3 | bas | `get_adjustment` | 316 | bas_adjustments |
| 4 | bas | `delete_adjustment` | 338 | bas_adjustments |
| 5 | bas | `update_request_status` | 921 | classification_requests |
| 6 | portal | `get_with_details` | 386 | document_requests |
| 7 | tax_planning | `get_next_sort_order` | 161 | tax_scenarios |
| 8 | tax_planning | `get_recent_messages` | 203 | tax_plan_messages |
| 9 | tax_planning | `set_current` | 315 | tax_plan_analyses |
| 10 | xero | `get_by_id` | 212 | xero_connections |
| 11 | xero | `update` | 300 | xero_connections |
| 12 | xero | `disconnect` | 362 | xero_connections |
| 13 | xero | `soft_delete` | 767 | xero_clients |
| 14 | xero | `list_all_for_tenant` | 773 | xero_clients |
| 15 | quality | `dismiss_issue` | 310 | quality_issues |
| 16 | quality | `get_issue_by_id` | 335 | quality_issues |

## Systemic Pattern: connection_id-only filtering

~100+ methods across bas, xero, portal, quality, aggregation, payroll modules query by `connection_id` without explicit `tenant_id`. This is architecturally acceptable because `connection_id` is a UUID obtained through prior tenant-filtered queries. RLS provides defense-in-depth.

## Intentional Cross-Tenant Methods (safe by design)

- `BASRepository.get_all_unlodged_sessions_by_tenant` — scheduled deadline notifications
- `PortalInvitationRepository.expire_old_invitations` — maintenance
- `DocumentRequestRepository.get_pending_reminders` — scheduled reminders
- `PortalDocumentRepository.get_pending_scans` — virus scan queue
- `BulkRequestRepository.get_pending` — task queue
- `OnboardingRepository.list_incomplete` — drip email processing
- `XeroConnectionRepository.find_by_xero_tenant_id` — webhook processing
- `AdminRepository` (all methods) — admin dashboard

## Modules Fully Safe (100% tenant_id filtered)

- `feedback/repository.py` — 10/10 methods safe
- `clients/repository.py` — 5/5 methods safe
- `dashboard/repository.py` — 3/3 methods safe
- `admin/repository.py` — 14/14 methods safe (intentional cross-tenant for admin)
- `tax_planning/repository.py: TaxPlanRepository` — all methods safe
- `tax_planning/repository.py: ImplementationItemRepository` — all methods safe

## Recommendation

The combination of RLS policies (now active with FORCE on all tables) + the connection_id indirection pattern provides adequate security for beta launch. The 16 HIGH-risk PK-only methods should be reviewed in a future hardening pass to add explicit tenant_id filters as defense-in-depth, but they are not launch-blocking with RLS active.
