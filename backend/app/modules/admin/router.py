"""FastAPI router for admin endpoints.

Provides platform-level administrative functionality:
- Aggregate usage statistics
- Upsell opportunity identification
- Tenant usage details
- Tenant management (list, detail, tier change, credits)
- Feature flag overrides
- Revenue analytics

All endpoints require admin role authentication.

Spec 020: Usage Tracking & Limits
Spec 022: Admin Dashboard (Internal)
"""

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db as get_db_session
from app.modules.auth.models import PracticeUser
from app.modules.auth.permissions import require_admin
from app.modules.billing.schemas import (
    AdminTenantUsageResponse,
    AdminUsageStats,
    SubscriptionTierType,
    UpsellOpportunitiesResponse,
)

from .exceptions import (
    CreditApplicationError,
    InvalidFeatureKeyError,
    SelfModificationBlockedError,
    TenantNotFoundError,
    TierDowngradeBlockedError,
)
from .schemas import (
    CreditRequest,
    CreditResponse,
    FeatureFlagOverrideRequest,
    FeatureFlagOverrideResponse,
    FeatureFlagsResponse,
    FeatureKeyType,
    PlatformUsageMetrics,
    RevenueMetricsResponse,
    RevenuePeriod,
    RevenueTrendsResponse,
    SortOrder,
    TenantDetailResponse,
    TenantListResponse,
    TenantSortField,
    TenantStatusFilter,
    TierChangeConflict,
    TierChangeRequest,
    TierChangeResponse,
    TopUsersResponse,
)
from .service import AdminDashboardService
from .usage_service import AdminUsageService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# =============================================================================
# Dependencies
# =============================================================================


async def get_admin_usage_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminUsageService:
    """Get AdminUsageService instance.

    Args:
        session: Database session.

    Returns:
        Configured AdminUsageService.
    """
    return AdminUsageService(session)


async def get_admin_dashboard_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminDashboardService:
    """Get AdminDashboardService instance.

    Args:
        session: Database session.

    Returns:
        Configured AdminDashboardService.
    """
    return AdminDashboardService(session)


# =============================================================================
# Usage Statistics Endpoints
# =============================================================================


@router.get(
    "/usage",
    response_model=PlatformUsageMetrics,
    summary="Get platform usage metrics",
    description="""
    Returns platform-wide usage metrics including:
    - Total clients across all tenants
    - Total syncs performed
    - Total AI queries
    - Metrics broken down by tier

    **Requires admin role.**
    """,
)
async def get_platform_usage(
    _: Annotated[PracticeUser, Depends(require_admin())],
    service: Annotated[AdminUsageService, Depends(get_admin_usage_service)],
) -> PlatformUsageMetrics:
    """Get aggregate platform usage metrics.

    Returns platform-level metrics for admin dashboard usage analytics.
    """
    return await service.get_platform_usage()


@router.get(
    "/usage/top",
    response_model=TopUsersResponse,
    summary="Get top tenants by metric",
    description="""
    Returns top tenants ranked by a specific metric.

    Supported metrics:
    - clients: Number of clients
    - syncs: Number of syncs performed
    - ai_queries: Number of AI queries

    **Requires admin role.**
    """,
)
async def get_top_users(
    _: Annotated[PracticeUser, Depends(require_admin())],
    service: Annotated[AdminUsageService, Depends(get_admin_usage_service)],
    metric: str = Query(default="clients", description="Metric to rank by"),
    limit: int = Query(default=10, ge=1, le=100, description="Maximum results"),
) -> TopUsersResponse:
    """Get top tenants by a specific metric.

    Returns list of top performing tenants for the specified metric.
    """
    return await service.get_top_users(metric=metric, limit=limit)


@router.get(
    "/usage/stats",
    response_model=AdminUsageStats,
    summary="Get aggregate usage statistics",
    description="""
    Returns platform-wide usage statistics including:
    - Total tenant and client counts
    - Average clients per tenant
    - Tenants at or approaching their limits
    - Tenant distribution by subscription tier

    **Requires admin role.**
    """,
)
async def get_usage_stats(
    _: Annotated[PracticeUser, Depends(require_admin())],
    service: Annotated[AdminUsageService, Depends(get_admin_usage_service)],
) -> AdminUsageStats:
    """Get aggregate usage statistics across all tenants.

    Returns platform-level metrics for admin dashboard.
    """
    return await service.get_aggregate_stats()


