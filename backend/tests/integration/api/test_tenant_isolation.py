"""Integration tests for tenant isolation via RLS.

Tests cover:
- API returns only current tenant's data
- Cross-tenant resource access returns 404 (not 403)
- Request body tenant_id is ignored, JWT tenant_id is used
- Direct DB query without tenant context returns empty
"""

# Placeholder - implementation in Phase 4
