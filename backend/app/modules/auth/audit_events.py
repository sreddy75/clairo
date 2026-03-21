"""Authentication-specific audit event definitions.

This module defines audit event types for:
- Authentication events (login, logout, token validation)
- User lifecycle events (created, role changed, deactivated)
- Invitation events (created, accepted, expired, revoked)
- Tenant settings changes
- RBAC access denied events

All events are logged with 7-year retention for compliance.
"""

# Auth-specific audit event definitions
AUTH_AUDIT_EVENTS = {
    # Authentication events
    "auth.login.success": {
        "category": "auth",
        "retention": "7y",
        "sensitive": ["ip"],
        "description": "User successfully logged in",
    },
    "auth.login.failure": {
        "category": "auth",
        "retention": "7y",
        "sensitive": ["email", "ip"],
        "description": "Login attempt failed",
    },
    "auth.logout": {
        "category": "auth",
        "retention": "7y",
        "sensitive": [],
        "description": "User logged out",
    },
    "auth.token.invalid": {
        "category": "auth",
        "retention": "7y",
        "sensitive": ["ip"],
        "description": "Invalid token rejected",
    },
    # User lifecycle events
    "user.created": {
        "category": "auth",
        "retention": "7y",
        "sensitive": [],
        "description": "New user registered",
    },
    "user.role.changed": {
        "category": "auth",
        "retention": "7y",
        "sensitive": [],
        "description": "User role was changed",
    },
    "user.deactivated": {
        "category": "auth",
        "retention": "7y",
        "sensitive": [],
        "description": "User was deactivated",
    },
    "user.activated": {
        "category": "auth",
        "retention": "7y",
        "sensitive": [],
        "description": "User was activated",
    },
    # Invitation events
    "user.invitation.created": {
        "category": "auth",
        "retention": "7y",
        "sensitive": ["email"],
        "description": "Invitation sent to new user",
    },
    "user.invitation.accepted": {
        "category": "auth",
        "retention": "7y",
        "sensitive": [],
        "description": "Invitation was accepted",
    },
    "user.invitation.expired": {
        "category": "auth",
        "retention": "7y",
        "sensitive": ["email"],
        "description": "Invitation expired without acceptance",
    },
    "user.invitation.revoked": {
        "category": "auth",
        "retention": "7y",
        "sensitive": [],
        "description": "Invitation was revoked",
    },
    # Tenant settings
    "tenant.settings.changed": {
        "category": "auth",
        "retention": "7y",
        "sensitive": [],
        "description": "Tenant settings were modified",
    },
    # RBAC events
    "rbac.access.denied": {
        "category": "auth",
        "retention": "7y",
        "sensitive": [],
        "description": "Permission check failed",
    },
    # MFA events
    "auth.mfa.enabled": {
        "category": "auth",
        "retention": "7y",
        "sensitive": [],
        "description": "User enabled MFA",
    },
    "auth.mfa.disabled": {
        "category": "auth",
        "retention": "7y",
        "sensitive": [],
        "description": "User disabled MFA",
    },
    "auth.mfa.required.changed": {
        "category": "auth",
        "retention": "7y",
        "sensitive": [],
        "description": "Tenant MFA requirement changed",
    },
    # Session events
    "auth.session.created": {
        "category": "auth",
        "retention": "7y",
        "sensitive": ["ip"],
        "description": "New session created",
    },
    "auth.session.revoked": {
        "category": "auth",
        "retention": "7y",
        "sensitive": [],
        "description": "Session revoked",
    },
    # Webhook events
    "webhook.received": {
        "category": "auth",
        "retention": "7y",
        "sensitive": [],
        "description": "Clerk webhook received",
    },
    "webhook.processed": {
        "category": "auth",
        "retention": "7y",
        "sensitive": [],
        "description": "Clerk webhook processed successfully",
    },
    "webhook.failed": {
        "category": "auth",
        "retention": "7y",
        "sensitive": [],
        "description": "Clerk webhook processing failed",
    },
}