@router.get(
    "/usage/opportunities",
    response_model=UpsellOpportunitiesResponse,
    summary="Get upsell opportunities",
    description="""
    Returns tenants approaching their client limit who may benefit
    from upgrading to a higher tier.

    Results are sorted by percentage used (highest first).

    **Requires admin role.**
    """,
)
async def get_upsell_opportunities(
    _: Annotated[PracticeUser, Depends(require_admin())],
    service: Annotated[AdminUsageService, Depends(get_admin_usage_service)],
    threshold: int = Query(
        default=80,
        ge=1,
        le=100,
        description="Minimum usage percentage to include (default 80)",
    ),
    tier: SubscriptionTierType | None = Query(
        default=None,
        description="Filter by specific tier",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Maximum results to return",
    ),
) -> UpsellOpportunitiesResponse:
    """Get tenants approaching their client limit.

    These are potential upsell opportunities where tenants
    may benefit from upgrading their subscription tier.
    """
    opportunities, total = await service.get_upsell_opportunities(
        threshold=threshold,
        tier=tier,
        limit=limit,
    )
    return UpsellOpportunitiesResponse(
        opportunities=opportunities,
        total=total,
    )


@router.get(
    "/usage/tenant/{tenant_id}",
    response_model=AdminTenantUsageResponse,
    summary="Get tenant usage details",
    description="""
    Returns detailed usage information for a specific tenant including:
    - Current usage metrics
    - Usage history (snapshots)
    - Recent usage alerts

    **Requires admin role.**
    """,
)
async def get_tenant_usage_details(
    tenant_id: UUID,
    _: Annotated[PracticeUser, Depends(require_admin())],
    service: Annotated[AdminUsageService, Depends(get_admin_usage_service)],
) -> AdminTenantUsageResponse:
    """Get detailed usage information for a specific tenant.

    Returns full usage metrics, history, and alerts for admin review.
    """
    result = await service.get_tenant_usage_details(tenant_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return result


# =============================================================================
# Tenant Management Endpoints (Spec 022)
# =============================================================================


@router.get(
    "/tenants",
    response_model=TenantListResponse,
    summary="List all tenants",
    description="""
    Returns a paginated list of all tenants with filtering, sorting, and search.

    **Filters:**
    - search: Search by tenant name
    - tier: Filter by subscription tier
    - status: Filter by active/inactive/all

    **Sorting:**
    - sort_by: name, created_at, mrr, client_count
    - sort_order: asc, desc

    **Requires admin role.**
    """,
)
async def list_tenants(
    admin_user: Annotated[PracticeUser, Depends(require_admin())],
    service: Annotated[AdminDashboardService, Depends(get_admin_dashboard_service)],
    search: str | None = Query(default=None, description="Search by tenant name"),
    tier: SubscriptionTierType | None = Query(default=None, description="Filter by tier"),
    admin_status: TenantStatusFilter = Query(
        default="all", alias="status", description="Filter by status"
    ),
    sort_by: TenantSortField = Query(default="created_at", description="Sort field"),
    sort_order: SortOrder = Query(default="desc", description="Sort order"),
    page: int = Query(default=1, ge=1, description="Page number"),
    limit: int = Query(default=20, ge=1, le=100, description="Page size"),
) -> TenantListResponse:
    """List all tenants with filtering and pagination."""
    logger.info(
        "listing_tenants",
        admin_id=str(admin_user.id),
        search=search,
        tier=tier,
        status=admin_status,
    )

    return await service.list_tenants(
        search=search,
        tier=tier,
        status=admin_status,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        limit=limit,
    )


@router.get(
    "/tenants/{tenant_id}",
    response_model=TenantDetailResponse,
    summary="Get tenant details",
    description="""
    Returns detailed information about a specific tenant including:
    - Billing information
    - Usage metrics
    - Subscription history
    - Feature flags

    **Requires admin role.**
    """,
)
async def get_tenant_detail(
    tenant_id: UUID,
    admin_user: Annotated[PracticeUser, Depends(require_admin())],
    service: Annotated[AdminDashboardService, Depends(get_admin_dashboard_service)],
) -> TenantDetailResponse:
    """Get detailed tenant information."""
    logger.info(
        "getting_tenant_detail",
        admin_id=str(admin_user.id),
        tenant_id=str(tenant_id),
    )

    try:
        return await service.get_tenant_detail(tenant_id)
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )


