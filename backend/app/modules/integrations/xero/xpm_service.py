"""XPM client service — manages Xero Practice Manager client-to-org linking, matching, and progress tracking."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.modules.integrations.xero.client import XeroClient
from app.modules.integrations.xero.connection_service import XeroConnectionService
from app.modules.integrations.xero.encryption import TokenEncryption
from app.modules.integrations.xero.exceptions import XpmClientNotFoundError
from app.modules.integrations.xero.models import (
    XeroConnectionStatus,
    XeroConnectionType,
    XpmClientConnectionStatus,
)
from app.modules.integrations.xero.repository import (
    XeroConnectionRepository,
    XpmClientRepository,
)
from app.modules.integrations.xero.schemas import (
    XeroConnectionResponse,
    XeroConnectionUpdate,
    XeroOrganization,
    XpmClientConnectionProgress,
    XpmClientListResponse,
    XpmClientResponse,
    XpmClientStatusCounts,
)

logger = logging.getLogger(__name__)


class XpmClientService:
    """Service for XPM client and Xero organization connection management.

    Handles:
    - Fetching all Xero connections from Xero API
    - Syncing connections to database
    - Matching Xero organizations to XPM clients
    - Managing XPM client connection status
    """

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        """Initialize XPM client service.

        Args:
            session: Database session.
            settings: Application settings.
        """
        self.session = session
        self.settings = settings
        self.xpm_client_repo = XpmClientRepository(session)
        self.connection_repo = XeroConnectionRepository(session)
        self.encryption = TokenEncryption(settings.token_encryption.key.get_secret_value())

    async def fetch_xero_connections(
        self,
        connection_id: UUID,
    ) -> list[XeroOrganization]:
        """Fetch all authorized Xero organizations from Xero API.

        Uses an existing connection's access token to call the Xero /connections
        endpoint and retrieve all organizations the user has access to.

        Args:
            connection_id: ID of an existing active XeroConnection to use for auth.

        Returns:
            List of XeroOrganization objects from Xero API.

        Raises:
            XeroConnectionNotFoundError: If connection not found.
            XeroConnectionInactiveError: If connection is not active.
        """
        # Get the connection for auth
        connection = await self.connection_repo.get_by_id(connection_id)
        if not connection:
            raise XeroConnectionNotFoundExc(connection_id)

        if connection.status == XeroConnectionStatus.NEEDS_REAUTH:
            from app.modules.integrations.xero.exceptions import XeroAuthRequiredError

            raise XeroAuthRequiredError(connection_id, org_name=connection.organization_name or "")

        if connection.status != XeroConnectionStatus.ACTIVE:
            raise XeroConnectionInactiveError(
                f"Connection {connection_id} is not active (status: {connection.status})"
            )

        # Get access token via ensure_valid_token (handles expiry + grant-scoped lock)
        conn_service = XeroConnectionService(self.session, self.settings)
        access_token = await conn_service.ensure_valid_token(connection_id)

        # Fetch connections from Xero API
        async with XeroClient(self.settings.xero) as client:
            organizations = await client.get_connections(access_token)

        logger.info(
            "Fetched %d Xero connections for tenant %s",
            len(organizations),
            connection.tenant_id,
        )

        return organizations

    async def sync_xero_connections(
        self,
        tenant_id: UUID,
        organizations: list[XeroOrganization],
        connected_by: UUID | None = None,
    ) -> dict[str, Any]:
        """Sync Xero organizations to database as XeroConnection records.

        Creates or updates XeroConnection records for each organization.
        Groups connections by authEventId to identify bulk authorization batches.

        Args:
            tenant_id: The Clairo tenant ID.
            organizations: List of XeroOrganization from Xero API.
            connected_by: User ID who authorized the connections.

        Returns:
            Dictionary with sync results:
            - created: Number of new connections created
            - updated: Number of existing connections updated
            - total: Total organizations processed
            - connections: List of connection IDs
        """
        created = 0
        updated = 0
        connection_ids: list[UUID] = []

        for org in organizations:
            # Check if connection already exists
            existing = await self.connection_repo.get_by_xero_tenant_id(
                tenant_id=tenant_id,
                xero_tenant_id=org.id,
            )

            if existing:
                # Update existing connection (re-authorization or refresh)
                await self.connection_repo.update(
                    connection_id=existing.id,
                    data=XeroConnectionUpdate(
                        status=XeroConnectionStatus.ACTIVE,
                    ),
                )
                # Update auth_event_id if provided (for bulk connections)
                if org.auth_event_id:
                    from sqlalchemy import text

                    await self.session.execute(
                        text("""
                        UPDATE xero_connections
                        SET auth_event_id = :auth_event_id
                        WHERE id = :connection_id
                        """),
                        {
                            "auth_event_id": org.auth_event_id,
                            "connection_id": existing.id,
                        },
                    )
                connection_ids.append(existing.id)
                updated += 1
                logger.debug(
                    "Updated existing connection %s for org %s",
                    existing.id,
                    org.display_name,
                )
            else:
                # This is a new organization - we need tokens to create a connection
                # In practice, this sync method is called after OAuth callback
                # where we already have the tokens. For now, log a warning.
                logger.warning(
                    "Organization %s (%s) not in database - needs OAuth authorization",
                    org.display_name,
                    org.id,
                )
                # We'll track it but can't create without tokens
                # The OAuth callback handler should create these

        logger.info(
            "Synced Xero connections for tenant %s: %d created, %d updated",
            tenant_id,
            created,
            updated,
        )

        return {
            "created": created,
            "updated": updated,
            "total": len(organizations),
            "connections": connection_ids,
        }

    async def match_connections_to_xpm_clients(
        self,
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Match Xero connections to XPM clients.

        Attempts to match XeroConnection records to XpmClient records based on:
        1. Exact organization name match
        2. ABN match (if available in organization details)
        3. Fuzzy name match (TODO: implement later)

        Args:
            tenant_id: The Clairo tenant ID.

        Returns:
            Dictionary with matching results:
            - matched: List of {client_id, connection_id, org_name}
            - unmatched_connections: List of connections without matching clients
            - unmatched_clients: List of clients without connections
        """
        matched: list[dict[str, Any]] = []
        unmatched_connections: list[dict[str, Any]] = []

        # Get all client-type connections for this tenant
        all_connections = await self.connection_repo.list_by_tenant(
            tenant_id=tenant_id,
            include_disconnected=False,
        )

        # Filter to client connections only (not practice connections)
        client_connections = [
            c for c in all_connections if c.connection_type == XeroConnectionType.CLIENT
        ]

        # Get all XPM clients that are not yet connected
        unconnected_clients, _ = await self.xpm_client_repo.get_unconnected_clients(
            tenant_id=tenant_id,
            limit=1000,  # Get all for matching
        )

        # Create a lookup by name (normalized)
        client_by_name: dict[str, Any] = {}
        for client in unconnected_clients:
            normalized_name = client.name.lower().strip()
            client_by_name[normalized_name] = client

        # Try to match each connection
        for connection in client_connections:
            # Skip if this connection is already linked to a client
            existing_link = await self.xpm_client_repo.get_by_xero_connection_id(connection.id)
            if existing_link:
                matched.append(
                    {
                        "client_id": str(existing_link.id),
                        "client_name": existing_link.name,
                        "connection_id": str(connection.id),
                        "org_name": connection.organization_name,
                        "match_type": "existing",
                    }
                )
                continue

            # Try exact name match
            normalized_org_name = connection.organization_name.lower().strip()
            if normalized_org_name in client_by_name:
                client = client_by_name[normalized_org_name]
                # Link the connection to the client
                await self.xpm_client_repo.link_xero_connection(
                    client_id=client.id,
                    xero_connection_id=connection.id,
                    xero_org_name=connection.organization_name,
                )
                matched.append(
                    {
                        "client_id": str(client.id),
                        "client_name": client.name,
                        "connection_id": str(connection.id),
                        "org_name": connection.organization_name,
                        "match_type": "exact_name",
                    }
                )
                # Remove from unconnected pool
                del client_by_name[normalized_org_name]
                continue

            # No match found
            unmatched_connections.append(
                {
                    "connection_id": str(connection.id),
                    "org_name": connection.organization_name,
                    "xero_tenant_id": connection.xero_tenant_id,
                }
            )

        # Remaining clients are unmatched
        unmatched_clients = [
            {
                "client_id": str(client.id),
                "client_name": client.name,
                "xpm_client_id": client.xpm_client_id,
            }
            for client in client_by_name.values()
        ]

        logger.info(
            "Matched Xero connections to XPM clients for tenant %s: "
            "%d matched, %d unmatched connections, %d unmatched clients",
            tenant_id,
            len(matched),
            len(unmatched_connections),
            len(unmatched_clients),
        )

        return {
            "matched": matched,
            "unmatched_connections": unmatched_connections,
            "unmatched_clients": unmatched_clients,
        }

    async def link_client_to_connection(
        self,
        client_id: UUID,
        connection_id: UUID,
    ) -> XpmClientResponse:
        """Manually link an XPM client to a Xero connection.

        Used when automatic matching fails and user manually selects which
        Xero organization belongs to which client.

        Args:
            client_id: The XPM client ID.
            connection_id: The XeroConnection ID to link.

        Returns:
            Updated XpmClientResponse.

        Raises:
            XpmClientNotFoundError: If client not found.
            XeroConnectionNotFoundError: If connection not found.
        """
        # Verify client exists
        client = await self.xpm_client_repo.get_by_id(client_id)
        if not client:
            raise XpmClientNotFoundError(client_id)

        # Verify connection exists
        connection = await self.connection_repo.get_by_id(connection_id)
        if not connection:
            raise XeroConnectionNotFoundExc(connection_id)

        # Link them
        updated_client = await self.xpm_client_repo.link_xero_connection(
            client_id=client_id,
            xero_connection_id=connection_id,
            xero_org_name=connection.organization_name,
        )

        logger.info(
            "Linked XPM client %s to Xero connection %s (%s)",
            client_id,
            connection_id,
            connection.organization_name,
        )

        return XpmClientResponse.model_validate(updated_client)

    async def unlink_client_from_connection(
        self,
        client_id: UUID,
        reason: str | None = None,
    ) -> XpmClientResponse:
        """Unlink an XPM client from its Xero connection.

        Args:
            client_id: The XPM client ID.
            reason: Optional reason for unlinking (for audit).

        Returns:
            Updated XpmClientResponse.

        Raises:
            XpmClientNotFoundError: If client not found.
        """
        client = await self.xpm_client_repo.get_by_id(client_id)
        if not client:
            raise XpmClientNotFoundError(client_id)

        updated_client = await self.xpm_client_repo.unlink_xero_connection(
            client_id=client_id,
            mark_as_disconnected=True,
        )

        logger.info(
            "Unlinked XPM client %s from Xero connection. Reason: %s",
            client_id,
            reason or "Not specified",
        )

        return XpmClientResponse.model_validate(updated_client)

    async def list_xpm_clients(
        self,
        tenant_id: UUID,
        connection_status: XpmClientConnectionStatus | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> XpmClientListResponse:
        """List XPM clients for a tenant with filtering.

        Args:
            tenant_id: The tenant ID.
            connection_status: Filter by connection status.
            search: Search by name.
            limit: Max results.
            offset: Pagination offset.

        Returns:
            XpmClientListResponse with clients and pagination info.
        """
        clients, total = await self.xpm_client_repo.list_by_tenant(
            tenant_id=tenant_id,
            connection_status=connection_status,
            search=search,
            limit=limit,
            offset=offset,
        )

        return XpmClientListResponse(
            clients=[XpmClientResponse.model_validate(c) for c in clients],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_connection_progress(
        self,
        tenant_id: UUID,
    ) -> XpmClientConnectionProgress:
        """Get connection progress summary for a tenant.

        Shows how many XPM clients have their Xero organizations connected.

        Args:
            tenant_id: The tenant ID.

        Returns:
            XpmClientConnectionProgress with status counts and rates.
        """
        counts = await self.xpm_client_repo.count_by_connection_status(tenant_id)
        total = sum(counts.values())

        connected = counts.get("connected", 0)
        connection_rate = connected / total if total > 0 else 0.0

        return XpmClientConnectionProgress(
            status_counts=XpmClientStatusCounts(
                not_connected=counts.get("not_connected", 0),
                connected=connected,
                disconnected=counts.get("disconnected", 0),
                no_access=counts.get("no_access", 0),
                total=total,
            ),
            connection_rate=connection_rate,
            all_connected=(connected == total and total > 0),
        )

    async def link_client_by_tenant_id(
        self,
        client_id: UUID,
        xero_tenant_id: str,
        tenant_id: UUID,
    ) -> XpmClientResponse:
        """Link an XPM client to a Xero connection by Xero tenant ID.

        Alternative to link_client_to_connection that uses Xero's tenant ID
        instead of our internal connection UUID.

        Args:
            client_id: The XPM client ID.
            xero_tenant_id: The Xero organization's tenant ID.
            tenant_id: The tenant ID for scoping.

        Returns:
            Updated XpmClientResponse.

        Raises:
            XpmClientNotFoundError: If client not found.
            XeroConnectionNotFoundError: If no connection with that tenant ID.
        """
        # Verify client exists
        client = await self.xpm_client_repo.get_by_id(client_id)
        if not client:
            raise XpmClientNotFoundError(client_id)

        # Find connection by Xero tenant ID
        connection = await self.connection_repo.get_by_xero_tenant_id(
            xero_tenant_id=xero_tenant_id,
            tenant_id=tenant_id,
        )
        if not connection:
            raise XeroConnectionNotFoundExc(
                f"No Xero connection found with tenant ID: {xero_tenant_id}"
            )

        # Link them
        updated_client = await self.xpm_client_repo.link_xero_connection(
            client_id=client_id,
            xero_connection_id=connection.id,
            xero_org_name=connection.organization_name,
        )

        logger.info(
            "Linked XPM client %s to Xero org %s (tenant_id: %s)",
            client_id,
            connection.organization_name,
            xero_tenant_id,
        )

        return XpmClientResponse.model_validate(updated_client)

    async def get_unmatched_connections(
        self,
        tenant_id: UUID,
    ) -> list[XeroConnectionResponse]:
        """Get Xero connections that aren't linked to any XPM client.

        These are organizations the accountant has authorized but couldn't be
        automatically matched to an XPM client (by name or email).

        Args:
            tenant_id: The tenant ID.

        Returns:
            List of XeroConnectionResponse for unmatched connections.
        """
        # Get all XPM clients with their connection IDs
        clients, _ = await self.xpm_client_repo.list_by_tenant(
            tenant_id=tenant_id,
            limit=10000,  # Get all clients
            offset=0,
        )
        linked_connection_ids = {c.xero_connection_id for c in clients if c.xero_connection_id}

        # Get all active Xero connections for tenant
        all_connections = await self.connection_repo.list_by_tenant(tenant_id)

        # Filter to only unmatched (not linked to any client)
        unmatched = [
            conn
            for conn in all_connections
            if conn.id not in linked_connection_ids
            and conn.status != XeroConnectionStatus.DISCONNECTED
        ]

        return [XeroConnectionResponse.model_validate(conn) for conn in unmatched]
