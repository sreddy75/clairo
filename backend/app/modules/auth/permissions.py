"""Role-based access control (RBAC) system.

This module provides:
- Permission enum: All available permissions in the system
- ROLE_PERMISSIONS: Mapping of roles to their granted permissions
- require_permission(): FastAPI dependency for permission checking
- require_role(): FastAPI dependency for role checking
- require_any_permission(): FastAPI dependency for OR-based permission checking

Role Hierarchy:
- ADMIN: Full access to all operations including user management
- ACCOUNTANT: Full access to client and BAS operations, no user management
- STAFF: Read-only access to client data

Usage:
    from app.modules.auth.permissions import require_permission, Permission

    @router.get("/users")
    async def list_users(
        _: None = Depends(require_permission(Permission.USER_READ)),
    ):
        ...

    @router.post("/users/{user_id}/role")
    async def update_role(
        user_id: UUID,
        _: None = Depends(require_role(UserRole.ADMIN)),
    ):
        ...
"""

from collections.abc import Callable
from enum import Enum

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditService
from app.core.logging import get_logger
from app.database import get_db as get_db_session

from .clerk import ClerkTokenPayload
from .models import PracticeUser, UserRole

logger = get_logger(__name__)


class Permission(str, Enum):
    """All available permissions in the system.

    Permissions follow a resource.action pattern:
    - READ: View resource data
    - WRITE: Create or update resource data
    - DELETE: Remove resource data

    Special permissions:
    - LODGE: Submit BAS to ATO (separate from write)
    """

    # User management permissions (Admin only)
    USER_READ = "user.read"
    USER_WRITE = "user.write"
    USER_DELETE = "user.delete"

    # Tenant management permissions (Admin only)
    TENANT_READ = "tenant.read"
    TENANT_WRITE = "tenant.write"

    # Client management permissions
    CLIENT_READ = "client.read"
    CLIENT_WRITE = "client.write"
    CLIENT_DELETE = "client.delete"

    # BAS management permissions
    BAS_READ = "bas.read"
    BAS_WRITE = "bas.write"
    BAS_LODGE = "bas.lodge"  # Special permission for ATO submission

    # Report permissions
    REPORT_READ = "report.read"
    REPORT_CREATE = "report.create"

    # Integration permissions
    INTEGRATION_READ = "integration.read"
    INTEGRATION_MANAGE = "integration.manage"

    def __str__(self) -> str:
        """Return the permission value as string."""
        return self.value


# Role to permission mapping
# Each role is granted a set of permissions
ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.ADMIN: {
        # Full access to user management
        Permission.USER_READ,
        Permission.USER_WRITE,
        Permission.USER_DELETE,
        # Full access to tenant settings
        Permission.TENANT_READ,
        Permission.TENANT_WRITE,
        # Full access to clients
        Permission.CLIENT_READ,
        Permission.CLIENT_WRITE,
        Permission.CLIENT_DELETE,
        # Full access to BAS
        Permission.BAS_READ,
        Permission.BAS_WRITE,
        Permission.BAS_LODGE,
        # Full access to reports
        Permission.REPORT_READ,
        Permission.REPORT_CREATE,
        # Full access to integrations
        Permission.INTEGRATION_READ,
        Permission.INTEGRATION_MANAGE,
    },
    UserRole.ACCOUNTANT: {
        # Can view users but not manage them
        Permission.USER_READ,
        # Can view tenant settings but not modify
        Permission.TENANT_READ,
        # Full access to clients
        Permission.CLIENT_READ,
        Permission.CLIENT_WRITE,
        Permission.CLIENT_DELETE,
        # Full access to BAS
        Permission.BAS_READ,
        Permission.BAS_WRITE,
        Permission.BAS_LODGE,
        # Full access to reports
        Permission.REPORT_READ,
        Permission.REPORT_CREATE,
        # Can view integrations
        Permission.INTEGRATION_READ,
    },
    UserRole.STAFF: {
        # Read-only access to users
        Permission.USER_READ,
        # Read-only access to tenant
        Permission.TENANT_READ,
        # Read-only access to clients
        Permission.CLIENT_READ,
        # Read-only access to BAS
        Permission.BAS_READ,
        # Read-only access to reports
        Permission.REPORT_READ,
    },
}