@router.put(
    "/tenants/{tenant_id}/tier",
    response_model=TierChangeResponse,
    responses={
        409: {"model": TierChangeConflict, "description": "Tier change blocked"},
    },
    summary="Change tenant tier",
    description="""
    Change a tenant's subscription tier.

    If downgrading, will check client limits unless force_downgrade is true.

    **Requires admin role.**
    """,
)
async def change_tenant_tier(
    tenant_id: UUID,
    request: TierChangeRequest,
    admin_user: Annotated[PracticeUser, Depends(require_admin())],
    service: Annotated[AdminDashboardService, Depends(get_admin_dashboard_service)],
) -> TierChangeResponse:
    """Change a tenant's subscription tier."""
    logger.info(
        "changing_tenant_tier",
        admin_id=str(admin_user.id),
        tenant_id=str(tenant_id),
        new_tier=request.new_tier,
    )

    try:
        return await service.change_tenant_tier(
            tenant_id=tenant_id,
            new_tier=request.new_tier,
            reason=request.reason,
            admin_user=admin_user,
            force_downgrade=request.force_downgrade,
        )
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    except SelfModificationBlockedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify your own tenant",
        )
    except TierDowngradeBlockedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": str(e),
                "code": "excess_clients",
                "details": {
                    "current_clients": e.current_clients,
                    "new_limit": e.new_limit,
                },
            },
        )


@router.post(
    "/tenants/{tenant_id}/credit",
    response_model=CreditResponse,
    summary="Apply credit to tenant",
    description="""
    Apply a credit to a tenant's account.

    **Requires admin role.**
    """,
)
async def apply_credit(
    tenant_id: UUID,
    request: CreditRequest,
    admin_user: Annotated[PracticeUser, Depends(require_admin())],
    service: Annotated[AdminDashboardService, Depends(get_admin_dashboard_service)],
) -> CreditResponse:
    """Apply a credit to a tenant's account."""
    logger.info(
        "applying_credit",
        admin_id=str(admin_user.id),
        tenant_id=str(tenant_id),
        amount_cents=request.amount_cents,
    )

    try:
        return await service.apply_credit(
            tenant_id=tenant_id,
            amount_cents=request.amount_cents,
            credit_type=request.credit_type,
            reason=request.reason,
            admin_user=admin_user,
        )
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    except SelfModificationBlockedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify your own tenant",
        )
    except CreditApplicationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =============================================================================
# Feature Flag Endpoints (Spec 022)
# =============================================================================


@router.get(
    "/tenants/{tenant_id}/features",
    response_model=FeatureFlagsResponse,
    summary="Get tenant feature flags",
    description="""
    Returns all feature flags for a tenant, including tier defaults and overrides.

    **Requires admin role.**
    """,
)
async def get_tenant_feature_flags(
    tenant_id: UUID,
    admin_user: Annotated[PracticeUser, Depends(require_admin())],
    service: Annotated[AdminDashboardService, Depends(get_admin_dashboard_service)],
) -> FeatureFlagsResponse:
    """Get all feature flags for a tenant."""
    try:
        return await service.get_tenant_feature_flags(tenant_id)
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )


