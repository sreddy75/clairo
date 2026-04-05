"""Pydantic schemas for authentication and multi-tenancy.

This module provides request/response schemas for:
- Tenant operations (create, update, response)
- User operations (base identity and practice profile)
- Invitation operations (create, response, public view)
- Authentication flows (register, me, logout)

Schema naming conventions:
- Base: Common fields shared across operations
- Create: Fields for creating new entities
- Update: Fields for updating existing entities
- Response: Fields returned in API responses
- Summary: Minimal fields for embedded responses
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import InvitationStatus, SubscriptionStatus, SubscriptionTier, UserRole, UserType

# =============================================================================
# Base Schemas (shared fields)
# =============================================================================


class TenantBase(BaseModel):
    """Base tenant schema with common fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Practice name")


class UserBase(BaseModel):
    """Base user schema with common fields."""

    email: EmailStr = Field(..., description="User email address")


class PracticeUserBase(BaseModel):
    """Base practice user schema with common fields."""

    role: UserRole = Field(default=UserRole.ACCOUNTANT, description="User role within the tenant")


class InvitationBase(BaseModel):
    """Base invitation schema with common fields."""

    email: EmailStr = Field(..., description="Email address of the invitee")
    role: UserRole = Field(
        default=UserRole.ACCOUNTANT, description="Role to assign upon acceptance"
    )


# =============================================================================
# Create Schemas (for POST requests)
# =============================================================================


class TenantCreate(TenantBase):
    """Schema for creating a new tenant.

    The slug is auto-generated from the name if not provided.
    """

    slug: str | None = Field(
        None,
        min_length=3,
        max_length=50,
        pattern=r"^[a-z0-9-]+$",
        description="URL-friendly identifier (auto-generated if not provided)",
    )


class PracticeUserCreate(UserBase, PracticeUserBase):
    """Schema for creating a new practice user.

    Used internally when linking a Clerk user to a tenant.
    """

    clerk_id: str = Field(..., min_length=1, max_length=100, description="Clerk user ID")


class InvitationCreate(InvitationBase):
    """Schema for creating a new invitation.

    Only email and role are required; other fields are set automatically.
    """

    pass


# =============================================================================
# Update Schemas (for PATCH requests)
# =============================================================================