def has_permission(role: UserRole, permission: Permission) -> bool:
    """Check if a role has a specific permission.

    Args:
        role: The user's role.
        permission: The permission to check.

    Returns:
        True if the role has the permission, False otherwise.
    """
    role_permissions = ROLE_PERMISSIONS.get(role, set())
    return permission in role_permissions


def get_permissions_for_role(role: UserRole) -> list[str]:
    """Get all permissions for a given role as string list.

    Args:
        role: The user's role.

    Returns:
        List of permission strings granted to the role.
    """
    permissions = ROLE_PERMISSIONS.get(role, set())
    return sorted([str(p) for p in permissions])


async def _get_practice_user_from_request(
    request: Request,
    session: AsyncSession,
) -> PracticeUser:
    """Get practice user from request state or database.

    Args:
        request: FastAPI request object.
        session: Database session.

    Returns:
        Practice user with relationships loaded.

    Raises:
        HTTPException: If user not found.
    """
    from .repository import PracticeUserRepository

    # Get user claims from middleware
    user: ClerkTokenPayload | None = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # Get practice user from database
    repo = PracticeUserRepository(session)
    practice_user = await repo.get_by_clerk_id(user.sub, load_relations=True)

    if practice_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in database",
        )

    # Check if user is active
    if not practice_user.user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return practice_user


def require_permission(permission: Permission) -> Callable:
    """Create a FastAPI dependency that requires a specific permission.

    This dependency checks if the current user has the specified permission
    based on their role. If not, it raises a 403 Forbidden error and logs
    an RBAC access denied event.

    Args:
        permission: The required permission.

    Returns:
        FastAPI dependency function.

    Usage:
        @router.get("/users")
        async def list_users(
            _: None = Depends(require_permission(Permission.USER_READ)),
        ):
            ...
    """

    async def dependency(
        request: Request,
        session: AsyncSession = Depends(get_db_session),
    ) -> PracticeUser:
        """Check if user has the required permission.

        Args:
            request: FastAPI request object.
            session: Database session.

        Returns:
            The authenticated practice user.

        Raises:
            HTTPException: If user lacks the permission.
        """
        practice_user = await _get_practice_user_from_request(request, session)

        # Check permission
        if not has_permission(practice_user.role, permission):
            # Log the access denied event
            try:
                audit_service = AuditService(session)
                await audit_service.log_event(
                    event_type="rbac.access.denied",
                    event_category="auth",
                    actor_type="user",
                    actor_id=practice_user.user_id,
                    actor_email=practice_user.email,
                    tenant_id=practice_user.tenant_id,
                    resource_type=permission.value.split(".")[0],
                    action=permission.value.split(".")[1] if "." in permission.value else "access",
                    outcome="failure",
                    metadata={
                        "required_permission": str(permission),
                        "user_role": str(practice_user.role),
                        "endpoint": str(request.url.path),
                        "method": request.method,
                    },
                )
            except Exception as e:
                logger.error("Failed to log access denied event", error=str(e))

            logger.warning(
                "Permission denied",
                user_id=str(practice_user.user_id),
                role=str(practice_user.role),
                required_permission=str(permission),
                endpoint=str(request.url.path),
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "AUTHORIZATION_ERROR",
                        "message": "You do not have permission to perform this action",
                        "details": {
                            "required_permission": str(permission),
                        },
                    }
                },
            )

        return practice_user

    return dependency