@router.put(
    "/tenants/{tenant_id}/features/{feature_key}",
    response_model=FeatureFlagOverrideResponse,
    summary="Set feature flag override",
    description="""
    Set or update a feature flag override for a tenant.

    **Requires admin role.**
    """,
)
async def set_feature_flag_override(
    tenant_id: UUID,
    feature_key: FeatureKeyType,
    request: FeatureFlagOverrideRequest,
    admin_user: Annotated[PracticeUser, Depends(require_admin())],
    service: Annotated[AdminDashboardService, Depends(get_admin_dashboard_service)],
) -> FeatureFlagOverrideResponse:
    """Set a feature flag override for a tenant."""
    logger.info(
        "setting_feature_flag_override",
        admin_id=str(admin_user.id),
        tenant_id=str(tenant_id),
        feature_key=feature_key,
        value=request.value,
    )

    try:
        return await service.set_feature_flag_override(
            tenant_id=tenant_id,
            feature_key=feature_key,
            value=request.value,
            reason=request.reason,
            admin_user=admin_user,
        )
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    except SelfModificationBlockedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify your own tenant",
        )
    except InvalidFeatureKeyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/tenants/{tenant_id}/features/{feature_key}",
    response_model=FeatureFlagOverrideResponse,
    summary="Delete feature flag override",
    description="""
    Delete a feature flag override (revert to tier default).

    **Requires admin role.**
    """,
)
async def delete_feature_flag_override(
    tenant_id: UUID,
    feature_key: FeatureKeyType,
    admin_user: Annotated[PracticeUser, Depends(require_admin())],
    service: Annotated[AdminDashboardService, Depends(get_admin_dashboard_service)],
) -> FeatureFlagOverrideResponse:
    """Delete a feature flag override (revert to tier default)."""
    logger.info(
        "deleting_feature_flag_override",
        admin_id=str(admin_user.id),
        tenant_id=str(tenant_id),
        feature_key=feature_key,
    )

    try:
        return await service.delete_feature_flag_override(
            tenant_id=tenant_id,
            feature_key=feature_key,
            admin_user=admin_user,
        )
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    except SelfModificationBlockedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify your own tenant",
        )


# =============================================================================
# Revenue Analytics Endpoints (Spec 022)
# =============================================================================


@router.get(
    "/revenue/metrics",
    response_model=RevenueMetricsResponse,
    summary="Get revenue metrics",
    description="""
    Returns aggregate revenue metrics including MRR, churn, and expansion.

    **Requires admin role.**
    """,
)
async def get_revenue_metrics(
    admin_user: Annotated[PracticeUser, Depends(require_admin())],
    service: Annotated[AdminDashboardService, Depends(get_admin_dashboard_service)],
    period_days: int = Query(default=30, ge=7, le=365, description="Period in days"),
) -> RevenueMetricsResponse:
    """Get aggregate revenue metrics."""
    return await service.get_revenue_metrics(period_days=period_days)


@router.get(
    "/revenue/trends",
    response_model=RevenueTrendsResponse,
    summary="Get revenue trends",
    description="""
    Returns revenue trends over time for charting.

    **Requires admin role.**
    """,
)
async def get_revenue_trends(
    admin_user: Annotated[PracticeUser, Depends(require_admin())],
    service: Annotated[AdminDashboardService, Depends(get_admin_dashboard_service)],
    period: RevenuePeriod = Query(default="daily", description="Aggregation period"),
    lookback_days: int = Query(default=30, ge=7, le=365, description="Days to look back"),
) -> RevenueTrendsResponse:
    """Get revenue trends over time."""
    return await service.get_revenue_trends(period=period, lookback_days=lookback_days)


# =============================================================================
# Audit Log Endpoints (Spec 052)
# =============================================================================


