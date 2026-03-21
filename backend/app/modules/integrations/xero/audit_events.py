"""Xero integration audit event definitions.

Defines audit events for:
- OAuth flow
- Connection lifecycle
- Token operations
- Rate limiting
"""

XERO_AUDIT_EVENTS = {
    "integration.xero.oauth_started": {
        "category": "integration",
        "description": "User initiated Xero OAuth flow",
        "retention_years": 5,
    },
    "integration.xero.connected": {
        "category": "integration",
        "description": "Successfully connected Xero organization",
        "retention_years": 7,
    },
    "integration.xero.disconnected": {
        "category": "integration",
        "description": "Disconnected Xero organization",
        "retention_years": 7,
    },
    "integration.xero.token_refreshed": {
        "category": "integration",
        "description": "Automatically refreshed Xero access token",
        "retention_years": 5,
    },
    "integration.xero.token_refresh_failed": {
        "category": "integration",
        "description": "Failed to refresh Xero access token",
        "retention_years": 5,
    },
    "integration.xero.rate_limited": {
        "category": "integration",
        "description": "Hit Xero API rate limit",
        "retention_years": 5,
    },
    "integration.xero.authorization_required": {
        "category": "integration",
        "description": "Xero connection requires re-authorization",
        "retention_years": 5,
    },
    "integration.xero.oauth_state_mismatch": {
        "category": "security",
        "description": "OAuth state validation failed (potential CSRF)",
        "retention_years": 7,
    },
}