class TenantUpdate(BaseModel):
    """Schema for updating tenant settings.

    All fields are optional - only provided fields are updated.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=255, description="Practice name")
    mfa_required: bool | None = Field(None, description="Whether MFA is required for all users")
    settings: dict[str, Any] | None = Field(None, description="Tenant-specific configuration")


class PracticeUserRoleUpdate(BaseModel):
    """Schema for changing a user's role.

    Only admins can change roles.
    """

    model_config = ConfigDict(extra="forbid")

    role: UserRole = Field(..., description="New role for the user")


class PracticeUserDeactivate(BaseModel):
    """Schema for deactivating a user.

    Requires a reason for audit purposes.
    """

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=1, max_length=500, description="Reason for deactivation")


# =============================================================================
# Response Schemas (for API responses)
# =============================================================================


class TenantResponse(TenantBase):
    """Schema for tenant in API responses.

    Includes all tenant fields including computed properties.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Tenant unique identifier")
    slug: str = Field(..., description="URL-friendly identifier")
    subscription_status: SubscriptionStatus = Field(..., description="Current subscription state")
    tier: SubscriptionTier = Field(
        default=SubscriptionTier.PROFESSIONAL, description="Subscription tier"
    )
    client_count: int = Field(default=0, description="Current number of active clients")
    current_period_end: datetime | None = Field(None, description="End of current billing period")
    mfa_required: bool = Field(..., description="Whether MFA is required")
    is_active: bool = Field(..., description="Whether tenant is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class TenantSummary(BaseModel):
    """Minimal tenant info for embedded responses.

    Used when tenant is included as a nested object.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Tenant unique identifier")
    name: str = Field(..., description="Practice name")
    slug: str = Field(..., description="URL-friendly identifier")


class UserResponse(UserBase):
    """Schema for base user identity in API responses.

    Returns core identity fields only.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="User unique identifier")
    user_type: UserType = Field(..., description="Type of user")
    is_active: bool = Field(..., description="Whether user is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class PracticeUserResponse(BaseModel):
    """Schema for practice user profile in API responses.

    Includes profile fields and related user/tenant info.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Practice user unique identifier")
    user_id: UUID = Field(..., description="Base user ID")
    tenant_id: UUID = Field(..., description="Tenant ID")
    clerk_id: str = Field(..., description="Clerk user ID")
    email: str = Field(..., description="Email from base user")
    role: UserRole = Field(..., description="Role within tenant")
    is_active: bool = Field(..., description="Whether user is active (from base User)")
    mfa_enabled: bool = Field(..., description="Whether MFA is configured")
    last_login_at: datetime | None = Field(None, description="Last login timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class PracticeUserSummary(BaseModel):
    """Minimal practice user info for embedded responses.

    Used when user is included as a nested object.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Practice user unique identifier")
    email: str = Field(..., description="Email address")
    role: UserRole = Field(..., description="Role within tenant")


class PracticeUserWithTenant(PracticeUserResponse):
    """Practice user response with full tenant details.

    Used for the /me endpoint to provide complete context.
    """

    tenant: TenantSummary = Field(..., description="Tenant details")


class InvitationResponse(InvitationBase):
    """Schema for invitation in API responses.

    Includes all invitation fields and computed status.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Invitation unique identifier")
    tenant_id: UUID = Field(..., description="Tenant ID")
    invited_by: UUID = Field(..., description="Practice user who created invitation")
    token: str = Field(..., description="Invitation token")
    status: InvitationStatus = Field(..., description="Current invitation status")
    expires_at: datetime = Field(..., description="Expiration timestamp")
    accepted_at: datetime | None = Field(None, description="Acceptance timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")

    # Optional nested objects
    inviter: PracticeUserSummary | None = Field(None, description="User who created the invitation")


class InvitationPublic(BaseModel):
    """Public invitation details (no sensitive info).

    Used for the public invitation lookup endpoint.
    This is returned when looking up an invitation by token
    before the user is authenticated.
    """

    model_config = ConfigDict(from_attributes=True)

    email: str = Field(..., description="Invited email address")
    role: UserRole = Field(..., description="Role to be assigned")
    status: InvitationStatus = Field(..., description="Current invitation status")
    expires_at: datetime = Field(..., description="Expiration timestamp")
    tenant_name: str = Field(..., description="Name of the inviting tenant")


# =============================================================================
# Auth Flow Schemas
# =============================================================================


class RegisterRequest(BaseModel):
    """Request schema for completing registration.

    After authenticating with Clerk, the frontend calls this endpoint
    to complete the registration and link the Clerk user to a tenant.
    """

    invitation_token: str | None = Field(
        None,
        description="Invitation token (if joining existing tenant)",
    )
    tenant_name: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        description="Name for new tenant (if not using invitation)",
    )
    tier: SubscriptionTier | None = Field(
        None,
        description="Subscription tier for new tenant (defaults to starter)",
    )


class RegisterResponse(BaseModel):
    """Response schema for registration.

    Returns the created user, tenant, and whether it's a new tenant.
    """

    user: PracticeUserResponse = Field(..., description="Created practice user")
    tenant: TenantResponse = Field(..., description="User's tenant")
    is_new_tenant: bool = Field(..., description="Whether a new tenant was provisioned")


class MeResponse(BaseModel):
    """Response schema for current user info.

    Returns comprehensive user profile with tenant and permissions.
    """

    user: PracticeUserWithTenant = Field(..., description="Current user with tenant")
    permissions: list[str] = Field(..., description="List of user permissions")


class BootstrapResponse(BaseModel):
    """Response schema for the bootstrap endpoint.

    Combines user profile, feature access, and trial status into a single
    response to eliminate sequential API calls on page load.
    """

    user: MeResponse = Field(..., description="Current user profile with tenant and permissions")
    features: Any | None = Field(None, description="Feature access status for current tenant")
    trial_status: Any | None = Field(None, description="Trial status for current tenant")
    tos_accepted_at: datetime | None = Field(None, description="When user accepted ToS")
    tos_version_accepted: str | None = Field(None, description="ToS version accepted")
    subscription_status: str | None = Field(None, description="Current subscription status")
    can_access: bool = Field(True, description="Whether write operations are allowed")


class AcceptTermsRequest(BaseModel):
    """Request schema for accepting Terms of Service."""

    version: str = Field(..., description="ToS version being accepted", min_length=1, max_length=20)


class AcceptTermsResponse(BaseModel):
    """Response schema after accepting Terms of Service."""

    tos_accepted_at: datetime = Field(..., description="Acceptance timestamp")
    tos_version_accepted: str = Field(..., description="Version accepted")


class TosVersionResponse(BaseModel):
    """Response schema for current ToS version."""

    version: str = Field(..., description="Current ToS version")
    effective_date: str = Field(..., description="Effective date of current ToS")


class LogoutRequest(BaseModel):
    """Request schema for logout.

    Supports logging out current session or all sessions.
    """

    all_devices: bool = Field(
        default=False,
        description="Log out from all devices (not just current session)",
    )


class LogoutResponse(BaseModel):
    """Response schema for logout."""

    message: str = Field(default="Logged out successfully")
    all_devices: bool = Field(default=False, description="Whether all sessions were logged out")


# =============================================================================
# User Management Schemas
# =============================================================================


class UserListResponse(BaseModel):
    """Response schema for listing users."""

    users: list[PracticeUserResponse] = Field(..., description="List of users")
    total: int = Field(..., description="Total count")


class UserActionResponse(BaseModel):
    """Response schema for user action (deactivate/activate)."""

    user: PracticeUserResponse = Field(..., description="Updated user")
    message: str = Field(..., description="Action result message")


# =============================================================================
# Tenant Settings Schemas
# =============================================================================


class TenantSettingsResponse(BaseModel):
    """Response schema for tenant settings."""

    id: UUID = Field(..., description="Tenant ID")
    name: str = Field(..., description="Tenant name")
    slug: str = Field(..., description="URL slug")
    mfa_required: bool = Field(..., description="MFA requirement")
    subscription_status: SubscriptionStatus = Field(..., description="Subscription status")
    tier: SubscriptionTier = Field(
        default=SubscriptionTier.PROFESSIONAL, description="Subscription tier"
    )
    client_count: int = Field(default=0, description="Current client count")
    current_period_end: datetime | None = Field(None, description="Billing period end")
    settings: dict[str, Any] = Field(default_factory=dict, description="Custom settings")
    is_active: bool = Field(..., description="Whether tenant is active")
    is_suspended: bool = Field(default=False, description="Whether tenant is suspended")


# =============================================================================
# Invitation List Schemas
# =============================================================================


class InvitationListResponse(BaseModel):
    """Response schema for listing invitations."""

    invitations: list[InvitationResponse] = Field(..., description="List of invitations")
    total: int = Field(..., description="Total count")