@router.get(
    "/audit",
    summary="List audit events",
    description="Paginated, filterable audit log for the current tenant.",
)
async def list_audit_events(
    admin_user: Annotated[PracticeUser, Depends(require_admin())],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=100),
    event_type: str | None = Query(default=None),
    event_category: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
) -> dict:
    """List audit events for the admin's tenant."""
    from sqlalchemy import func, select

    from app.core.audit import AuditLog
    from app.modules.admin.schemas import AuditLogItem, AuditLogListResponse

    tenant_id = admin_user.tenant_id

    query = select(AuditLog).where(AuditLog.tenant_id == tenant_id)

    if event_type:
        query = query.where(AuditLog.event_type.startswith(event_type))
    if event_category:
        query = query.where(AuditLog.event_category == event_category)
    if date_from:
        from datetime import datetime as dt

        query = query.where(AuditLog.occurred_at >= dt.fromisoformat(date_from))
    if date_to:
        from datetime import datetime as dt

        query = query.where(AuditLog.occurred_at <= dt.fromisoformat(date_to))

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    # Paginate
    query = query.order_by(AuditLog.occurred_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await session.execute(query)
    rows = result.scalars().all()

    items = [
        AuditLogItem(
            id=r.id,
            occurred_at=r.occurred_at,
            event_type=r.event_type,
            event_category=r.event_category,
            actor_email=r.actor_email,
            resource_type=r.resource_type,
            resource_id=r.resource_id,
            action=r.action,
            outcome=r.outcome,
            metadata=r.metadata,
        )
        for r in rows
    ]

    pages = (total + per_page - 1) // per_page
    return AuditLogListResponse(
        items=items, total=total, page=page, per_page=per_page, pages=pages
    ).model_dump()


@router.get(
    "/audit/summary",
    summary="Audit log summary",
    description="Aggregated statistics for the audit log.",
)
async def get_audit_summary(
    admin_user: Annotated[PracticeUser, Depends(require_admin())],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Get summary stats for the tenant's audit log."""
    from sqlalchemy import func, select

    from app.core.audit import AuditLog
    from app.modules.admin.schemas import AuditSummaryResponse

    tenant_id = admin_user.tenant_id

    # Total
    total = (
        await session.execute(
            select(func.count()).where(AuditLog.tenant_id == tenant_id)
        )
    ).scalar() or 0

    # By category
    cat_rows = (
        await session.execute(
            select(AuditLog.event_category, func.count())
            .where(AuditLog.tenant_id == tenant_id)
            .group_by(AuditLog.event_category)
        )
    ).all()
    by_category = {row[0]: row[1] for row in cat_rows}

    # By event type (top 20)
    type_rows = (
        await session.execute(
            select(AuditLog.event_type, func.count())
            .where(AuditLog.tenant_id == tenant_id)
            .group_by(AuditLog.event_type)
            .order_by(func.count().desc())
            .limit(20)
        )
    ).all()
    by_event_type = {row[0]: row[1] for row in type_rows}

    # AI suggestion stats
    ai_approved = (
        await session.execute(
            select(func.count()).where(
                AuditLog.tenant_id == tenant_id,
                AuditLog.event_type == "ai.suggestion.approved",
            )
        )
    ).scalar() or 0
    ai_modified = (
        await session.execute(
            select(func.count()).where(
                AuditLog.tenant_id == tenant_id,
                AuditLog.event_type == "ai.suggestion.modified",
            )
        )
    ).scalar() or 0
    ai_rejected = (
        await session.execute(
            select(func.count()).where(
                AuditLog.tenant_id == tenant_id,
                AuditLog.event_type == "ai.suggestion.rejected",
            )
        )
    ).scalar() or 0

    return AuditSummaryResponse(
        total_events=total,
        by_category=by_category,
        by_event_type=by_event_type,
        ai_suggestions={
            "approved": ai_approved,
            "modified": ai_modified,
            "rejected": ai_rejected,
            "total": ai_approved + ai_modified + ai_rejected,
        },
    ).model_dump()


@router.get(
    "/audit/export",
    summary="Export audit log as CSV",
    description="Stream audit events as CSV download.",
)
async def export_audit_csv(
    admin_user: Annotated[PracticeUser, Depends(require_admin())],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    event_type: str | None = Query(default=None),
    event_category: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    max_rows: int = Query(default=50000, ge=1, le=50000),
) -> StreamingResponse:
    """Export audit log as CSV."""
    import csv
    import io

    from sqlalchemy import select

    from app.core.audit import AuditLog

    tenant_id = admin_user.tenant_id
    query = select(AuditLog).where(AuditLog.tenant_id == tenant_id)

    if event_type:
        query = query.where(AuditLog.event_type.startswith(event_type))
    if event_category:
        query = query.where(AuditLog.event_category == event_category)
    if date_from:
        from datetime import datetime as dt

        query = query.where(AuditLog.occurred_at >= dt.fromisoformat(date_from))
    if date_to:
        from datetime import datetime as dt

        query = query.where(AuditLog.occurred_at <= dt.fromisoformat(date_to))

    query = query.order_by(AuditLog.occurred_at.desc()).limit(max_rows)
    result = await session.execute(query)
    rows = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "occurred_at", "event_type", "event_category", "actor_email",
        "resource_type", "resource_id", "action", "outcome", "metadata",
    ])
    for r in rows:
        writer.writerow([
            r.occurred_at.isoformat() if r.occurred_at else "",
            r.event_type, r.event_category, r.actor_email or "",
            r.resource_type or "", str(r.resource_id) if r.resource_id else "",
            r.action, r.outcome, str(r.metadata) if r.metadata else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
    )
