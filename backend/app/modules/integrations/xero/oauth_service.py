"""Xero OAuth 2.0 service — handles auth URL generation, callbacks, and connection upsert."""

from __future__ import annotations

import contextlib
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.modules.integrations.xero.client import XeroClient
from app.modules.integrations.xero.encryption import TokenEncryption
from app.modules.integrations.xero.exceptions import XeroOAuthError
from app.modules.integrations.xero.models import (
    XeroConnection,
    XeroConnectionStatus,
    XeroConnectionType,
)
from app.modules.integrations.xero.oauth import (
    build_authorization_url,
    generate_code_challenge,
    generate_code_verifier,
    generate_state,
)
from app.modules.integrations.xero.repository import (
    XeroConnectionRepository,
    XeroOAuthStateRepository,
    XpmClientRepository,
)
from app.modules.integrations.xero.schemas import (
    XeroAuthUrlResponse,
    XeroConnectionCreate,
    XeroConnectionUpdate,
    XeroOrganization,
)

logger = logging.getLogger(__name__)


class XeroOAuthService:
    """Service for handling Xero OAuth 2.0 flow."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        """Initialize OAuth service.

        Args:
            session: Database session.
            settings: Application settings.
        """
        self.session = session
        self.settings = settings
        self.state_repo = XeroOAuthStateRepository(session)
        self.connection_repo = XeroConnectionRepository(session)
        self.encryption = TokenEncryption(settings.token_encryption.key.get_secret_value())

    async def generate_auth_url(
        self,
        tenant_id: UUID,
        user_id: UUID,
        frontend_redirect_uri: str,
    ) -> XeroAuthUrlResponse:
        """Generate Xero OAuth authorization URL.

        Creates PKCE parameters and stores state for callback validation.

        Args:
            tenant_id: The tenant initiating OAuth.
            user_id: The user initiating OAuth.
            frontend_redirect_uri: Where to redirect after OAuth.

        Returns:
            XeroAuthUrlResponse with authorization URL and state.
        """
        # Generate PKCE parameters
        code_verifier = generate_code_verifier()
        code_challenge = generate_code_challenge(code_verifier)
        state = generate_state()

        # Store state for callback validation
        expires_at = datetime.now(UTC) + timedelta(minutes=10)
        await self.state_repo.create(
            tenant_id=tenant_id,
            user_id=user_id,
            state=state,
            code_verifier=code_verifier,
            redirect_uri=frontend_redirect_uri,
            expires_at=expires_at,
        )

        # Build authorization URL
        auth_url = build_authorization_url(
            settings=self.settings.xero,
            state=state,
            code_challenge=code_challenge,
            redirect_uri=self.settings.xero.redirect_uri,
        )

        return XeroAuthUrlResponse(auth_url=auth_url, state=state)

    async def generate_client_auth_url(
        self,
        tenant_id: UUID,
        user_id: UUID,
        xpm_client_id: UUID,
        frontend_redirect_uri: str,
    ) -> XeroAuthUrlResponse:
        """Generate Xero OAuth authorization URL for a specific client's org.

        Creates PKCE parameters and stores state with client context for callback.
        The OAuth flow will be for authorizing access to the client's Xero organization.

        Args:
            tenant_id: The tenant (accounting practice) ID.
            user_id: The user initiating OAuth.
            xpm_client_id: The XPM client whose Xero org we're authorizing.
            frontend_redirect_uri: Where to redirect after OAuth.

        Returns:
            XeroAuthUrlResponse with authorization URL and state.
        """
        # Generate PKCE parameters
        code_verifier = generate_code_verifier()
        code_challenge = generate_code_challenge(code_verifier)
        state = generate_state()

        # Store state for callback validation (with client context)
        expires_at = datetime.now(UTC) + timedelta(minutes=10)
        await self.state_repo.create(
            tenant_id=tenant_id,
            user_id=user_id,
            state=state,
            code_verifier=code_verifier,
            redirect_uri=frontend_redirect_uri,
            expires_at=expires_at,
            xpm_client_id=xpm_client_id,
            connection_type=XeroConnectionType.CLIENT,
        )

        # Build authorization URL
        # Note: For individual client auth, we could add acr_values=bulk_connect:false
        # to force single-org selection, but Xero may not support this
        auth_url = build_authorization_url(
            settings=self.settings.xero,
            state=state,
            code_challenge=code_challenge,
            redirect_uri=self.settings.xero.redirect_uri,
        )

        return XeroAuthUrlResponse(auth_url=auth_url, state=state)

    async def handle_callback(
        self,
        code: str,
        state: str,
    ) -> tuple[XeroConnection, UUID | None]:
        """Handle OAuth callback from Xero.

        Validates state, exchanges code for tokens, and creates connection.
        If this was a client-specific OAuth, also links the connection to the XPM client.

        Args:
            code: Authorization code from Xero.
            state: State parameter for CSRF validation.

        Returns:
            Tuple of (XeroConnection, xpm_client_id or None).

        Raises:
            XeroOAuthError: If state is invalid or token exchange fails.
        """
        # Validate state
        oauth_state = await self.state_repo.get_by_state(state)
        if oauth_state is None:
            raise XeroOAuthError("Invalid or unknown state parameter")

        if not oauth_state.is_valid:
            if oauth_state.is_expired:
                raise XeroOAuthError("Authorization expired, please try again")
            if oauth_state.is_used:
                raise XeroOAuthError("Authorization already completed")
            raise XeroOAuthError("Invalid state")

        # Mark state as used
        await self.state_repo.mark_as_used(oauth_state.id)

        # Exchange code for tokens
        async with XeroClient(self.settings.xero) as client:
            token_response, token_expires_at = await client.exchange_code(
                code=code,
                code_verifier=oauth_state.code_verifier,
                redirect_uri=self.settings.xero.redirect_uri,
            )

            # Get connected organizations
            organizations = await client.get_connections(token_response.access_token)

        if not organizations:
            raise XeroOAuthError("No organizations authorized")

        # Check if payroll scopes were granted
        payroll_scopes = ["payroll.employees", "payroll.payruns"]
        has_payroll = all(scope in token_response.scopes_list for scope in payroll_scopes)

        # Determine connection type from OAuth state
        connection_type = oauth_state.connection_type
        xpm_client_id = oauth_state.xpm_client_id

        encrypted_access = self.encryption.encrypt(token_response.access_token)
        encrypted_refresh = self.encryption.encrypt(token_response.refresh_token)

        # Process the primary org (first org, or the one linked to a specific XPM client)
        primary_org = organizations[0]
        primary_connection = await self._upsert_connection(
            tenant_id=oauth_state.tenant_id,
            org=primary_org,
            encrypted_access=encrypted_access,
            encrypted_refresh=encrypted_refresh,
            token_expires_at=token_expires_at,
            scopes=token_response.scopes_list,
            user_id=oauth_state.user_id,
            has_payroll=has_payroll,
            connection_type=connection_type,
            xpm_client_id=xpm_client_id,
        )

        # When NOT a client-specific OAuth, also create connections for
        # remaining authorized orgs so all Xero orgs are imported at once
        if not xpm_client_id and len(organizations) > 1:
            for org in organizations[1:]:
                # Don't fail the primary connection if a secondary one fails
                with contextlib.suppress(Exception):
                    await self._upsert_connection(
                        tenant_id=oauth_state.tenant_id,
                        org=org,
                        encrypted_access=encrypted_access,
                        encrypted_refresh=encrypted_refresh,
                        token_expires_at=token_expires_at,
                        scopes=token_response.scopes_list,
                        user_id=oauth_state.user_id,
                        has_payroll=has_payroll,
                        connection_type=connection_type,
                        xpm_client_id=None,
                    )

        return primary_connection, xpm_client_id

    async def _upsert_connection(
        self,
        tenant_id: UUID,
        org: XeroOrganization,
        encrypted_access: str,
        encrypted_refresh: str,
        token_expires_at: datetime,
        scopes: list[str],
        user_id: UUID,
        has_payroll: bool,
        connection_type: XeroConnectionType,
        xpm_client_id: UUID | None,
    ) -> XeroConnection:
        """Create or update a single Xero connection.

        Args:
            tenant_id: The Clairo tenant ID.
            org: Xero organization from the API.
            encrypted_access: Encrypted access token.
            encrypted_refresh: Encrypted refresh token.
            token_expires_at: Token expiry time.
            scopes: Granted OAuth scopes.
            user_id: User who initiated the connection.
            has_payroll: Whether payroll scopes were granted.
            connection_type: Connection type (practice or client).
            xpm_client_id: Optional XPM client to link.

        Returns:
            The created or updated XeroConnection.
        """
        existing = await self.connection_repo.get_by_xero_tenant_id(
            tenant_id=tenant_id,
            xero_tenant_id=org.id,
        )

        if existing:
            updated = await self.connection_repo.update(
                connection_id=existing.id,
                data=XeroConnectionUpdate(
                    access_token=encrypted_access,
                    refresh_token=encrypted_refresh,
                    token_expires_at=token_expires_at,
                    status=XeroConnectionStatus.ACTIVE,
                    has_payroll_access=has_payroll,
                ),
            )
            if updated:
                if connection_type == XeroConnectionType.CLIENT:
                    from sqlalchemy import text

                    await self.session.execute(
                        text("""
                        UPDATE xero_connections
                        SET connection_type = :connection_type
                        WHERE id = :connection_id
                        """),
                        {
                            "connection_type": connection_type.value,
                            "connection_id": updated.id,
                        },
                    )
                    if xpm_client_id:
                        xpm_repo = XpmClientRepository(self.session)
                        await xpm_repo.link_xero_connection(
                            client_id=xpm_client_id,
                            xero_connection_id=updated.id,
                            xero_org_name=org.display_name,
                        )
                return updated
            raise XeroOAuthError("Failed to update existing connection")

        connection = await self.connection_repo.create(
            XeroConnectionCreate(
                tenant_id=tenant_id,
                xero_tenant_id=org.id,
                organization_name=org.display_name,
                access_token=encrypted_access,
                refresh_token=encrypted_refresh,
                token_expires_at=token_expires_at,
                scopes=scopes,
                connected_by=user_id,
                has_payroll_access=has_payroll,
                connection_type=connection_type.value if connection_type else "practice",
                auth_event_id=org.auth_event_id,
            )
        )

        if connection_type == XeroConnectionType.CLIENT and xpm_client_id:
            xpm_repo = XpmClientRepository(self.session)
            await xpm_repo.link_xero_connection(
                client_id=xpm_client_id,
                xero_connection_id=connection.id,
                xero_org_name=org.display_name,
            )

        # Auto-create PracticeClient for new connection (Spec 058)
        try:
            from app.modules.clients.repository import PracticeClientRepository

            pc_repo = PracticeClientRepository(self.session)
            existing = await pc_repo.get_by_xero_connection_id(connection.id)
            if not existing:
                await pc_repo.create(
                    tenant_id=tenant_id,
                    name=org.display_name,
                    accounting_software="xero",
                    xero_connection_id=connection.id,
                )
        except Exception:
            pass  # Non-fatal

        return connection