def require_role(*roles: UserRole) -> Callable:
    """Create a FastAPI dependency that requires one of the specified roles.

    This dependency checks if the current user has one of the specified roles.
    If not, it raises a 403 Forbidden error.

    Args:
        *roles: One or more required roles (user must have at least one).

    Returns:
        FastAPI dependency function.

    Usage:
        @router.post("/users/{user_id}/role")
        async def update_role(
            user_id: UUID,
            _: PracticeUser = Depends(require_role(UserRole.ADMIN)),
        ):
            ...
    """
    required_roles = set(roles)

    async def dependency(
        request: Request,
        session: AsyncSession = Depends(get_db_session),
    ) -> PracticeUser:
        """Check if user has one of the required roles.

        Args:
            request: FastAPI request object.
            session: Database session.

        Returns:
            The authenticated practice user.

        Raises:
            HTTPException: If user doesn't have one of the required roles.
        """
        practice_user = await _get_practice_user_from_request(request, session)

        # Check role
        if practice_user.role not in required_roles:
            # Log the access denied event
            try:
                audit_service = AuditService(session)
                await audit_service.log_event(
                    event_type="rbac.access.denied",
                    event_category="auth",
                    actor_type="user",
                    actor_id=practice_user.user_id,
                    actor_email=practice_user.email,
                    tenant_id=practice_user.tenant_id,
                    action="access",
                    outcome="failure",
                    metadata={
                        "required_roles": [str(r) for r in required_roles],
                        "user_role": str(practice_user.role),
                        "endpoint": str(request.url.path),
                        "method": request.method,
                    },
                )
            except Exception as e:
                logger.error("Failed to log access denied event", error=str(e))

            logger.warning(
                "Role not authorized",
                user_id=str(practice_user.user_id),
                role=str(practice_user.role),
                required_roles=[str(r) for r in required_roles],
                endpoint=str(request.url.path),
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "AUTHORIZATION_ERROR",
                        "message": "You do not have the required role to perform this action",
                        "details": {
                            "required_roles": [str(r) for r in required_roles],
                        },
                    }
                },
            )

        return practice_user

    return dependency


def require_any_permission(*permissions: Permission) -> Callable:
    """Create a FastAPI dependency that requires any one of the specified permissions.

    This dependency checks if the current user has at least one of the specified
    permissions. Useful for endpoints that multiple roles can access with different
    capabilities.

    Args:
        *permissions: One or more permissions (user must have at least one).

    Returns:
        FastAPI dependency function.

    Usage:
        @router.get("/clients")
        async def list_clients(
            _: PracticeUser = Depends(require_any_permission(
                Permission.CLIENT_READ,
                Permission.CLIENT_WRITE,
            )),
        ):
            ...
    """
    required_permissions = set(permissions)

    async def dependency(
        request: Request,
        session: AsyncSession = Depends(get_db_session),
    ) -> PracticeUser:
        """Check if user has any of the required permissions.

        Args:
            request: FastAPI request object.
            session: Database session.

        Returns:
            The authenticated practice user.

        Raises:
            HTTPException: If user lacks all of the permissions.
        """
        practice_user = await _get_practice_user_from_request(request, session)

        # Check if user has any of the required permissions
        role_permissions = ROLE_PERMISSIONS.get(practice_user.role, set())
        if not role_permissions.intersection(required_permissions):
            # Log the access denied event
            try:
                audit_service = AuditService(session)
                await audit_service.log_event(
                    event_type="rbac.access.denied",
                    event_category="auth",
                    actor_type="user",
                    actor_id=practice_user.user_id,
                    actor_email=practice_user.email,
                    tenant_id=practice_user.tenant_id,
                    action="access",
                    outcome="failure",
                    metadata={
                        "required_permissions": [str(p) for p in required_permissions],
                        "user_role": str(practice_user.role),
                        "endpoint": str(request.url.path),
                        "method": request.method,
                    },
                )
            except Exception as e:
                logger.error("Failed to log access denied event", error=str(e))

            logger.warning(
                "No matching permissions",
                user_id=str(practice_user.user_id),
                role=str(practice_user.role),
                required_permissions=[str(p) for p in required_permissions],
                endpoint=str(request.url.path),
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "AUTHORIZATION_ERROR",
                        "message": "You do not have permission to perform this action",
                        "details": {
                            "required_permissions": [str(p) for p in required_permissions],
                        },
                    }
                },
            )

        return practice_user

    return dependency


def require_admin() -> Callable:
    """Convenience dependency that requires admin role.

    Shortcut for require_role(UserRole.ADMIN).

    Returns:
        FastAPI dependency function.

    Usage:
        @router.delete("/users/{user_id}")
        async def delete_user(
            user_id: UUID,
            current_user: PracticeUser = Depends(require_admin()),
        ):
            ...
    """
    return require_role(UserRole.ADMIN)
