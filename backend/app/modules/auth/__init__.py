"""Authentication and Multi-tenancy Module.

This module provides:
- JWT-based authentication with Clerk integration
- Multi-tenant isolation via PostgreSQL Row-Level Security (RLS)
- Role-based access control (Admin, Accountant, Staff)
- User invitation and onboarding workflows
- Audit logging for all authentication events
- Session management and logout
- MFA enforcement
- Clerk webhook integration
- Rate limiting for auth endpoints

Module structure:
- router.py: FastAPI endpoints for auth, users, invitations, tenant settings, webhooks
- service.py: AuthService, UserService, InvitationService business logic
- repository.py: UserRepository, PracticeUserRepository, TenantRepository, InvitationRepository
- models.py: User (base), PracticeUser (profile), Tenant, Invitation SQLAlchemy models
- schemas.py: Pydantic request/response schemas
- clerk.py: Clerk SDK integration and JWKS client
- middleware.py: JWTMiddleware, TenantMiddleware
- permissions.py: Role definitions and permission checking
- audit_events.py: Auth-specific audit event types
- webhooks.py: Clerk webhook handlers
- rate_limit.py: Rate limiting utilities
"""

from .models import (
    Invitation,
    InvitationStatus,
    PracticeUser,
    SubscriptionStatus,
    Tenant,
    User,
    UserRole,
    UserType,
)
from .permissions import Permission, require_permission, require_role
from .service import AuthService, InvitationService, UserService
from .webhooks import ClerkWebhookHandler, WebhookEvent, verify_webhook_signature

__all__ = [
    # Models
    "User",
    "PracticeUser",
    "Tenant",
    "Invitation",
    # Enums
    "UserType",
    "UserRole",
    "SubscriptionStatus",
    "InvitationStatus",
    # Permissions
    "Permission",
    "require_permission",
    "require_role",
    # Services
    "AuthService",
    "UserService",
    "InvitationService",
    # Webhooks
    "ClerkWebhookHandler",
    "WebhookEvent",
    "verify_webhook_signature",
]
