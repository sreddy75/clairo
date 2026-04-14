"""Bulk import service — multi-org OAuth flow for importing multiple Xero client organizations."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.modules.auth.models import Tenant
from app.modules.integrations.xero.client import XeroClient
from app.modules.integrations.xero.encryption import TokenEncryption
from app.modules.integrations.xero.exceptions import (
    BulkImportInProgressError,
    BulkImportValidationError,
    XeroOAuthError,
)
from app.modules.integrations.xero.models import XeroConnection
from app.modules.integrations.xero.oauth import (
    build_authorization_url,
    generate_code_challenge,
    generate_code_verifier,
    generate_state,
)
from app.modules.integrations.xero.repository import (
    XeroConnectionRepository,
    XeroOAuthStateRepository,
)
from app.modules.integrations.xero.schemas import (
    ImportOrganization,
    XeroConnectionCreate,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Bulk Import Service (Phase 035)
# =============================================================================


class BulkImportService:
    """Service for bulk importing multiple Xero client organizations.

    Handles the multi-org OAuth flow:
    1. initiate_bulk_import() - Generate auth URL with is_bulk_import=True
    2. handle_bulk_callback() - Process callback, return all authorized orgs
    3. confirm_bulk_import() - Create connections, BulkImportJob, queue sync
    """

    # Uncertified Xero app limit
    XERO_ORG_LIMIT = 25

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        """Initialize bulk import service.

        Args:
            session: Database session.
            settings: Application settings.
        """
        from app.core.audit import AuditService
        from app.modules.onboarding.repository import (
            BulkImportJobRepository,
            BulkImportOrganizationRepository,
        )

        self.session = session
        self.settings = settings
        self.state_repo = XeroOAuthStateRepository(session)
        self.connection_repo = XeroConnectionRepository(session)
        self.encryption = TokenEncryption(settings.token_encryption.key.get_secret_value())
        self.job_repo = BulkImportJobRepository(session)
        self.org_repo = BulkImportOrganizationRepository(session)
        self.audit_service = AuditService(session)
        self.logger = logging.getLogger(__name__)

    async def initiate_bulk_import(
        self,
        tenant_id: UUID,
        user_id: UUID,
        redirect_uri: str,
    ) -> dict[str, str]:
        """Initiate a bulk import OAuth flow.

        Checks for concurrent imports, creates OAuth state with is_bulk_import=True,
        and generates the Xero authorization URL.

        Args:
            tenant_id: The tenant (accounting practice) ID.
            user_id: The user initiating the import.
            redirect_uri: Frontend URL to redirect back to after OAuth.

        Returns:
            Dict with auth_url and state token.

        Raises:
            BulkImportInProgressError: If a bulk import is already in progress.
        """
        from app.modules.onboarding.models import BulkImportJobStatus

        # Check for concurrent bulk import (FR-017)
        active_jobs = await self.job_repo.list_by_tenant(
            tenant_id, status=BulkImportJobStatus.IN_PROGRESS
        )
        if active_jobs:
            raise BulkImportInProgressError(tenant_id, active_jobs[0].id)

        # Also check PENDING jobs (queued but not yet started)
        pending_jobs = await self.job_repo.list_by_tenant(
            tenant_id, status=BulkImportJobStatus.PENDING
        )
        # Only block on pending jobs that are xero_bulk_oauth source type
        pending_bulk = [j for j in pending_jobs if j.source_type == "xero_bulk_oauth"]
        if pending_bulk:
            raise BulkImportInProgressError(tenant_id, pending_bulk[0].id)

        # Generate PKCE parameters
        code_verifier = generate_code_verifier()
        code_challenge = generate_code_challenge(code_verifier)
        state = generate_state()

        # Store state for callback validation with bulk import flag
        expires_at = datetime.now(UTC) + timedelta(minutes=10)
        await self.state_repo.create(
            tenant_id=tenant_id,
            user_id=user_id,
            state=state,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
            expires_at=expires_at,
            is_bulk_import=True,
        )

        # Build authorization URL
        auth_url = build_authorization_url(
            settings=self.settings.xero,
            state=state,
            code_challenge=code_challenge,
            redirect_uri=self.settings.xero.redirect_uri,
        )

        # Audit event
        await self.audit_service.log_event(
            event_type="integration.xero.bulk_import.start",
            event_category="integration",
            resource_type="bulk_import",
            resource_id=tenant_id,
            action="create",
            outcome="success",
            tenant_id=tenant_id,
            new_values={"user_id": str(user_id), "redirect_uri": redirect_uri},
        )

        self.logger.info(
            "Bulk import OAuth initiated",
            extra={"tenant_id": str(tenant_id), "user_id": str(user_id)},
        )

        return {"auth_url": auth_url, "state": state}

    async def handle_bulk_callback(
        self,
        code: str,
        state: str,
    ) -> dict[str, Any]:
        """Handle OAuth callback for bulk import.

        Validates state, exchanges code for tokens, fetches all authorized orgs,
        identifies new vs already-connected, and returns the list for configuration.
        Does NOT create connections yet - that happens on confirm.

        Args:
            code: Authorization code from Xero.
            state: State parameter for CSRF validation.

        Returns:
            Dict with auth_event_id, organizations, counts, and plan limits.

        Raises:
            XeroOAuthError: If state is invalid or token exchange fails.
        """
        from app.core.feature_flags import get_client_limit
        from app.modules.integrations.xero.schemas import ImportOrganization

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

        # Verify this is a bulk import flow
        if not oauth_state.is_bulk_import:
            raise XeroOAuthError("State is not for bulk import flow")

        # Mark state as used
        await self.state_repo.mark_as_used(oauth_state.id)

        # Exchange code for tokens
        async with XeroClient(self.settings.xero) as client:
            token_response, token_expires_at = await client.exchange_code(
                code=code,
                code_verifier=oauth_state.code_verifier,
                redirect_uri=self.settings.xero.redirect_uri,
            )

            # Get ALL connected organizations
            all_orgs = await client.get_connections(token_response.access_token)

        if not all_orgs:
            raise XeroOAuthError("No organizations authorized")

        # Store tokens temporarily for use during confirm step
        # We encrypt and store on the OAuth state record for retrieval
        encrypted_access = self.encryption.encrypt(token_response.access_token)
        encrypted_refresh = self.encryption.encrypt(token_response.refresh_token)

        # Filter to orgs from this auth event (FR-002)
        # If auth_event_id is available, use it; otherwise include all
        auth_event_id = None
        if all_orgs[0].auth_event_id:
            auth_event_id = all_orgs[0].auth_event_id

        # Get existing connections for this tenant
        existing_connections = await self.connection_repo.list_by_tenant(
            tenant_id=oauth_state.tenant_id,
            include_disconnected=False,
        )
        existing_xero_ids = {conn.xero_tenant_id: conn for conn in existing_connections}

        # Build organization list with already_connected status
        organizations: list[ImportOrganization] = []
        already_connected_count = 0
        new_count = 0

        for org in all_orgs:
            existing_conn = existing_xero_ids.get(org.id)
            is_connected = existing_conn is not None
            if is_connected:
                already_connected_count += 1
            else:
                new_count += 1

            organizations.append(
                ImportOrganization(
                    xero_tenant_id=org.id,
                    organization_name=org.display_name,
                    already_connected=is_connected,
                    existing_connection_id=existing_conn.id if existing_conn else None,
                )
            )

        # Check subscription tier limit (FR-006)
        from sqlalchemy import select as sa_select

        tenant = await self.session.scalar(
            sa_select(Tenant).where(Tenant.id == oauth_state.tenant_id)
        )

        plan_limit = 0
        current_client_count = 0
        available_slots = 0
        if tenant:
            tier_value: str = tenant.tier.value  # type: ignore[assignment]
            limit = get_client_limit(tier_value)
            plan_limit = limit if limit is not None else 999999
            current_client_count = tenant.client_count
            available_slots = (
                max(0, plan_limit - current_client_count) if limit is not None else 999999
            )

        # Check uncertified app limit (FR-007)
        total_orgs = len(all_orgs)
        if total_orgs > self.XERO_ORG_LIMIT:
            self.logger.warning(
                "Bulk import: org count exceeds uncertified app limit",
                extra={
                    "tenant_id": str(oauth_state.tenant_id),
                    "org_count": total_orgs,
                    "limit": self.XERO_ORG_LIMIT,
                },
            )

        # Store encrypted tokens on the state for retrieval during confirm
        # Using the state record's redirect_uri field is insufficient,
        # so we store tokens in a temporary approach via session state
        # We'll store the tokens keyed by auth_event_id for confirm step
        from app.modules.integrations.xero.models import XeroOAuthState

        oauth_state_record = await self.session.get(XeroOAuthState, oauth_state.id)
        if oauth_state_record:
            # Store encrypted tokens in the redirect_uri field as JSON
            # (This field is no longer needed after callback)
            import json

            token_data = json.dumps(
                {
                    "access_token": encrypted_access,
                    "refresh_token": encrypted_refresh,
                    "token_expires_at": token_expires_at.isoformat(),
                    "scopes": token_response.scopes_list,
                }
            )
            oauth_state_record.redirect_uri = token_data

        # Audit event
        await self.audit_service.log_event(
            event_type="integration.xero.oauth.multi_org",
            event_category="integration",
            resource_type="bulk_import",
            resource_id=oauth_state.tenant_id,
            action="read",
            outcome="success",
            tenant_id=oauth_state.tenant_id,
            new_values={
                "auth_event_id": auth_event_id,
                "total_orgs": total_orgs,
                "new_count": new_count,
                "already_connected_count": already_connected_count,
            },
        )

        self.logger.info(
            "Bulk import callback processed",
            extra={
                "tenant_id": str(oauth_state.tenant_id),
                "auth_event_id": auth_event_id,
                "total_orgs": total_orgs,
                "new_orgs": new_count,
                "already_connected": already_connected_count,
            },
        )

        # Auto-match organizations to existing clients (T025 - US4)
        org_dicts = [org.model_dump() for org in organizations]
        org_dicts = await self.match_orgs_to_clients(
            tenant_id=oauth_state.tenant_id,
            organizations=org_dicts,
        )

        return {
            "auth_event_id": auth_event_id or "",
            "organizations": org_dicts,
            "already_connected_count": already_connected_count,
            "new_count": new_count,
            "plan_limit": plan_limit,
            "current_client_count": current_client_count,
            "available_slots": available_slots,
            "state": state,  # Needed by confirm to retrieve tokens
        }

    async def confirm_bulk_import(
        self,
        tenant_id: UUID,
        user_id: UUID,
        state: str,
        auth_event_id: str,
        organizations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Confirm selected organizations and start bulk import.

        Creates XeroConnection records for selected orgs, creates a BulkImportJob,
        creates BulkImportOrganization records, and queues Celery sync tasks.

        Args:
            tenant_id: The tenant ID.
            user_id: The user confirming the import.
            state: OAuth state token (used to retrieve stored tokens).
            auth_event_id: Authorization event ID grouping the orgs.
            organizations: List of org selections with configuration.

        Returns:
            Dict with job details.

        Raises:
            BulkImportInProgressError: If import already in progress.
            BulkImportValidationError: If validation fails.
            XeroOAuthError: If tokens cannot be retrieved.
        """
        from app.core.feature_flags import get_client_limit
        from app.modules.onboarding.models import (
            BulkImportJob,
            BulkImportJobStatus,
        )

        # Check for concurrent bulk import (FR-017)
        active_jobs = await self.job_repo.list_by_tenant(
            tenant_id, status=BulkImportJobStatus.IN_PROGRESS
        )
        if active_jobs:
            raise BulkImportInProgressError(tenant_id, active_jobs[0].id)

        # Retrieve stored tokens from the OAuth state
        import json

        oauth_state = await self.state_repo.get_by_state(state)
        if oauth_state is None:
            raise XeroOAuthError("OAuth state not found - session may have expired")

        try:
            token_data = json.loads(oauth_state.redirect_uri)
            encrypted_access = token_data["access_token"]
            encrypted_refresh = token_data["refresh_token"]
            token_expires_at = datetime.fromisoformat(token_data["token_expires_at"])
            scopes = token_data.get("scopes", [])
        except (json.JSONDecodeError, KeyError) as e:
            raise XeroOAuthError(f"Failed to retrieve stored tokens: {e}") from e

        # Separate selected vs deselected orgs
        selected_orgs = [o for o in organizations if o.get("selected", False)]
        deselected_orgs = [o for o in organizations if not o.get("selected", False)]

        if not selected_orgs:
            raise BulkImportValidationError("No organizations selected for import")

        # Check subscription tier limit (FR-006)
        from sqlalchemy import select as sa_select

        tenant = await self.session.scalar(sa_select(Tenant).where(Tenant.id == tenant_id))

        if tenant:
            tier_value: str = tenant.tier.value  # type: ignore[assignment]
            limit = get_client_limit(tier_value)
            if limit is not None:
                available = max(0, limit - tenant.client_count)
                # Count only genuinely new orgs (not already connected)
                new_selected = [o for o in selected_orgs if not o.get("already_connected", False)]
                if len(new_selected) > available:
                    raise BulkImportValidationError(
                        f"Selection exceeds plan limit. "
                        f"Available slots: {available}, selected: {len(new_selected)}. "
                        f"Please deselect some organizations or upgrade your plan."
                    )

        # Check payroll scopes
        payroll_scopes = ["payroll.employees", "payroll.payruns"]
        has_payroll = all(scope in scopes for scope in payroll_scopes)

        # Create XeroConnections for each selected NEW org
        created_connections: dict[str, XeroConnection] = {}
        for org_selection in selected_orgs:
            xero_tenant_id = org_selection["xero_tenant_id"]

            # Skip already-connected orgs
            if org_selection.get("already_connected", False):
                continue

            connection_type = org_selection.get("connection_type", "client")

            # Create XeroConnection with shared tokens
            connection = await self.connection_repo.create(
                XeroConnectionCreate(
                    tenant_id=tenant_id,
                    xero_tenant_id=xero_tenant_id,
                    organization_name=org_selection.get(
                        "organization_name", f"Org {xero_tenant_id[:8]}"
                    ),
                    access_token=encrypted_access,
                    refresh_token=encrypted_refresh,
                    token_expires_at=token_expires_at,
                    scopes=scopes,
                    connected_by=user_id,
                    has_payroll_access=has_payroll,
                    auth_event_id=auth_event_id,
                    connection_type=connection_type,
                )
            )

            created_connections[xero_tenant_id] = connection

            # Audit per-connection creation
            await self.audit_service.log_event(
                event_type="integration.xero.connection.created",
                event_category="integration",
                resource_type="xero_connection",
                resource_id=connection.id,
                action="create",
                outcome="success",
                tenant_id=tenant_id,
                new_values={
                    "xero_tenant_id": xero_tenant_id,
                    "organization_name": org_selection.get("organization_name", ""),
                    "connection_type": connection_type,
                    "auth_event_id": auth_event_id,
                    "bulk_import": True,
                },
            )

        # Create BulkImportJob
        all_client_ids = [o["xero_tenant_id"] for o in selected_orgs]
        job = BulkImportJob(
            tenant_id=tenant_id,
            status=BulkImportJobStatus.PENDING,
            source_type="xero_bulk_oauth",
            total_clients=len(selected_orgs),
            client_ids=all_client_ids,
        )
        job = await self.job_repo.create(job)

        # Create BulkImportOrganization records for ALL orgs (selected + deselected)
        org_records: list[dict[str, Any]] = []

        for org_selection in selected_orgs:
            xero_tenant_id = org_selection["xero_tenant_id"]
            is_already_connected = org_selection.get("already_connected", False)
            conn = created_connections.get(xero_tenant_id)

            status = "pending"
            if is_already_connected:
                status = "skipped"

            org_records.append(
                {
                    "tenant_id": tenant_id,
                    "bulk_import_job_id": job.id,
                    "xero_tenant_id": xero_tenant_id,
                    "organization_name": org_selection.get(
                        "organization_name", f"Org {xero_tenant_id[:8]}"
                    ),
                    "status": status,
                    "connection_id": conn.id if conn else None,
                    "connection_type": org_selection.get("connection_type", "client"),
                    "assigned_user_id": (
                        UUID(org_selection["assigned_user_id"])
                        if org_selection.get("assigned_user_id")
                        else None
                    ),
                    "already_connected": is_already_connected,
                    "selected_for_import": True,
                }
            )

        for org_selection in deselected_orgs:
            org_records.append(
                {
                    "tenant_id": tenant_id,
                    "bulk_import_job_id": job.id,
                    "xero_tenant_id": org_selection["xero_tenant_id"],
                    "organization_name": org_selection.get(
                        "organization_name", f"Org {org_selection['xero_tenant_id'][:8]}"
                    ),
                    "status": "skipped",
                    "connection_type": org_selection.get("connection_type", "client"),
                    "already_connected": org_selection.get("already_connected", False),
                    "selected_for_import": False,
                }
            )

        if org_records:
            await self.org_repo.bulk_create(org_records)

        # Calculate counts
        skipped = len([o for o in org_records if o["status"] == "skipped"])

        self.logger.info(
            "Bulk import confirmed",
            extra={
                "tenant_id": str(tenant_id),
                "job_id": str(job.id),
                "selected_count": len(selected_orgs),
                "deselected_count": len(deselected_orgs),
                "connections_created": len(created_connections),
            },
        )

        # Queue Celery task for bulk sync (T020)
        from app.tasks.celery_app import celery_app

        celery_app.send_task(
            "app.tasks.xero.run_bulk_xero_import",
            kwargs={
                "job_id": str(job.id),
                "tenant_id": str(tenant_id),
            },
        )

        return {
            "job_id": job.id,
            "status": job.status.value,
            "total_organizations": job.total_clients,
            "imported_count": 0,
            "failed_count": 0,
            "skipped_count": skipped,
            "progress_percent": 0,
            "created_at": job.created_at,
        }

    # =========================================================================
    # App-Wide Rate Limit (T021)
    # =========================================================================

    @staticmethod
    async def check_app_rate_limit() -> bool:
        """Check if app-wide Xero rate limit allows more requests.

        Uses Redis counter for the current minute window.

        Returns:
            True if requests can proceed, False if rate limited.
        """
        try:
            import redis.asyncio as aioredis

            from app.config import get_settings

            settings = get_settings()
            client = aioredis.from_url(settings.redis.url)

            minute_key = f"xero:app_rate_limit:{int(datetime.now(UTC).timestamp()) // 60}"
            remaining = await client.get(minute_key)
            await client.aclose()

            if remaining is not None and int(remaining) < 500:
                return False
            return True
        except Exception:
            # If Redis is unavailable, allow requests (fail open)
            return True

    @staticmethod
    async def update_app_rate_limit(remaining: int) -> None:
        """Update the app-wide rate limit counter from Xero response header.

        Args:
            remaining: Value from X-AppMinLimit-Remaining header.
        """
        try:
            import redis.asyncio as aioredis

            from app.config import get_settings

            settings = get_settings()
            client = aioredis.from_url(settings.redis.url)

            minute_key = f"xero:app_rate_limit:{int(datetime.now(UTC).timestamp()) // 60}"
            await client.set(minute_key, remaining, ex=60)
            await client.aclose()
        except Exception:
            pass  # Best-effort

    # =========================================================================
    # Auto-Matching (T025 - US4)
    # =========================================================================

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize organization name for matching.

        Strips common suffixes like "Pty Ltd", "Pty", "Ltd" and normalizes
        whitespace and case.
        """
        import re

        normalized = name.lower().strip()
        # Remove common Australian business suffixes
        for suffix in ["pty ltd", "pty. ltd.", "pty. ltd", "pty ltd.", "limited", "pty", "ltd"]:
            if normalized.endswith(suffix):
                normalized = normalized[: -len(suffix)].strip()
        # Remove extra whitespace
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    @staticmethod
    def _jaccard_similarity(name_a: str, name_b: str) -> float:
        """Calculate Jaccard similarity between two names based on word tokens."""
        tokens_a = set(name_a.lower().split())
        tokens_b = set(name_b.lower().split())
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        return len(intersection) / len(union) if union else 0.0

    async def match_orgs_to_clients(
        self,
        tenant_id: UUID,
        organizations: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Match imported Xero organizations against existing client records.

        Two-pass matching (R6):
        1. Exact match on normalized names
        2. Fuzzy match with Jaccard similarity > 0.8

        Args:
            tenant_id: The tenant ID.
            organizations: List of org dicts with xero_tenant_id and organization_name.

        Returns:
            Updated list with match_status and matched_client_name fields set.
        """
        # Get existing connections (which represent connected client businesses)
        existing_connections = await self.connection_repo.list_by_tenant(
            tenant_id=tenant_id,
            include_disconnected=False,
        )

        # Build normalized name lookup
        existing_names: dict[str, str] = {}  # normalized_name -> original_name
        for conn in existing_connections:
            if conn.organization_name:
                norm = self._normalize_name(conn.organization_name)
                existing_names[norm] = conn.organization_name

        for org in organizations:
            org_name = org.get("organization_name", "")
            norm_org = self._normalize_name(org_name)

            # Pass 1: Exact match
            if norm_org in existing_names:
                org["match_status"] = "matched"
                org["matched_client_name"] = existing_names[norm_org]
                continue

            # Pass 2: Fuzzy match
            best_score = 0.0
            best_match = None
            for norm_existing, original_name in existing_names.items():
                score = self._jaccard_similarity(norm_org, norm_existing)
                if score > best_score:
                    best_score = score
                    best_match = original_name

            if best_score >= 0.8 and best_match:
                org["match_status"] = "suggested"
                org["matched_client_name"] = best_match
            else:
                org["match_status"] = "unmatched"
                org["matched_client_name"] = None

        return organizations
