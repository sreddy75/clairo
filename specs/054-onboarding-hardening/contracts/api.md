# API Contracts: Onboarding & Core Hardening

**Branch**: `054-onboarding-hardening` | **Date**: 2026-04-05

## No New API Endpoints

This spec does not add new endpoints. All existing endpoints are verified to work correctly through integration tests.

## Endpoints Under Test

### BAS Workflow (verified end-to-end)

| Method | Path | Test Coverage |
|---|---|---|
| POST | /api/v1/bas/sessions | Session creation |
| POST | /api/v1/bas/sessions/{id}/suggestions/generate | AI tax code suggestions |
| POST | /api/v1/bas/suggestions/{id}/approve | Suggestion approval |
| POST | /api/v1/bas/sessions/{id}/calculate | GST calculation |
| POST | /api/v1/bas/sessions/{id}/approve | Session approval |
| GET | /api/v1/bas/sessions/{id}/export/pdf | PDF export |
| GET | /api/v1/bas/sessions/{id}/export/csv | CSV export |

### Tax Planning Workflow (verified end-to-end)

| Method | Path | Test Coverage |
|---|---|---|
| POST | /api/v1/tax-planning/plans | Plan creation |
| POST | /api/v1/tax-planning/plans/{id}/chat | AI chat |
| POST | /api/v1/tax-planning/plans/{id}/analyze | Multi-agent analysis |
| GET | /api/v1/tax-planning/plans/{id}/export/pdf | PDF export |

### Portal Flow (verified end-to-end)

| Method | Path | Test Coverage |
|---|---|---|
| POST | /api/v1/portal/clients/{id}/invite | Send invitation |
| POST | /api/v1/client-portal/auth/verify | Magic link verification |
| GET | /api/v1/client-portal/dashboard | Portal dashboard |
| GET | /api/v1/client-portal/tax-plan | Shared tax plan |

### Tenant Isolation (verified per-endpoint)

All endpoints above are tested with two tenants to verify zero cross-tenant data leakage.
