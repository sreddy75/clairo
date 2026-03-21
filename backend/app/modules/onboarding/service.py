"""Business logic for onboarding flow.

Provides service methods for:
- Starting and tracking onboarding progress
- Tier selection and Stripe checkout
- Xero connection
- Bulk client import
- Product tour
- Checklist management
- Email drip sequence
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger
from app.modules.auth.repository import TenantRepository
from app.modules.billing.schemas import SubscriptionTierType
from app.modules.billing.service import BillingService
from app.modules.onboarding.models import (
    BulkImportJob,
    BulkImportJobStatus,
    EmailDrip,
    OnboardingProgress,
    OnboardingStatus,
)
from app.modules.onboarding.repository import (
    BulkImportJobRepository,
    EmailDripRepository,
    OnboardingRepository,
)
from app.modules.onboarding.schemas import (
    AvailableClient,
    ChecklistItem,
    OnboardingChecklist,
)

# Default trial period for new subscriptions
DEFAULT_TRIAL_DAYS = 14

logger = get_logger(__name__)


class OnboardingService:
    """Service for managing onboarding flow."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize service with database session."""
        self.session = session
        self.onboarding_repo = OnboardingRepository(session)
        self.import_job_repo = BulkImportJobRepository(session)
        self.email_drip_repo = EmailDripRepository(session)
        self.tenant_repo = TenantRepository(session)
        self.billing_service = BillingService(session)

    # =========================================================================
    # Progress Management
    # =========================================================================

    async def get_progress(self, tenant_id: UUID) -> OnboardingProgress | None:
        """Get onboarding progress for a tenant."""
        return await self.onboarding_repo.get_by_tenant_id(tenant_id)

    async def start_onboarding(self, tenant_id: UUID) -> OnboardingProgress:
        """Start onboarding for a new tenant.

        Creates OnboardingProgress record with status=STARTED.
        Emits audit event and sends welcome email.
        """
        progress, created = await self.onboarding_repo.get_or_create(tenant_id)

        if created:
            logger.info("Onboarding started", tenant_id=str(tenant_id))
            # TODO: Emit OnboardingStartedEvent
            # TODO: Send welcome email

        return progress

    async def get_or_start_onboarding(self, tenant_id: UUID) -> OnboardingProgress:
        """Get existing progress or start new onboarding."""
        progress, _ = await self.onboarding_repo.get_or_create(tenant_id)
        return progress

    # =========================================================================
    # Tier Selection
    # =========================================================================

    async def select_tier(
        self,
        tenant_id: UUID,
        tier: SubscriptionTierType,
        with_trial: bool = True,
    ) -> OnboardingProgress:
        """Select subscription tier and start free trial server-side.

        Creates a Stripe trial subscription directly (no checkout redirect).
        No credit card required upfront. Idempotent — if tenant already has
        a subscription, updates the tier and proceeds without error.

        Args:
            tenant_id: Tenant ID
            tier: Subscription tier (starter/professional/growth/enterprise)
            with_trial: Whether to include 14-day free trial (default: True)

        Returns:
            Updated OnboardingProgress

        Raises:
            ValueError: If tenant not found or tier is enterprise
        """
        progress = await self.get_or_start_onboarding(tenant_id)

        # Get tenant for billing
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        subscription_id = tenant.stripe_subscription_id

        if subscription_id:
            # Tenant already has a subscription (previous attempt or old flow).
            # Just update the tier on the tenant and proceed with onboarding.
            tenant.tier = tier  # type: ignore[assignment]
            await self.session.flush()
            logger.info(
                "Tier updated on existing subscription",
                tenant_id=str(tenant_id),
                tier=tier,
                subscription_id=subscription_id,
            )
        else:
            # Create trial subscription server-side (no Stripe Checkout redirect)
            trial_days = DEFAULT_TRIAL_DAYS if with_trial else None
            result = await self.billing_service.start_trial(
                tenant=tenant,
                tier=tier,
                trial_period_days=trial_days or DEFAULT_TRIAL_DAYS,
            )
            subscription_id = result["id"]

        # Update progress — go straight to PAYMENT_SETUP (skip TIER_SELECTED)
        now = datetime.now(UTC)
        await self.onboarding_repo.update(
            progress.id,
            {
                "status": OnboardingStatus.PAYMENT_SETUP,
                "tier_selected_at": now,
                "payment_setup_at": now,
                "current_step": "connect_xero",
                "extra_data": {
                    **progress.extra_data,
                    "selected_tier": tier,
                    "subscription_id": subscription_id,
                    "trial_days": DEFAULT_TRIAL_DAYS,
                },
            },
        )

        logger.info(
            "Tier selected and trial started",
            tenant_id=str(tenant_id),
            tier=tier,
            subscription_id=subscription_id,
        )

        # Refresh progress to get updated data
        progress = await self.onboarding_repo.get_by_tenant_id(tenant_id)
        return progress  # type: ignore

    async def complete_payment(self, tenant_id: UUID, session_id: str) -> OnboardingProgress:
        """Mark payment setup as complete after Stripe checkout.

        .. deprecated::
            This method is deprecated. Trial subscriptions are now created
            server-side in select_tier(). Kept for any in-flight edge cases
            where a user completed Stripe Checkout before the migration.

        Args:
            tenant_id: Tenant ID
            session_id: Stripe checkout session ID

        This method retrieves the Stripe checkout session, extracts the
        selected tier from metadata, and updates the tenant's tier accordingly.
        """
        import stripe

        from app.modules.auth.models import SubscriptionStatus, SubscriptionTier

        progress = await self.get_or_start_onboarding(tenant_id)

        # Get tenant to update tier
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        # Retrieve Stripe checkout session to get tier from metadata
        try:
            settings = get_settings()
            stripe.api_key = settings.stripe.secret_key.get_secret_value()

            checkout_session = stripe.checkout.Session.retrieve(
                session_id,
                expand=["subscription"],
            )

            # Get tier from session or subscription metadata
            tier_str = None

            # Try subscription metadata first (most reliable)
            if checkout_session.subscription:
                sub = checkout_session.subscription
                if hasattr(sub, "metadata") and sub.metadata:
                    tier_str = sub.metadata.get("tier")

            # Fall back to session metadata
            if not tier_str and checkout_session.metadata:
                tier_str = checkout_session.metadata.get("tier")

            # Update tenant tier if we found it
            if tier_str:
                try:
                    new_tier = SubscriptionTier(tier_str)
                    tenant.tier = new_tier
                    logger.info(
                        "Updated tenant tier from checkout session",
                        tenant_id=str(tenant_id),
                        tier=tier_str,
                        session_id=session_id,
                    )
                except ValueError:
                    logger.warning(
                        "Invalid tier in checkout session metadata",
                        tier=tier_str,
                        tenant_id=str(tenant_id),
                    )
            else:
                logger.warning(
                    "No tier found in checkout session metadata",
                    tenant_id=str(tenant_id),
                    session_id=session_id,
                )

            # Update subscription ID and status if subscription exists
            if checkout_session.subscription:
                sub = checkout_session.subscription
                sub_id = sub.id if hasattr(sub, "id") else str(sub)
                tenant.stripe_subscription_id = sub_id

                # Check subscription status
                if hasattr(sub, "status"):
                    if sub.status == "trialing":
                        tenant.subscription_status = SubscriptionStatus.TRIAL
                    elif sub.status == "active":
                        tenant.subscription_status = SubscriptionStatus.ACTIVE

            await self.session.flush()

        except stripe.StripeError as e:
            logger.error(
                "Failed to retrieve Stripe checkout session",
                error=str(e),
                session_id=session_id,
                tenant_id=str(tenant_id),
            )
            # Continue with onboarding even if Stripe call fails
            # The webhook will handle the tier update as backup

        await self.onboarding_repo.update(
            progress.id,
            {
                "status": OnboardingStatus.PAYMENT_SETUP,
                "payment_setup_at": datetime.now(UTC),
                "current_step": "connect_xero",
            },
        )

        logger.info("Payment setup complete", tenant_id=str(tenant_id), session_id=session_id)

        # Refresh to get updated data
        progress = await self.onboarding_repo.get_by_tenant_id(tenant_id)
        return progress  # type: ignore

    # =========================================================================
    # Xero Connection
    # =========================================================================

    async def initiate_xero_connect(
        self, tenant_id: UUID, user_id: UUID, frontend_redirect_uri: str
    ) -> str:
        """Generate Xero OAuth URL with appropriate scopes.

        Args:
            tenant_id: The tenant initiating OAuth.
            user_id: The user initiating OAuth.
            frontend_redirect_uri: Where to redirect after OAuth completes.

        Returns:
            Xero OAuth authorization URL
        """
        from app.config import get_settings
        from app.modules.integrations.xero.service import XeroOAuthService

        settings = get_settings()
        oauth_service = XeroOAuthService(session=self.session, settings=settings)

        response = await oauth_service.generate_auth_url(
            tenant_id=tenant_id,
            user_id=user_id,
            frontend_redirect_uri=frontend_redirect_uri,
        )

        return response.auth_url

    async def complete_xero_connect(
        self, tenant_id: UUID, code: str, state: str
    ) -> OnboardingProgress:
        """Handle Xero OAuth callback.

        Args:
            tenant_id: Tenant ID
            code: OAuth authorization code
            state: OAuth state parameter
        """
        progress = await self.get_or_start_onboarding(tenant_id)

        # TODO: Exchange code for tokens
        # TODO: Detect XPM vs Xero Accounting

        await self.onboarding_repo.update(
            progress.id,
            {
                "status": OnboardingStatus.XERO_CONNECTED,
                "xero_connected_at": datetime.now(UTC),
                "current_step": "import_clients",
            },
        )

        logger.info("Xero connected", tenant_id=str(tenant_id))

        progress = await self.onboarding_repo.get_by_tenant_id(tenant_id)
        return progress  # type: ignore

    async def skip_xero(self, tenant_id: UUID) -> OnboardingProgress:
        """Skip Xero connection step."""
        progress = await self.get_or_start_onboarding(tenant_id)

        await self.onboarding_repo.update(
            progress.id,
            {
                "status": OnboardingStatus.SKIPPED_XERO,
                "xero_skipped": True,
                "current_step": "product_tour",
            },
        )

        logger.info("Xero connection skipped", tenant_id=str(tenant_id))

        progress = await self.onboarding_repo.get_by_tenant_id(tenant_id)
        return progress  # type: ignore

    # =========================================================================
    # Client Import
    # =========================================================================

    async def get_available_clients(
        self,
        tenant_id: UUID,
        search: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """Get clients available for import from Xero/XPM.

        Returns dict with clients, total, source_type, tier_limit, current_count.
        Includes Xero org connection status for each client.
        """
        # Import here to avoid circular dependency
        from app.modules.integrations.xero.service import XpmClientService

        settings = get_settings()
        xpm_service = XpmClientService(self.session, settings)

        # Fetch XPM clients with their Xero org connection status
        xpm_clients = await xpm_service.list_xpm_clients(
            tenant_id=tenant_id,
            search=search,
            page=page,
            page_size=page_size,
        )

        # Get tier limit from billing service
        tier_limit = await self.billing_service.get_client_limit(tenant_id)
        current_count = await self.billing_service.get_current_client_count(tenant_id)

        # Transform XPM clients to AvailableClient with Xero status
        available_clients: list[AvailableClient] = [
            AvailableClient(
                id=str(client.id),
                name=client.name,
                email=client.email,
                abn=client.abn,
                status="active" if client.is_active else "inactive",
                already_imported=False,  # TODO: Check Clairo client table
                xero_org_status=client.connection_status,
                xero_connection_id=client.xero_connection_id,
            )
            for client in xpm_clients.clients
        ]

        return {
            "clients": available_clients,
            "total": xpm_clients.total,
            "source_type": "xpm",
            "tier_limit": tier_limit,
            "current_count": current_count,
            "page": xpm_clients.page,
            "page_size": xpm_clients.page_size,
        }

    async def start_bulk_import(
        self, tenant_id: UUID, client_ids: list[str], source_type: str = "xpm"
    ) -> BulkImportJob:
        """Start bulk client import job.

        Creates BulkImportJob record and queues Celery task.
        """
        job = BulkImportJob(
            tenant_id=tenant_id,
            source_type=source_type,
            client_ids=client_ids,
            total_clients=len(client_ids),
            status=BulkImportJobStatus.PENDING,
        )

        job = await self.import_job_repo.create(job)

        # TODO: Queue Celery task
        # bulk_import_clients.delay(str(job.id), client_ids)

        logger.info(
            "Bulk import started",
            tenant_id=str(tenant_id),
            job_id=str(job.id),
            client_count=len(client_ids),
        )

        return job

    async def get_import_job(self, tenant_id: UUID, job_id: UUID) -> BulkImportJob | None:
        """Get import job status with tenant filtering."""
        return await self.import_job_repo.get_by_id_and_tenant(job_id, tenant_id)

    async def retry_failed_imports(self, tenant_id: UUID, job_id: UUID) -> BulkImportJob | None:
        """Retry failed imports from a previous job.

        Creates a new job with only the failed client IDs.
        """
        original_job = await self.import_job_repo.get_by_id_and_tenant(job_id, tenant_id)
        if not original_job or not original_job.failed_clients:
            return None

        # Extract failed client IDs
        failed_ids = [client["xero_id"] for client in original_job.failed_clients]

        # Create new job
        return await self.start_bulk_import(tenant_id, failed_ids, original_job.source_type)

    # =========================================================================
    # Product Tour
    # =========================================================================

    async def complete_tour(self, tenant_id: UUID) -> OnboardingProgress:
        """Mark product tour as completed."""
        progress = await self.get_or_start_onboarding(tenant_id)

        update_data = {
            "tour_completed_at": datetime.now(UTC),
            "current_step": "complete",
        }

        # Check if all steps are complete
        if self._is_all_complete(progress):
            update_data["status"] = OnboardingStatus.COMPLETED
            update_data["completed_at"] = datetime.now(UTC)
        else:
            update_data["status"] = OnboardingStatus.TOUR_COMPLETED

        await self.onboarding_repo.update(progress.id, update_data)

        logger.info("Tour completed", tenant_id=str(tenant_id))

        progress = await self.onboarding_repo.get_by_tenant_id(tenant_id)
        return progress  # type: ignore

    async def skip_tour(self, tenant_id: UUID) -> OnboardingProgress:
        """Skip product tour."""
        progress = await self.get_or_start_onboarding(tenant_id)

        update_data = {
            "tour_skipped": True,
            "current_step": "complete",
        }

        # Check if all steps are complete (with tour skipped)
        if self._is_all_complete(progress, tour_skipped=True):
            update_data["status"] = OnboardingStatus.COMPLETED
            update_data["completed_at"] = datetime.now(UTC)

        await self.onboarding_repo.update(progress.id, update_data)

        logger.info("Tour skipped", tenant_id=str(tenant_id))

        progress = await self.onboarding_repo.get_by_tenant_id(tenant_id)
        return progress  # type: ignore

    def _is_all_complete(self, progress: OnboardingProgress, tour_skipped: bool = False) -> bool:
        """Check if all required onboarding steps are complete."""
        has_payment = progress.payment_setup_at is not None
        has_xero = progress.xero_connected_at is not None or progress.xero_skipped
        has_tour = progress.tour_completed_at is not None or tour_skipped

        return has_payment and has_xero and has_tour

    # =========================================================================
    # Progress Markers (called from other modules)
    # =========================================================================

    async def mark_xero_connected(self, tenant_id: UUID) -> None:
        """Mark Xero as connected in onboarding progress.

        Called from Xero OAuth callback. Idempotent — won't overwrite
        an existing timestamp.
        """
        progress = await self.onboarding_repo.get_by_tenant_id(tenant_id)
        if not progress or progress.xero_connected_at is not None:
            return

        update_data: dict[str, Any] = {
            "xero_connected_at": datetime.now(UTC),
        }
        if self._is_all_complete_with(progress, xero_connected=True):
            update_data["status"] = OnboardingStatus.COMPLETED
            update_data["completed_at"] = datetime.now(UTC)

        await self.onboarding_repo.update(progress.id, update_data)

    async def mark_clients_imported(self, tenant_id: UUID) -> None:
        """Mark first client as imported in onboarding progress.

        Called after sync completes with contacts. Idempotent — won't
        overwrite an existing timestamp.
        """
        progress = await self.onboarding_repo.get_by_tenant_id(tenant_id)
        if not progress or progress.clients_imported_at is not None:
            return

        update_data: dict[str, Any] = {
            "clients_imported_at": datetime.now(UTC),
        }
        if self._is_all_complete_with(progress, clients_imported=True):
            update_data["status"] = OnboardingStatus.COMPLETED
            update_data["completed_at"] = datetime.now(UTC)

        await self.onboarding_repo.update(progress.id, update_data)

    def _is_all_complete_with(
        self,
        progress: OnboardingProgress,
        xero_connected: bool = False,
        clients_imported: bool = False,
    ) -> bool:
        """Check if all steps would be complete given pending updates."""
        has_payment = progress.payment_setup_at is not None
        has_xero = progress.xero_connected_at is not None or progress.xero_skipped or xero_connected
        has_clients = progress.clients_imported_at is not None or clients_imported
        has_tour = progress.tour_completed_at is not None or progress.tour_skipped

        return has_payment and has_xero and has_clients and has_tour

    # =========================================================================
    # Checklist
    # =========================================================================

    async def get_checklist(self, tenant_id: UUID) -> OnboardingChecklist:
        """Build checklist from onboarding progress."""
        progress = await self.get_or_start_onboarding(tenant_id)

        items = [
            ChecklistItem(
                id="tier_selected",
                label="Select subscription tier",
                completed=progress.tier_selected_at is not None,
                completed_at=progress.tier_selected_at,
            ),
            ChecklistItem(
                id="payment_setup",
                label="Set up payment method",
                completed=progress.payment_setup_at is not None,
                completed_at=progress.payment_setup_at,
            ),
            ChecklistItem(
                id="xero_connected",
                label="Connect Xero",
                completed=progress.xero_connected_at is not None or progress.xero_skipped,
                completed_at=progress.xero_connected_at,
            ),
            ChecklistItem(
                id="clients_imported",
                label="Import your first client",
                completed=progress.clients_imported_at is not None,
                completed_at=progress.clients_imported_at,
            ),
            ChecklistItem(
                id="tour_completed",
                label="Complete product tour",
                completed=progress.tour_completed_at is not None or progress.tour_skipped,
                completed_at=progress.tour_completed_at,
            ),
        ]

        completed_count = sum(1 for item in items if item.completed)

        return OnboardingChecklist(
            items=items,
            completed_count=completed_count,
            total_count=len(items),
            dismissed=progress.checklist_dismissed,
        )

    async def dismiss_checklist(self, tenant_id: UUID) -> OnboardingProgress:
        """Dismiss onboarding checklist permanently."""
        progress = await self.get_or_start_onboarding(tenant_id)

        await self.onboarding_repo.update(
            progress.id,
            {"checklist_dismissed_at": datetime.now(UTC)},
        )

        logger.info("Checklist dismissed", tenant_id=str(tenant_id))

        progress = await self.onboarding_repo.get_by_tenant_id(tenant_id)
        return progress  # type: ignore

    # =========================================================================
    # Email Drip
    # =========================================================================

    async def send_welcome_email(self, tenant_id: UUID, email: str) -> bool:
        """Send welcome email and record in drip table."""
        # Check if already sent
        if await self.email_drip_repo.has_sent(tenant_id, "welcome"):
            return False

        # TODO: Send email via NotificationService

        # Record drip
        drip = EmailDrip(
            tenant_id=tenant_id,
            email_type="welcome",
            recipient_email=email,
        )
        await self.email_drip_repo.create(drip)

        logger.info("Welcome email sent", tenant_id=str(tenant_id), email=email)
        return True

    async def should_send_nudge(
        self, tenant_id: UUID, email_type: str, hours_since_start: int
    ) -> bool:
        """Check if nudge email should be sent.

        Args:
            tenant_id: Tenant ID
            email_type: Type of nudge email
            hours_since_start: Hours since onboarding started
        """
        # Check if already sent
        if await self.email_drip_repo.has_sent(tenant_id, email_type):
            return False

        progress = await self.get_progress(tenant_id)
        if not progress:
            return False

        # Calculate hours since start
        elapsed = datetime.now(UTC) - progress.started_at.replace(tzinfo=UTC)
        elapsed_hours = elapsed.total_seconds() / 3600

        return elapsed_hours >= hours_since_start
