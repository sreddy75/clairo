"""Repository pattern for onboarding data access.

Provides database operations for:
- OnboardingProgress
- BulkImportJob
- BulkImportOrganization
- EmailDrip
"""

from typing import Any
from uuid import UUID

from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.onboarding.models import (
    BulkImportJob,
    BulkImportJobStatus,
    BulkImportOrganization,
    EmailDrip,
    OnboardingProgress,
)


class OnboardingRepository:
    """Repository for OnboardingProgress data access."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_tenant_id(self, tenant_id: UUID) -> OnboardingProgress | None:
        """Get onboarding progress for a tenant."""
        result = await self.session.execute(
            select(OnboardingProgress).where(OnboardingProgress.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create(self, tenant_id: UUID) -> tuple[OnboardingProgress, bool]:
        """Get existing progress or create new one.

        Returns:
            Tuple of (progress, created) where created is True if new record.
        """
        progress = await self.get_by_tenant_id(tenant_id)
        if progress:
            return progress, False

        progress = OnboardingProgress(tenant_id=tenant_id)
        self.session.add(progress)
        await self.session.flush()
        await self.session.refresh(progress)
        return progress, True

    async def create(self, progress: OnboardingProgress) -> OnboardingProgress:
        """Create a new onboarding progress record."""
        self.session.add(progress)
        await self.session.flush()
        await self.session.refresh(progress)
        return progress

    async def update(self, progress_id: UUID, data: dict[str, Any]) -> OnboardingProgress | None:
        """Update an existing onboarding progress record."""
        result = await self.session.execute(
            select(OnboardingProgress).where(OnboardingProgress.id == progress_id)
        )
        progress = result.scalar_one_or_none()
        if not progress:
            return None

        for key, value in data.items():
            if hasattr(progress, key) and value is not None:
                setattr(progress, key, value)

        await self.session.flush()
        await self.session.refresh(progress)
        return progress

    async def list_incomplete(self) -> list[OnboardingProgress]:
        """Get all incomplete onboarding records for drip email processing."""
        from app.modules.onboarding.models import OnboardingStatus

        result = await self.session.execute(
            select(OnboardingProgress).where(
                OnboardingProgress.status != OnboardingStatus.COMPLETED
            )
        )
        return list(result.scalars().all())


class BulkImportJobRepository:
    """Repository for BulkImportJob data access."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_id(self, job_id: UUID) -> BulkImportJob | None:
        """Get bulk import job by ID."""
        result = await self.session.execute(select(BulkImportJob).where(BulkImportJob.id == job_id))
        return result.scalar_one_or_none()

    async def get_by_id_and_tenant(self, job_id: UUID, tenant_id: UUID) -> BulkImportJob | None:
        """Get bulk import job by ID with tenant filtering."""
        result = await self.session.execute(
            select(BulkImportJob).where(
                BulkImportJob.id == job_id,
                BulkImportJob.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, job: BulkImportJob) -> BulkImportJob:
        """Create a new bulk import job."""
        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def update(self, job_id: UUID, data: dict[str, Any]) -> BulkImportJob | None:
        """Update an existing bulk import job."""
        job = await self.get_by_id(job_id)
        if not job:
            return None

        for key, value in data.items():
            if hasattr(job, key) and value is not None:
                setattr(job, key, value)

        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        status: BulkImportJobStatus | None = None,
        skip: int = 0,
        limit: int = 10,
    ) -> list[BulkImportJob]:
        """List bulk import jobs for a tenant."""
        query = (
            select(BulkImportJob)
            .where(BulkImportJob.tenant_id == tenant_id)
            .order_by(BulkImportJob.created_at.desc())
        )

        if status:
            query = query.where(BulkImportJob.status == status)

        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())


class BulkImportOrganizationRepository:
    """Repository for BulkImportOrganization data access."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def create(self, org: BulkImportOrganization) -> BulkImportOrganization:
        """Create a new bulk import organization record."""
        self.session.add(org)
        await self.session.flush()
        await self.session.refresh(org)
        return org

    async def bulk_create(self, items: list[dict[str, Any]]) -> list[BulkImportOrganization]:
        """Create multiple bulk import organization records."""
        orgs = [BulkImportOrganization(**item) for item in items]
        self.session.add_all(orgs)
        await self.session.flush()
        for org in orgs:
            await self.session.refresh(org)
        return orgs

    async def get_by_id(self, org_id: UUID) -> BulkImportOrganization | None:
        """Get bulk import organization by ID."""
        result = await self.session.execute(
            select(BulkImportOrganization).where(BulkImportOrganization.id == org_id)
        )
        return result.scalar_one_or_none()

    async def get_by_job_id(
        self, job_id: UUID, tenant_id: UUID | None = None
    ) -> list[BulkImportOrganization]:
        """Get all organizations for a bulk import job."""
        query = select(BulkImportOrganization).where(
            BulkImportOrganization.bulk_import_job_id == job_id
        )
        if tenant_id is not None:
            query = query.where(BulkImportOrganization.tenant_id == tenant_id)
        query = query.order_by(BulkImportOrganization.organization_name)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_failed_by_job_id(
        self, job_id: UUID, tenant_id: UUID | None = None
    ) -> list[BulkImportOrganization]:
        """Get failed organizations for a bulk import job."""
        query = select(BulkImportOrganization).where(
            BulkImportOrganization.bulk_import_job_id == job_id,
            BulkImportOrganization.status == "failed",
        )
        if tenant_id is not None:
            query = query.where(BulkImportOrganization.tenant_id == tenant_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_status(
        self, org_id: UUID, status: str, **kwargs: Any
    ) -> BulkImportOrganization | None:
        """Update the status of a bulk import organization."""
        result = await self.session.execute(
            select(BulkImportOrganization).where(BulkImportOrganization.id == org_id)
        )
        org = result.scalar_one_or_none()
        if not org:
            return None

        org.status = status
        for key, value in kwargs.items():
            if hasattr(org, key):
                setattr(org, key, value)

        await self.session.flush()
        await self.session.refresh(org)
        return org

    async def count_by_job_id(self, job_id: UUID) -> dict[str, int]:
        """Get status counts for a bulk import job."""
        result = await self.session.execute(
            select(
                BulkImportOrganization.status,
                sa_func.count(BulkImportOrganization.id),
            )
            .where(BulkImportOrganization.bulk_import_job_id == job_id)
            .group_by(BulkImportOrganization.status)
        )
        return dict(result.all())


class EmailDripRepository:
    """Repository for EmailDrip data access."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def create(self, drip: EmailDrip) -> EmailDrip:
        """Create a new email drip record."""
        self.session.add(drip)
        await self.session.flush()
        await self.session.refresh(drip)
        return drip

    async def get_by_tenant_and_type(self, tenant_id: UUID, email_type: str) -> EmailDrip | None:
        """Get email drip by tenant and type."""
        result = await self.session.execute(
            select(EmailDrip).where(
                EmailDrip.tenant_id == tenant_id,
                EmailDrip.email_type == email_type,
            )
        )
        return result.scalar_one_or_none()

    async def has_sent(self, tenant_id: UUID, email_type: str) -> bool:
        """Check if email type has been sent to tenant."""
        drip = await self.get_by_tenant_and_type(tenant_id, email_type)
        return drip is not None

    async def list_by_tenant(self, tenant_id: UUID) -> list[EmailDrip]:
        """List all email drips for a tenant."""
        result = await self.session.execute(
            select(EmailDrip)
            .where(EmailDrip.tenant_id == tenant_id)
            .order_by(EmailDrip.sent_at.desc())
        )
        return list(result.scalars().all())
