"""Unit tests for OnboardingService.

Tests for:
- Onboarding progress management
- Tier selection
- Xero connection
- Bulk client import
- Product tour
- Checklist management
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.onboarding.models import (
    BulkImportJobStatus,
    OnboardingStatus,
)
from app.modules.onboarding.service import OnboardingService


class MockOnboardingProgress:
    """Mock OnboardingProgress for testing."""

    def __init__(
        self,
        status: OnboardingStatus = OnboardingStatus.STARTED,
        tier_selected_at: datetime | None = None,
        payment_setup_at: datetime | None = None,
        xero_connected_at: datetime | None = None,
        clients_imported_at: datetime | None = None,
        tour_completed_at: datetime | None = None,
        completed_at: datetime | None = None,
        xero_skipped: bool = False,
        tour_skipped: bool = False,
        checklist_dismissed: bool = False,
    ) -> None:
        self.id = uuid4()
        self.tenant_id = uuid4()
        self.status = status
        self.current_step = "start"
        self.started_at = datetime.now(UTC)
        self.tier_selected_at = tier_selected_at
        self.payment_setup_at = payment_setup_at
        self.xero_connected_at = xero_connected_at
        self.clients_imported_at = clients_imported_at
        self.tour_completed_at = tour_completed_at
        self.completed_at = completed_at
        self.xero_skipped = xero_skipped
        self.tour_skipped = tour_skipped
        self.checklist_dismissed = checklist_dismissed
        self.extra_data = {}


class MockTenant:
    """Mock Tenant for testing."""

    def __init__(
        self,
        tier: str = "starter",
        stripe_customer_id: str | None = None,
    ) -> None:
        self.id = uuid4()
        self.name = "Test Practice"
        self.slug = "test-practice"
        self.tier = MagicMock(value=tier)
        self.owner_email = "test@example.com"
        self.stripe_customer_id = stripe_customer_id
        self.stripe_subscription_id = None


class MockBulkImportJob:
    """Mock BulkImportJob for testing."""

    def __init__(
        self,
        status: BulkImportJobStatus = BulkImportJobStatus.PENDING,
        failed_clients: list | None = None,
    ) -> None:
        self.id = uuid4()
        self.tenant_id = uuid4()
        self.status = status
        self.source_type = "xpm"
        self.total_clients = 10
        self.imported_count = 0
        self.failed_count = 0
        self.progress_percent = 0.0
        self.started_at = datetime.now(UTC)
        self.completed_at = None
        self.client_ids = ["client1", "client2"]
        self.imported_clients = []
        self.failed_clients = failed_clients or []


# =============================================================================
# Progress Management Tests
# =============================================================================


class TestGetProgress:
    """Tests for get_progress method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_repositories(self, mock_session):
        """Create mock repositories."""
        with (
            patch("app.modules.onboarding.service.OnboardingRepository") as mock_onboarding_repo,
            patch("app.modules.onboarding.service.BulkImportJobRepository"),
            patch("app.modules.onboarding.service.EmailDripRepository"),
            patch("app.modules.onboarding.service.TenantRepository"),
            patch("app.modules.onboarding.service.BillingService"),
        ):
            mock_onboarding_repo.return_value.get_by_tenant_id = AsyncMock()
            yield mock_onboarding_repo.return_value

    @pytest.mark.asyncio
    async def test_get_progress_returns_none_when_not_found(self, mock_session, mock_repositories):
        """Should return None when no progress exists."""
        mock_repositories.get_by_tenant_id.return_value = None

        service = OnboardingService(mock_session)
        service.onboarding_repo = mock_repositories

        result = await service.get_progress(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_progress_returns_progress(self, mock_session, mock_repositories):
        """Should return progress when it exists."""
        progress = MockOnboardingProgress()
        mock_repositories.get_by_tenant_id.return_value = progress

        service = OnboardingService(mock_session)
        service.onboarding_repo = mock_repositories

        result = await service.get_progress(progress.tenant_id)

        assert result == progress


class TestStartOnboarding:
    """Tests for start_onboarding method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_start_onboarding_creates_progress(self, mock_session):
        """Should create new progress when starting onboarding."""
        tenant_id = uuid4()
        progress = MockOnboardingProgress()
        progress.tenant_id = tenant_id

        with (
            patch("app.modules.onboarding.service.OnboardingRepository") as mock_repo,
            patch("app.modules.onboarding.service.BulkImportJobRepository"),
            patch("app.modules.onboarding.service.EmailDripRepository"),
            patch("app.modules.onboarding.service.TenantRepository"),
            patch("app.modules.onboarding.service.BillingService"),
        ):
            mock_repo.return_value.get_or_create = AsyncMock(return_value=(progress, True))

            service = OnboardingService(mock_session)
            result = await service.start_onboarding(tenant_id)

            assert result.tenant_id == tenant_id

    @pytest.mark.asyncio
    async def test_start_onboarding_returns_existing(self, mock_session):
        """Should return existing progress when already started."""
        tenant_id = uuid4()
        progress = MockOnboardingProgress(status=OnboardingStatus.TIER_SELECTED)
        progress.tenant_id = tenant_id

        with (
            patch("app.modules.onboarding.service.OnboardingRepository") as mock_repo,
            patch("app.modules.onboarding.service.BulkImportJobRepository"),
            patch("app.modules.onboarding.service.EmailDripRepository"),
            patch("app.modules.onboarding.service.TenantRepository"),
            patch("app.modules.onboarding.service.BillingService"),
        ):
            mock_repo.return_value.get_or_create = AsyncMock(return_value=(progress, False))

            service = OnboardingService(mock_session)
            result = await service.start_onboarding(tenant_id)

            assert result.status == OnboardingStatus.TIER_SELECTED


# =============================================================================
# Tier Selection Tests
# =============================================================================


class TestSelectTier:
    """Tests for select_tier method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_select_tier_tenant_not_found_raises_error(self, mock_session):
        """Should raise ValueError when tenant not found."""
        tenant_id = uuid4()
        progress = MockOnboardingProgress()

        with (
            patch("app.modules.onboarding.service.OnboardingRepository") as mock_onboarding,
            patch("app.modules.onboarding.service.TenantRepository") as mock_tenant,
            patch("app.modules.onboarding.service.BulkImportJobRepository"),
            patch("app.modules.onboarding.service.EmailDripRepository"),
            patch("app.modules.onboarding.service.BillingService"),
        ):
            mock_onboarding.return_value.get_or_create = AsyncMock(return_value=(progress, False))
            mock_tenant.return_value.get_by_id = AsyncMock(return_value=None)

            service = OnboardingService(mock_session)

            with pytest.raises(ValueError) as exc_info:
                await service.select_tier(
                    tenant_id=tenant_id,
                    tier="professional",
                )

            assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_select_tier_creates_checkout_session(self, mock_session):
        """Should create Stripe checkout and update progress."""
        tenant_id = uuid4()
        progress = MockOnboardingProgress()
        tenant = MockTenant()

        with (
            patch("app.modules.onboarding.service.OnboardingRepository") as mock_onboarding,
            patch("app.modules.onboarding.service.TenantRepository") as mock_tenant,
            patch("app.modules.onboarding.service.BillingService") as mock_billing,
            patch("app.modules.onboarding.service.BulkImportJobRepository"),
            patch("app.modules.onboarding.service.EmailDripRepository"),
        ):
            mock_onboarding.return_value.get_or_create = AsyncMock(return_value=(progress, False))
            mock_onboarding.return_value.update = AsyncMock()
            mock_onboarding.return_value.get_by_tenant_id = AsyncMock(return_value=progress)
            mock_tenant.return_value.get_by_id = AsyncMock(return_value=tenant)
            mock_billing.return_value.start_trial = AsyncMock(return_value={"id": "sub_test123"})

            service = OnboardingService(mock_session)
            result_progress = await service.select_tier(
                tenant_id=tenant_id,
                tier="professional",
            )

            assert result_progress is not None
            mock_billing.return_value.start_trial.assert_called_once()


# =============================================================================
# Xero Connection Tests
# =============================================================================


class TestSkipXero:
    """Tests for skip_xero method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_skip_xero_updates_progress(self, mock_session):
        """Should update progress to mark Xero as skipped."""
        tenant_id = uuid4()
        progress = MockOnboardingProgress()

        with (
            patch("app.modules.onboarding.service.OnboardingRepository") as mock_repo,
            patch("app.modules.onboarding.service.BulkImportJobRepository"),
            patch("app.modules.onboarding.service.EmailDripRepository"),
            patch("app.modules.onboarding.service.TenantRepository"),
            patch("app.modules.onboarding.service.BillingService"),
        ):
            mock_repo.return_value.get_or_create = AsyncMock(return_value=(progress, False))
            mock_repo.return_value.update = AsyncMock()
            updated_progress = MockOnboardingProgress(
                status=OnboardingStatus.SKIPPED_XERO, xero_skipped=True
            )
            mock_repo.return_value.get_by_tenant_id = AsyncMock(return_value=updated_progress)

            service = OnboardingService(mock_session)
            result = await service.skip_xero(tenant_id)

            assert result.xero_skipped is True
            mock_repo.return_value.update.assert_called_once()


# =============================================================================
# Bulk Import Tests
# =============================================================================


class TestStartBulkImport:
    """Tests for start_bulk_import method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_start_bulk_import_creates_job(self, mock_session):
        """Should create a new import job."""
        tenant_id = uuid4()
        client_ids = ["client1", "client2", "client3"]

        with (
            patch("app.modules.onboarding.service.BulkImportJobRepository") as mock_repo,
            patch("app.modules.onboarding.service.OnboardingRepository"),
            patch("app.modules.onboarding.service.EmailDripRepository"),
            patch("app.modules.onboarding.service.TenantRepository"),
            patch("app.modules.onboarding.service.BillingService"),
        ):
            job = MockBulkImportJob()
            job.total_clients = len(client_ids)
            mock_repo.return_value.create = AsyncMock(return_value=job)

            service = OnboardingService(mock_session)
            result = await service.start_bulk_import(tenant_id, client_ids)

            assert result.total_clients == 3
            assert result.status == BulkImportJobStatus.PENDING


class TestGetImportJob:
    """Tests for get_import_job method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_get_import_job_returns_none_when_not_found(self, mock_session):
        """Should return None when job not found."""
        with (
            patch("app.modules.onboarding.service.BulkImportJobRepository") as mock_repo,
            patch("app.modules.onboarding.service.OnboardingRepository"),
            patch("app.modules.onboarding.service.EmailDripRepository"),
            patch("app.modules.onboarding.service.TenantRepository"),
            patch("app.modules.onboarding.service.BillingService"),
        ):
            mock_repo.return_value.get_by_id_and_tenant = AsyncMock(return_value=None)

            service = OnboardingService(mock_session)
            result = await service.get_import_job(uuid4(), uuid4())

            assert result is None

    @pytest.mark.asyncio
    async def test_get_import_job_returns_job(self, mock_session):
        """Should return job when found."""
        job = MockBulkImportJob()

        with (
            patch("app.modules.onboarding.service.BulkImportJobRepository") as mock_repo,
            patch("app.modules.onboarding.service.OnboardingRepository"),
            patch("app.modules.onboarding.service.EmailDripRepository"),
            patch("app.modules.onboarding.service.TenantRepository"),
            patch("app.modules.onboarding.service.BillingService"),
        ):
            mock_repo.return_value.get_by_id_and_tenant = AsyncMock(return_value=job)

            service = OnboardingService(mock_session)
            result = await service.get_import_job(job.tenant_id, job.id)

            assert result == job


class TestRetryFailedImports:
    """Tests for retry_failed_imports method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_retry_returns_none_when_no_failures(self, mock_session):
        """Should return None when no failed imports."""
        job = MockBulkImportJob(failed_clients=[])

        with (
            patch("app.modules.onboarding.service.BulkImportJobRepository") as mock_repo,
            patch("app.modules.onboarding.service.OnboardingRepository"),
            patch("app.modules.onboarding.service.EmailDripRepository"),
            patch("app.modules.onboarding.service.TenantRepository"),
            patch("app.modules.onboarding.service.BillingService"),
        ):
            mock_repo.return_value.get_by_id_and_tenant = AsyncMock(return_value=job)

            service = OnboardingService(mock_session)
            result = await service.retry_failed_imports(uuid4(), job.id)

            assert result is None

    @pytest.mark.asyncio
    async def test_retry_creates_new_job(self, mock_session):
        """Should create new job with failed client IDs."""
        failed_clients = [
            {"xero_id": "fail1", "error": "Connection error"},
            {"xero_id": "fail2", "error": "Timeout"},
        ]
        original_job = MockBulkImportJob(failed_clients=failed_clients)
        new_job = MockBulkImportJob()

        with (
            patch("app.modules.onboarding.service.BulkImportJobRepository") as mock_repo,
            patch("app.modules.onboarding.service.OnboardingRepository"),
            patch("app.modules.onboarding.service.EmailDripRepository"),
            patch("app.modules.onboarding.service.TenantRepository"),
            patch("app.modules.onboarding.service.BillingService"),
        ):
            mock_repo.return_value.get_by_id_and_tenant = AsyncMock(return_value=original_job)
            mock_repo.return_value.create = AsyncMock(return_value=new_job)

            service = OnboardingService(mock_session)
            result = await service.retry_failed_imports(uuid4(), original_job.id)

            assert result == new_job
            mock_repo.return_value.create.assert_called_once()


# =============================================================================
# Tour Tests
# =============================================================================


class TestCompleteTour:
    """Tests for complete_tour method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_complete_tour_updates_progress(self, mock_session):
        """Should mark tour as completed."""
        progress = MockOnboardingProgress(
            payment_setup_at=datetime.now(UTC),
            xero_connected_at=datetime.now(UTC),
        )

        with (
            patch("app.modules.onboarding.service.OnboardingRepository") as mock_repo,
            patch("app.modules.onboarding.service.BulkImportJobRepository"),
            patch("app.modules.onboarding.service.EmailDripRepository"),
            patch("app.modules.onboarding.service.TenantRepository"),
            patch("app.modules.onboarding.service.BillingService"),
        ):
            mock_repo.return_value.get_or_create = AsyncMock(return_value=(progress, False))
            mock_repo.return_value.update = AsyncMock()
            completed_progress = MockOnboardingProgress(
                status=OnboardingStatus.TOUR_COMPLETED,
                tour_completed_at=datetime.now(UTC),
            )
            mock_repo.return_value.get_by_tenant_id = AsyncMock(return_value=completed_progress)

            service = OnboardingService(mock_session)
            result = await service.complete_tour(uuid4())

            assert result.tour_completed_at is not None


class TestSkipTour:
    """Tests for skip_tour method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_skip_tour_sets_flag(self, mock_session):
        """Should set tour_skipped to True."""
        progress = MockOnboardingProgress()

        with (
            patch("app.modules.onboarding.service.OnboardingRepository") as mock_repo,
            patch("app.modules.onboarding.service.BulkImportJobRepository"),
            patch("app.modules.onboarding.service.EmailDripRepository"),
            patch("app.modules.onboarding.service.TenantRepository"),
            patch("app.modules.onboarding.service.BillingService"),
        ):
            mock_repo.return_value.get_or_create = AsyncMock(return_value=(progress, False))
            mock_repo.return_value.update = AsyncMock()
            skipped_progress = MockOnboardingProgress(tour_skipped=True)
            mock_repo.return_value.get_by_tenant_id = AsyncMock(return_value=skipped_progress)

            service = OnboardingService(mock_session)
            result = await service.skip_tour(uuid4())

            assert result.tour_skipped is True


# =============================================================================
# Checklist Tests
# =============================================================================


class TestGetChecklist:
    """Tests for get_checklist method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_get_checklist_all_incomplete(self, mock_session):
        """Should return checklist with 0 completed items."""
        progress = MockOnboardingProgress()

        with (
            patch("app.modules.onboarding.service.OnboardingRepository") as mock_repo,
            patch("app.modules.onboarding.service.BulkImportJobRepository"),
            patch("app.modules.onboarding.service.EmailDripRepository"),
            patch("app.modules.onboarding.service.TenantRepository"),
            patch("app.modules.onboarding.service.BillingService"),
        ):
            mock_repo.return_value.get_or_create = AsyncMock(return_value=(progress, False))

            service = OnboardingService(mock_session)
            result = await service.get_checklist(uuid4())

            assert result.completed_count == 0
            assert result.total_count == 5

    @pytest.mark.asyncio
    async def test_get_checklist_partially_complete(self, mock_session):
        """Should return checklist with partial completion."""
        progress = MockOnboardingProgress(
            tier_selected_at=datetime.now(UTC),
            payment_setup_at=datetime.now(UTC),
        )

        with (
            patch("app.modules.onboarding.service.OnboardingRepository") as mock_repo,
            patch("app.modules.onboarding.service.BulkImportJobRepository"),
            patch("app.modules.onboarding.service.EmailDripRepository"),
            patch("app.modules.onboarding.service.TenantRepository"),
            patch("app.modules.onboarding.service.BillingService"),
        ):
            mock_repo.return_value.get_or_create = AsyncMock(return_value=(progress, False))

            service = OnboardingService(mock_session)
            result = await service.get_checklist(uuid4())

            assert result.completed_count == 2
            assert result.total_count == 5

    @pytest.mark.asyncio
    async def test_get_checklist_all_complete(self, mock_session):
        """Should return checklist with all items completed."""
        progress = MockOnboardingProgress(
            tier_selected_at=datetime.now(UTC),
            payment_setup_at=datetime.now(UTC),
            xero_connected_at=datetime.now(UTC),
            clients_imported_at=datetime.now(UTC),
            tour_completed_at=datetime.now(UTC),
        )

        with (
            patch("app.modules.onboarding.service.OnboardingRepository") as mock_repo,
            patch("app.modules.onboarding.service.BulkImportJobRepository"),
            patch("app.modules.onboarding.service.EmailDripRepository"),
            patch("app.modules.onboarding.service.TenantRepository"),
            patch("app.modules.onboarding.service.BillingService"),
        ):
            mock_repo.return_value.get_or_create = AsyncMock(return_value=(progress, False))

            service = OnboardingService(mock_session)
            result = await service.get_checklist(uuid4())

            assert result.completed_count == 5
            assert result.total_count == 5

    @pytest.mark.asyncio
    async def test_get_checklist_skipped_counts_as_complete(self, mock_session):
        """Xero skipped and tour skipped should count as complete."""
        progress = MockOnboardingProgress(
            tier_selected_at=datetime.now(UTC),
            payment_setup_at=datetime.now(UTC),
            xero_skipped=True,
            tour_skipped=True,
        )

        with (
            patch("app.modules.onboarding.service.OnboardingRepository") as mock_repo,
            patch("app.modules.onboarding.service.BulkImportJobRepository"),
            patch("app.modules.onboarding.service.EmailDripRepository"),
            patch("app.modules.onboarding.service.TenantRepository"),
            patch("app.modules.onboarding.service.BillingService"),
        ):
            mock_repo.return_value.get_or_create = AsyncMock(return_value=(progress, False))

            service = OnboardingService(mock_session)
            result = await service.get_checklist(uuid4())

            # tier_selected, payment_setup, xero(skipped), tour(skipped) = 4
            assert result.completed_count == 4


class TestDismissChecklist:
    """Tests for dismiss_checklist method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_dismiss_checklist_sets_timestamp(self, mock_session):
        """Should set checklist_dismissed_at timestamp."""
        progress = MockOnboardingProgress()

        with (
            patch("app.modules.onboarding.service.OnboardingRepository") as mock_repo,
            patch("app.modules.onboarding.service.BulkImportJobRepository"),
            patch("app.modules.onboarding.service.EmailDripRepository"),
            patch("app.modules.onboarding.service.TenantRepository"),
            patch("app.modules.onboarding.service.BillingService"),
        ):
            mock_repo.return_value.get_or_create = AsyncMock(return_value=(progress, False))
            mock_repo.return_value.update = AsyncMock()
            dismissed_progress = MockOnboardingProgress(checklist_dismissed=True)
            mock_repo.return_value.get_by_tenant_id = AsyncMock(return_value=dismissed_progress)

            service = OnboardingService(mock_session)
            result = await service.dismiss_checklist(uuid4())

            assert result.checklist_dismissed is True


# =============================================================================
# Email Drip Tests
# =============================================================================


class TestSendWelcomeEmail:
    """Tests for send_welcome_email method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_send_welcome_email_records_drip(self, mock_session):
        """Should record email drip when sending."""
        tenant_id = uuid4()

        with (
            patch("app.modules.onboarding.service.EmailDripRepository") as mock_repo,
            patch("app.modules.onboarding.service.OnboardingRepository"),
            patch("app.modules.onboarding.service.BulkImportJobRepository"),
            patch("app.modules.onboarding.service.TenantRepository"),
            patch("app.modules.onboarding.service.BillingService"),
        ):
            mock_repo.return_value.has_sent = AsyncMock(return_value=False)
            mock_repo.return_value.create = AsyncMock()

            service = OnboardingService(mock_session)
            result = await service.send_welcome_email(tenant_id, "test@example.com")

            assert result is True
            mock_repo.return_value.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_welcome_email_skips_if_already_sent(self, mock_session):
        """Should return False if email already sent."""
        tenant_id = uuid4()

        with (
            patch("app.modules.onboarding.service.EmailDripRepository") as mock_repo,
            patch("app.modules.onboarding.service.OnboardingRepository"),
            patch("app.modules.onboarding.service.BulkImportJobRepository"),
            patch("app.modules.onboarding.service.TenantRepository"),
            patch("app.modules.onboarding.service.BillingService"),
        ):
            mock_repo.return_value.has_sent = AsyncMock(return_value=True)

            service = OnboardingService(mock_session)
            result = await service.send_welcome_email(tenant_id, "test@example.com")

            assert result is False


# =============================================================================
# Helper Method Tests
# =============================================================================


class TestIsAllComplete:
    """Tests for _is_all_complete helper method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    def test_not_complete_when_payment_missing(self, mock_session):
        """Should return False when payment not setup."""
        progress = MockOnboardingProgress(
            xero_connected_at=datetime.now(UTC),
            tour_completed_at=datetime.now(UTC),
        )

        with (
            patch("app.modules.onboarding.service.OnboardingRepository"),
            patch("app.modules.onboarding.service.BulkImportJobRepository"),
            patch("app.modules.onboarding.service.EmailDripRepository"),
            patch("app.modules.onboarding.service.TenantRepository"),
            patch("app.modules.onboarding.service.BillingService"),
        ):
            service = OnboardingService(mock_session)
            result = service._is_all_complete(progress)

            assert result is False

    def test_complete_with_all_steps(self, mock_session):
        """Should return True when all steps complete."""
        progress = MockOnboardingProgress(
            payment_setup_at=datetime.now(UTC),
            xero_connected_at=datetime.now(UTC),
            tour_completed_at=datetime.now(UTC),
        )

        with (
            patch("app.modules.onboarding.service.OnboardingRepository"),
            patch("app.modules.onboarding.service.BulkImportJobRepository"),
            patch("app.modules.onboarding.service.EmailDripRepository"),
            patch("app.modules.onboarding.service.TenantRepository"),
            patch("app.modules.onboarding.service.BillingService"),
        ):
            service = OnboardingService(mock_session)
            result = service._is_all_complete(progress)

            assert result is True

    def test_complete_with_xero_skipped(self, mock_session):
        """Should return True when Xero skipped."""
        progress = MockOnboardingProgress(
            payment_setup_at=datetime.now(UTC),
            xero_skipped=True,
            tour_completed_at=datetime.now(UTC),
        )

        with (
            patch("app.modules.onboarding.service.OnboardingRepository"),
            patch("app.modules.onboarding.service.BulkImportJobRepository"),
            patch("app.modules.onboarding.service.EmailDripRepository"),
            patch("app.modules.onboarding.service.TenantRepository"),
            patch("app.modules.onboarding.service.BillingService"),
        ):
            service = OnboardingService(mock_session)
            result = service._is_all_complete(progress)

            assert result is True

    def test_complete_with_tour_skipped_param(self, mock_session):
        """Should return True when tour_skipped param is True."""
        progress = MockOnboardingProgress(
            payment_setup_at=datetime.now(UTC),
            xero_connected_at=datetime.now(UTC),
        )

        with (
            patch("app.modules.onboarding.service.OnboardingRepository"),
            patch("app.modules.onboarding.service.BulkImportJobRepository"),
            patch("app.modules.onboarding.service.EmailDripRepository"),
            patch("app.modules.onboarding.service.TenantRepository"),
            patch("app.modules.onboarding.service.BillingService"),
        ):
            service = OnboardingService(mock_session)
            result = service._is_all_complete(progress, tour_skipped=True)

            assert result is True
