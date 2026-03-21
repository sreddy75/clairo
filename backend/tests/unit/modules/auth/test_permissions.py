"""Unit tests for the permission system.

Tests cover:
- Permission enum values and string representation
- Role-permission mappings are correct
- has_permission() function
- get_permissions_for_role() function
- require_permission() dependency allows authorized access
- require_permission() dependency denies unauthorized access
- require_role() dependency
- require_any_permission() dependency
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status

from app.modules.auth.models import PracticeUser, User, UserRole, UserType
from app.modules.auth.permissions import (
    ROLE_PERMISSIONS,
    Permission,
    get_permissions_for_role,
    has_permission,
    require_admin,
    require_any_permission,
    require_permission,
    require_role,
)

# =============================================================================
# Permission Enum Tests
# =============================================================================


class TestPermissionEnum:
    """Tests for Permission enum."""

    def test_permission_values(self):
        """Test that all expected permissions exist with correct values."""
        # User permissions
        assert Permission.USER_READ.value == "user.read"
        assert Permission.USER_WRITE.value == "user.write"
        assert Permission.USER_DELETE.value == "user.delete"

        # Tenant permissions
        assert Permission.TENANT_READ.value == "tenant.read"
        assert Permission.TENANT_WRITE.value == "tenant.write"

        # Client permissions
        assert Permission.CLIENT_READ.value == "client.read"
        assert Permission.CLIENT_WRITE.value == "client.write"
        assert Permission.CLIENT_DELETE.value == "client.delete"

        # BAS permissions
        assert Permission.BAS_READ.value == "bas.read"
        assert Permission.BAS_WRITE.value == "bas.write"
        assert Permission.BAS_LODGE.value == "bas.lodge"

        # Report permissions
        assert Permission.REPORT_READ.value == "report.read"
        assert Permission.REPORT_CREATE.value == "report.create"

        # Integration permissions
        assert Permission.INTEGRATION_READ.value == "integration.read"
        assert Permission.INTEGRATION_MANAGE.value == "integration.manage"

    def test_permission_str(self):
        """Test that Permission.__str__ returns the value."""
        assert str(Permission.USER_READ) == "user.read"
        assert str(Permission.BAS_LODGE) == "bas.lodge"

    def test_permission_is_string_enum(self):
        """Test that Permission can be used as string."""
        perm = Permission.USER_READ
        assert perm == "user.read"
        assert isinstance(perm, str)


# =============================================================================
# Role-Permission Mapping Tests
# =============================================================================


class TestRolePermissions:
    """Tests for ROLE_PERMISSIONS mapping."""

    def test_admin_has_all_permissions(self):
        """Test that ADMIN role has all permissions."""
        admin_perms = ROLE_PERMISSIONS[UserRole.ADMIN]

        # Admin should have all user permissions
        assert Permission.USER_READ in admin_perms
        assert Permission.USER_WRITE in admin_perms
        assert Permission.USER_DELETE in admin_perms

        # Admin should have all tenant permissions
        assert Permission.TENANT_READ in admin_perms
        assert Permission.TENANT_WRITE in admin_perms

        # Admin should have all client permissions
        assert Permission.CLIENT_READ in admin_perms
        assert Permission.CLIENT_WRITE in admin_perms
        assert Permission.CLIENT_DELETE in admin_perms

        # Admin should have all BAS permissions
        assert Permission.BAS_READ in admin_perms
        assert Permission.BAS_WRITE in admin_perms
        assert Permission.BAS_LODGE in admin_perms

        # Admin should have all report permissions
        assert Permission.REPORT_READ in admin_perms
        assert Permission.REPORT_CREATE in admin_perms

        # Admin should have all integration permissions
        assert Permission.INTEGRATION_READ in admin_perms
        assert Permission.INTEGRATION_MANAGE in admin_perms

    def test_accountant_has_correct_permissions(self):
        """Test that ACCOUNTANT role has expected permissions."""
        accountant_perms = ROLE_PERMISSIONS[UserRole.ACCOUNTANT]

        # Accountant should have read-only user access
        assert Permission.USER_READ in accountant_perms
        assert Permission.USER_WRITE not in accountant_perms
        assert Permission.USER_DELETE not in accountant_perms

        # Accountant should have read-only tenant access
        assert Permission.TENANT_READ in accountant_perms
        assert Permission.TENANT_WRITE not in accountant_perms

        # Accountant should have full client access
        assert Permission.CLIENT_READ in accountant_perms
        assert Permission.CLIENT_WRITE in accountant_perms
        assert Permission.CLIENT_DELETE in accountant_perms

        # Accountant should have full BAS access
        assert Permission.BAS_READ in accountant_perms
        assert Permission.BAS_WRITE in accountant_perms
        assert Permission.BAS_LODGE in accountant_perms

        # Accountant should have full report access
        assert Permission.REPORT_READ in accountant_perms
        assert Permission.REPORT_CREATE in accountant_perms

        # Accountant should have read-only integration access
        assert Permission.INTEGRATION_READ in accountant_perms
        assert Permission.INTEGRATION_MANAGE not in accountant_perms

    def test_staff_has_read_only_permissions(self):
        """Test that STAFF role has only read permissions."""
        staff_perms = ROLE_PERMISSIONS[UserRole.STAFF]

        # Staff should have read-only user access
        assert Permission.USER_READ in staff_perms
        assert Permission.USER_WRITE not in staff_perms
        assert Permission.USER_DELETE not in staff_perms

        # Staff should have read-only tenant access
        assert Permission.TENANT_READ in staff_perms
        assert Permission.TENANT_WRITE not in staff_perms

        # Staff should have read-only client access
        assert Permission.CLIENT_READ in staff_perms
        assert Permission.CLIENT_WRITE not in staff_perms
        assert Permission.CLIENT_DELETE not in staff_perms

        # Staff should have read-only BAS access
        assert Permission.BAS_READ in staff_perms
        assert Permission.BAS_WRITE not in staff_perms
        assert Permission.BAS_LODGE not in staff_perms

        # Staff should have read-only report access
        assert Permission.REPORT_READ in staff_perms
        assert Permission.REPORT_CREATE not in staff_perms

        # Staff should not have integration access
        assert Permission.INTEGRATION_READ not in staff_perms
        assert Permission.INTEGRATION_MANAGE not in staff_perms


# =============================================================================
# has_permission() Tests
# =============================================================================


class TestHasPermission:
    """Tests for has_permission function."""

    def test_admin_has_all_permissions(self):
        """Test that admin has all permissions."""
        for permission in Permission:
            assert has_permission(UserRole.ADMIN, permission) is True

    def test_accountant_has_expected_permissions(self):
        """Test accountant permission checking."""
        # Accountant should have these
        assert has_permission(UserRole.ACCOUNTANT, Permission.CLIENT_READ) is True
        assert has_permission(UserRole.ACCOUNTANT, Permission.CLIENT_WRITE) is True
        assert has_permission(UserRole.ACCOUNTANT, Permission.BAS_LODGE) is True

        # Accountant should NOT have these
        assert has_permission(UserRole.ACCOUNTANT, Permission.USER_WRITE) is False
        assert has_permission(UserRole.ACCOUNTANT, Permission.TENANT_WRITE) is False

    def test_staff_has_read_only_permissions(self):
        """Test staff permission checking."""
        # Staff should have read permissions
        assert has_permission(UserRole.STAFF, Permission.CLIENT_READ) is True
        assert has_permission(UserRole.STAFF, Permission.BAS_READ) is True

        # Staff should NOT have write permissions
        assert has_permission(UserRole.STAFF, Permission.CLIENT_WRITE) is False
        assert has_permission(UserRole.STAFF, Permission.BAS_WRITE) is False
        assert has_permission(UserRole.STAFF, Permission.BAS_LODGE) is False


# =============================================================================
# get_permissions_for_role() Tests
# =============================================================================


class TestGetPermissionsForRole:
    """Tests for get_permissions_for_role function."""

    def test_returns_sorted_list_of_strings(self):
        """Test that function returns sorted list of permission strings."""
        admin_perms = get_permissions_for_role(UserRole.ADMIN)

        assert isinstance(admin_perms, list)
        assert all(isinstance(p, str) for p in admin_perms)
        # Check sorting
        assert admin_perms == sorted(admin_perms)

    def test_admin_has_most_permissions(self):
        """Test that admin has more permissions than other roles."""
        admin_count = len(get_permissions_for_role(UserRole.ADMIN))
        accountant_count = len(get_permissions_for_role(UserRole.ACCOUNTANT))
        staff_count = len(get_permissions_for_role(UserRole.STAFF))

        assert admin_count > accountant_count > staff_count

    def test_returns_empty_for_unknown_role(self):
        """Test that function returns empty for non-existent role."""
        # Create a mock role that doesn't exist in the mapping
        perms = get_permissions_for_role(MagicMock())
        assert perms == []


# =============================================================================
# require_permission() Tests
# =============================================================================


class TestRequirePermission:
    """Tests for require_permission dependency."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock FastAPI request."""
        request = MagicMock()
        request.state = MagicMock()
        request.url.path = "/api/v1/users"
        request.method = "GET"
        return request

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def admin_user(self):
        """Create an admin practice user."""
        user = MagicMock(spec=User)
        user.id = uuid.uuid4()
        user.email = "admin@example.com"
        user.is_active = True
        user.user_type = UserType.PRACTICE_USER

        practice_user = MagicMock(spec=PracticeUser)
        practice_user.id = uuid.uuid4()
        practice_user.user_id = user.id
        practice_user.tenant_id = uuid.uuid4()
        practice_user.role = UserRole.ADMIN
        practice_user.email = user.email
        practice_user.user = user

        return practice_user

    @pytest.fixture
    def staff_user(self):
        """Create a staff practice user."""
        user = MagicMock(spec=User)
        user.id = uuid.uuid4()
        user.email = "staff@example.com"
        user.is_active = True
        user.user_type = UserType.PRACTICE_USER

        practice_user = MagicMock(spec=PracticeUser)
        practice_user.id = uuid.uuid4()
        practice_user.user_id = user.id
        practice_user.tenant_id = uuid.uuid4()
        practice_user.role = UserRole.STAFF
        practice_user.email = user.email
        practice_user.user = user

        return practice_user

    @pytest.mark.asyncio
    async def test_allows_authorized_access(self, mock_request, mock_session, admin_user):
        """Test that authorized users can access protected endpoints."""
        mock_request.state.user = MagicMock(sub="user_123")

        with patch("app.modules.auth.repository.PracticeUserRepository") as mock_repo_class:
            mock_repo = mock_repo_class.return_value
            mock_repo.get_by_clerk_id = AsyncMock(return_value=admin_user)

            dependency = require_permission(Permission.USER_READ)
            result = await dependency(mock_request, mock_session)

            assert result == admin_user

    @pytest.mark.asyncio
    async def test_denies_unauthorized_access(self, mock_request, mock_session, staff_user):
        """Test that unauthorized users are denied access."""
        mock_request.state.user = MagicMock(sub="user_123")

        with patch("app.modules.auth.repository.PracticeUserRepository") as mock_repo_class:
            mock_repo = mock_repo_class.return_value
            mock_repo.get_by_clerk_id = AsyncMock(return_value=staff_user)

            with patch("app.core.audit.AuditService") as mock_audit_class:
                mock_audit = mock_audit_class.return_value
                mock_audit.log_event = AsyncMock()

                dependency = require_permission(Permission.USER_WRITE)

                with pytest.raises(HTTPException) as exc_info:
                    await dependency(mock_request, mock_session)

                assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
                assert "AUTHORIZATION_ERROR" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_raises_401_when_not_authenticated(self, mock_request, mock_session):
        """Test that unauthenticated requests get 401."""
        mock_request.state.user = None

        dependency = require_permission(Permission.USER_READ)

        with pytest.raises(HTTPException) as exc_info:
            await dependency(mock_request, mock_session)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_raises_404_when_user_not_in_database(self, mock_request, mock_session):
        """Test that missing database user returns 404."""
        mock_request.state.user = MagicMock(sub="user_123")

        with patch("app.modules.auth.repository.PracticeUserRepository") as mock_repo_class:
            mock_repo = mock_repo_class.return_value
            mock_repo.get_by_clerk_id = AsyncMock(return_value=None)

            dependency = require_permission(Permission.USER_READ)

            with pytest.raises(HTTPException) as exc_info:
                await dependency(mock_request, mock_session)

            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_raises_403_for_deactivated_user(self, mock_request, mock_session, admin_user):
        """Test that deactivated users get 403."""
        mock_request.state.user = MagicMock(sub="user_123")
        admin_user.user.is_active = False

        with patch("app.modules.auth.repository.PracticeUserRepository") as mock_repo_class:
            mock_repo = mock_repo_class.return_value
            mock_repo.get_by_clerk_id = AsyncMock(return_value=admin_user)

            dependency = require_permission(Permission.USER_READ)

            with pytest.raises(HTTPException) as exc_info:
                await dependency(mock_request, mock_session)

            assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
            assert "deactivated" in str(exc_info.value.detail).lower()


# =============================================================================
# require_role() Tests
# =============================================================================


class TestRequireRole:
    """Tests for require_role dependency."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock FastAPI request."""
        request = MagicMock()
        request.state = MagicMock()
        request.url.path = "/api/v1/users"
        request.method = "POST"
        return request

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def admin_user(self):
        """Create an admin practice user."""
        user = MagicMock(spec=User)
        user.id = uuid.uuid4()
        user.email = "admin@example.com"
        user.is_active = True

        practice_user = MagicMock(spec=PracticeUser)
        practice_user.id = uuid.uuid4()
        practice_user.user_id = user.id
        practice_user.tenant_id = uuid.uuid4()
        practice_user.role = UserRole.ADMIN
        practice_user.email = user.email
        practice_user.user = user

        return practice_user

    @pytest.fixture
    def accountant_user(self):
        """Create an accountant practice user."""
        user = MagicMock(spec=User)
        user.id = uuid.uuid4()
        user.email = "accountant@example.com"
        user.is_active = True

        practice_user = MagicMock(spec=PracticeUser)
        practice_user.id = uuid.uuid4()
        practice_user.user_id = user.id
        practice_user.tenant_id = uuid.uuid4()
        practice_user.role = UserRole.ACCOUNTANT
        practice_user.email = user.email
        practice_user.user = user

        return practice_user

    @pytest.mark.asyncio
    async def test_allows_matching_role(self, mock_request, mock_session, admin_user):
        """Test that users with matching role are allowed."""
        mock_request.state.user = MagicMock(sub="user_123")

        with patch("app.modules.auth.repository.PracticeUserRepository") as mock_repo_class:
            mock_repo = mock_repo_class.return_value
            mock_repo.get_by_clerk_id = AsyncMock(return_value=admin_user)

            dependency = require_role(UserRole.ADMIN)
            result = await dependency(mock_request, mock_session)

            assert result == admin_user

    @pytest.mark.asyncio
    async def test_allows_any_of_multiple_roles(self, mock_request, mock_session, accountant_user):
        """Test that users with any of the specified roles are allowed."""
        mock_request.state.user = MagicMock(sub="user_123")

        with patch("app.modules.auth.repository.PracticeUserRepository") as mock_repo_class:
            mock_repo = mock_repo_class.return_value
            mock_repo.get_by_clerk_id = AsyncMock(return_value=accountant_user)

            dependency = require_role(UserRole.ADMIN, UserRole.ACCOUNTANT)
            result = await dependency(mock_request, mock_session)

            assert result == accountant_user

    @pytest.mark.asyncio
    async def test_denies_non_matching_role(self, mock_request, mock_session, accountant_user):
        """Test that users without the required role are denied."""
        mock_request.state.user = MagicMock(sub="user_123")

        with patch("app.modules.auth.repository.PracticeUserRepository") as mock_repo_class:
            mock_repo = mock_repo_class.return_value
            mock_repo.get_by_clerk_id = AsyncMock(return_value=accountant_user)

            with patch("app.core.audit.AuditService") as mock_audit_class:
                mock_audit = mock_audit_class.return_value
                mock_audit.log_event = AsyncMock()

                dependency = require_role(UserRole.ADMIN)

                with pytest.raises(HTTPException) as exc_info:
                    await dependency(mock_request, mock_session)

                assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


# =============================================================================
# require_any_permission() Tests
# =============================================================================


class TestRequireAnyPermission:
    """Tests for require_any_permission dependency."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock FastAPI request."""
        request = MagicMock()
        request.state = MagicMock()
        request.url.path = "/api/v1/clients"
        request.method = "GET"
        return request

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def staff_user(self):
        """Create a staff practice user."""
        user = MagicMock(spec=User)
        user.id = uuid.uuid4()
        user.email = "staff@example.com"
        user.is_active = True

        practice_user = MagicMock(spec=PracticeUser)
        practice_user.id = uuid.uuid4()
        practice_user.user_id = user.id
        practice_user.tenant_id = uuid.uuid4()
        practice_user.role = UserRole.STAFF
        practice_user.email = user.email
        practice_user.user = user

        return practice_user

    @pytest.mark.asyncio
    async def test_allows_if_has_any_permission(self, mock_request, mock_session, staff_user):
        """Test that user with any of the permissions is allowed."""
        mock_request.state.user = MagicMock(sub="user_123")

        with patch("app.modules.auth.repository.PracticeUserRepository") as mock_repo_class:
            mock_repo = mock_repo_class.return_value
            mock_repo.get_by_clerk_id = AsyncMock(return_value=staff_user)

            # Staff has CLIENT_READ but not CLIENT_WRITE
            dependency = require_any_permission(Permission.CLIENT_READ, Permission.CLIENT_WRITE)
            result = await dependency(mock_request, mock_session)

            assert result == staff_user

    @pytest.mark.asyncio
    async def test_denies_if_has_no_permissions(self, mock_request, mock_session, staff_user):
        """Test that user without any of the permissions is denied."""
        mock_request.state.user = MagicMock(sub="user_123")

        with patch("app.modules.auth.repository.PracticeUserRepository") as mock_repo_class:
            mock_repo = mock_repo_class.return_value
            mock_repo.get_by_clerk_id = AsyncMock(return_value=staff_user)

            with patch("app.core.audit.AuditService") as mock_audit_class:
                mock_audit = mock_audit_class.return_value
                mock_audit.log_event = AsyncMock()

                # Staff has neither USER_WRITE nor USER_DELETE
                dependency = require_any_permission(Permission.USER_WRITE, Permission.USER_DELETE)

                with pytest.raises(HTTPException) as exc_info:
                    await dependency(mock_request, mock_session)

                assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


# =============================================================================
# require_admin() Tests
# =============================================================================


class TestRequireAdmin:
    """Tests for require_admin convenience function."""

    def test_returns_require_role_for_admin(self):
        """Test that require_admin returns a role dependency for ADMIN."""
        dependency = require_admin()
        # The dependency should be callable
        assert callable(dependency)
