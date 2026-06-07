"""API router for the tax_strategies module (Spec 060).

Exposes two routers:
- `router`: admin endpoints under `/api/v1/admin/tax-strategies`. Gated on
  `super_admin` Clerk role (front end also enforces this; backend gate is
  defense-in-depth).
- `public_router`: hydration endpoints under `/api/v1/tax-strategies`.
  Strips the internal-only `source_ref` field per FR-008.

Contract: specs/060-tax-strategies-kb/contracts/admin-tax-strategies.openapi.yaml
Contract: specs/060-tax-strategies-kb/contracts/public-tax-strategies.openapi.yaml
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_clerk_user
from app.database import get_db
from app.modules.auth.clerk import ClerkTokenPayload
from app.modules.tax_strategies.exceptions import (
    InvalidStatusTransitionError,
    SeedValidationError,
    StrategyNotFoundError,
)
from app.modules.tax_strategies.models import TaxStrategy
from app.modules.tax_strategies.repository import TaxStrategyRepository
from app.modules.tax_strategies.schemas import (
    ALLOWED_CATEGORIES,
    AuthoringJobResponse,
    PipelineStatsResponse,
    PublicHydrationBatchResponse,
    PublicTaxStrategy,
    RejectPayload,
    SeedSummaryResponse,
    TaxStrategyDetail,
    TaxStrategyListItem,
    TaxStrategyListResponse,
    TaxStrategyListResponseMeta,
)
from app.modules.tax_strategies.service import TaxStrategyService, seed_from_csv

router = APIRouter(prefix="/api/v1/admin/tax-strategies", tags=["tax-strategies-admin"])
public_router = APIRouter(prefix="/api/v1/tax-strategies", tags=["tax-strategies"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


async def require_super_admin(
    user: Annotated[ClerkTokenPayload, Depends(get_clerk_user)],
) -> ClerkTokenPayload:
    """Gate admin endpoints on the `super_admin` Clerk role.

    Frontend also enforces this in the admin page guard; this is a backend
    check so direct API callers can't bypass the UI gate.

    Dev fallbacks: when Clerk's default session JWT template omits `role`,
    `email`, and/or `public_metadata`, the check falls back to
    comma-separated `DEV_SUPER_ADMIN_EMAILS` or `DEV_SUPER_ADMIN_SUBS` env
    vars (matching `sub` is the most reliable since Clerk's default JWT
    carries `sub` unconditionally). Both must stay empty in staging/prod —
    configure the Clerk JWT template there to include `role` (and
    optionally `email`) from `user.public_metadata`.
    """
    if user.role == "super_admin":
        return user

    import os
    import sys

    email_fallback = os.environ.get("DEV_SUPER_ADMIN_EMAILS", "")
    allowed_emails = {e.strip().lower() for e in email_fallback.split(",") if e.strip()}
    sub_fallback = os.environ.get("DEV_SUPER_ADMIN_SUBS", "")
    allowed_subs = {s.strip() for s in sub_fallback.split(",") if s.strip()}

    print(
        f"[require_super_admin] role={user.role!r} email={user.email!r} "
        f"sub={user.sub!r} allowed_emails={sorted(allowed_emails)} "
        f"allowed_subs={sorted(allowed_subs)}",
        file=sys.stderr,
        flush=True,
    )

    if user.email and user.email.lower() in allowed_emails:
        return user
    if user.sub and user.sub in allowed_subs:
        return user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="super_admin role required",
    )


DbSession = Annotated[AsyncSession, Depends(get_db)]
SuperAdmin = Annotated[ClerkTokenPayload, Depends(require_super_admin)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _display_name_from_clerk(user: ClerkTokenPayload) -> str:
    """Produce a human-readable name snapshot for the reviewer audit trail."""
    return user.email or user.sub


def _strategy_to_list_item(strategy: TaxStrategy) -> TaxStrategyListItem:
    return TaxStrategyListItem.model_validate(strategy)


def _map_status_transition_error(
    exc: InvalidStatusTransitionError,
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error": "invalid_status_transition",
            "code": "invalid_status_transition",
            "details": {
                "strategy_id": exc.strategy_id,
                "from_status": exc.from_status,
                "to_status": exc.to_status,
            },
        },
    )


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=TaxStrategyListResponse)
async def list_tax_strategies(
    _user: SuperAdmin,
    session: DbSession,
    status_filter: str | None = Query(default=None, alias="status"),
    category: str | None = Query(default=None),
    tenant_id: str | None = Query(default="platform"),
    q: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> TaxStrategyListResponse:
    """Paginated list with filters (status, category, tenant, text search)."""
    if category is not None and category not in ALLOWED_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown category {category!r}",
        )
    repo = TaxStrategyRepository(session)
    offset = (page - 1) * page_size
    rows, total = await repo.list_with_filters(
        status=status_filter,
        category=category,
        tenant_id=tenant_id,
        query=q,
        offset=offset,
        limit=page_size,
    )
    return TaxStrategyListResponse(
        data=[_strategy_to_list_item(r) for r in rows],
        meta=TaxStrategyListResponseMeta(page=page, page_size=page_size, total=total),
    )


@router.get("/pipeline-stats", response_model=PipelineStatsResponse)
async def get_pipeline_stats(
    _user: SuperAdmin,
    session: DbSession,
) -> PipelineStatsResponse:
    """Counts per lifecycle status for the kanban dashboard."""
    repo = TaxStrategyRepository(session)
    counts = await repo.count_by_status()
    return PipelineStatsResponse(counts=counts)


@router.get("/staleness")
async def get_staleness_report(
    _user: SuperAdmin,
    session: DbSession,
) -> dict:
    """Compare live `TaxStrategy` rows against committed `data/strategies/*.yaml`.

    Three drift types reported per strategy id:
      - content_drift: both YAML and DB row exist but content hashes differ
        (someone edited a YAML without running the sync).
      - missing_row: YAML file exists but no DB row for it (sync never ran).
      - version_ahead: YAML version is higher than DB's live row — explicit
        version bump still pending sync.
      - yaml_missing: DB row exists but no YAML — candidate orphan.

    Consumed by the admin Strategies tab to surface a drift banner.
    """
    from app.modules.tax_strategies.sync import compute_staleness_report

    entries = await compute_staleness_report(session)
    # Group by reason for easier rendering in the frontend.
    grouped: dict[str, list[str]] = {}
    for e in entries:
        grouped.setdefault(e.reason, []).append(e.strategy_id)
    return {
        "total": len(entries),
        "by_reason": grouped,
        "entries": [{"strategy_id": e.strategy_id, "reason": e.reason} for e in entries],
    }


@router.get("/{strategy_id}", response_model=TaxStrategyDetail)
async def get_tax_strategy_detail(
    strategy_id: str,
    _user: SuperAdmin,
    session: DbSession,
) -> TaxStrategyDetail:
    """Full detail including version history and authoring job log."""
    repo = TaxStrategyRepository(session)
    strategy = await repo.get_live_version(strategy_id)
    if strategy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tax strategy {strategy_id!r} not found",
        )

    versions = await repo.list_versions(strategy_id)
    jobs = await repo.list_jobs_for_strategy(strategy_id)

    detail = TaxStrategyDetail.model_validate(strategy)
    detail.version_history = [_strategy_to_list_item(v) for v in versions]
    detail.authoring_jobs = [AuthoringJobResponse.model_validate(j) for j in jobs]
    return detail


# --- Stage triggers --------------------------------------------------------


async def _trigger_stage_endpoint(
    stage: str,
    strategy_id: str,
    user: ClerkTokenPayload,
    session: AsyncSession,
) -> AuthoringJobResponse:
    svc = TaxStrategyService(session)
    try:
        job = await svc.trigger_stage(
            strategy_id=strategy_id,
            stage=stage,
            actor_clerk_user_id=user.sub,
        )
    except StrategyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tax strategy {strategy_id!r} not found",
        ) from None
    except InvalidStatusTransitionError as exc:
        raise _map_status_transition_error(exc) from None
    await session.commit()
    return AuthoringJobResponse.model_validate(job)


@router.post(
    "/{strategy_id}/research",
    response_model=AuthoringJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_research(
    strategy_id: str,
    user: SuperAdmin,
    session: DbSession,
) -> AuthoringJobResponse:
    return await _trigger_stage_endpoint("research", strategy_id, user, session)


@router.post(
    "/{strategy_id}/draft",
    response_model=AuthoringJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_draft(
    strategy_id: str,
    user: SuperAdmin,
    session: DbSession,
) -> AuthoringJobResponse:
    return await _trigger_stage_endpoint("draft", strategy_id, user, session)


@router.post(
    "/{strategy_id}/enrich",
    response_model=AuthoringJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_enrich(
    strategy_id: str,
    user: SuperAdmin,
    session: DbSession,
) -> AuthoringJobResponse:
    return await _trigger_stage_endpoint("enrich", strategy_id, user, session)


# --- Transitions -----------------------------------------------------------


@router.post("/{strategy_id}/submit", response_model=TaxStrategyDetail)
async def submit_for_review(
    strategy_id: str,
    user: SuperAdmin,
    session: DbSession,
) -> TaxStrategyDetail:
    """Transition enriched → in_review."""
    svc = TaxStrategyService(session)
    try:
        strategy = await svc.submit_for_review(
            strategy_id=strategy_id,
            actor_clerk_user_id=user.sub,
            tenant_id=user.tenant_id,
        )
    except StrategyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tax strategy {strategy_id!r} not found",
        ) from None
    except InvalidStatusTransitionError as exc:
        raise _map_status_transition_error(exc) from None
    await session.commit()
    return TaxStrategyDetail.model_validate(strategy)


@router.post(
    "/{strategy_id}/approve",
    response_model=AuthoringJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def approve_and_publish(
    strategy_id: str,
    user: SuperAdmin,
    session: DbSession,
) -> AuthoringJobResponse:
    """Transition in_review → approved and queue publish. Captures reviewer
    identity from the Clerk JWT.
    """
    svc = TaxStrategyService(session)
    try:
        _strategy, job = await svc.approve(
            strategy_id=strategy_id,
            actor_clerk_user_id=user.sub,
            reviewer_display_name=_display_name_from_clerk(user),
            tenant_id=user.tenant_id,
        )
    except StrategyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tax strategy {strategy_id!r} not found",
        ) from None
    except InvalidStatusTransitionError as exc:
        raise _map_status_transition_error(exc) from None
    await session.commit()
    return AuthoringJobResponse.model_validate(job)


@router.post("/seed-from-csv", response_model=SeedSummaryResponse)
async def seed_from_csv_endpoint(
    user: SuperAdmin,
    session: DbSession,
) -> SeedSummaryResponse:
    """Idempotent bulk seed from the committed CSV fixture (FR-012).

    Creates stub TaxStrategy rows for any CLR-ID not already present.
    Re-running produces 0 creates and N skips. Invalid rows abort the run
    with 400 — no partial inserts.
    """
    try:
        summary = await seed_from_csv(
            session=session,
            triggered_by=user.sub,
            tenant_id=user.tenant_id,
        )
    except SeedValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "seed_validation_failed",
                "code": "seed_validation_failed",
                "details": {"errors": exc.errors},
            },
        ) from None
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from None
    await session.commit()
    return SeedSummaryResponse(
        created=summary.created,
        skipped=summary.skipped,
        errors=summary.errors,
    )


@router.post("/{strategy_id}/reject", response_model=TaxStrategyDetail)
async def reject_to_draft(
    strategy_id: str,
    payload: RejectPayload,
    user: SuperAdmin,
    session: DbSession,
) -> TaxStrategyDetail:
    """Transition in_review → drafted with reviewer notes."""
    svc = TaxStrategyService(session)
    try:
        strategy = await svc.reject(
            strategy_id=strategy_id,
            actor_clerk_user_id=user.sub,
            reviewer_notes=payload.reviewer_notes,
            tenant_id=user.tenant_id,
        )
    except StrategyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tax strategy {strategy_id!r} not found",
        ) from None
    except InvalidStatusTransitionError as exc:
        raise _map_status_transition_error(exc) from None
    await session.commit()
    return TaxStrategyDetail.model_validate(strategy)


# ---------------------------------------------------------------------------
# Public hydration endpoints — source_ref STRIPPED (FR-008)
# ---------------------------------------------------------------------------


def _to_public(strategy: TaxStrategy) -> PublicTaxStrategy:
    """Project a TaxStrategy to its public-safe view.

    NEVER includes source_ref. Only published, non-superseded strategies
    should reach this projection — the calling endpoint filters upstream.
    """
    return PublicTaxStrategy(
        strategy_id=strategy.strategy_id,
        name=strategy.name,
        categories=list(strategy.categories),
        implementation_text=strategy.implementation_text,
        explanation_text=strategy.explanation_text,
        ato_sources=list(strategy.ato_sources),
        case_refs=list(strategy.case_refs),
        fy_applicable_from=strategy.fy_applicable_from,
        fy_applicable_to=strategy.fy_applicable_to,
        version=strategy.version,
        is_platform=(strategy.tenant_id == "platform"),
    )


def _visible_to_caller(strategy: TaxStrategy) -> bool:
    """Enforce public-hydration visibility: only published, non-superseded."""
    return strategy.status == "published" and strategy.superseded_by_strategy_id is None


@public_router.get("/public", response_model=PublicHydrationBatchResponse)
async def hydrate_tax_strategies_batch(
    session: DbSession,
    ids: str = Query(..., description="Comma-separated CLR-XXX identifiers; max 20"),
) -> PublicHydrationBatchResponse:
    """Batch hydration for chat-message citation chips.

    Enforces FR-008: `source_ref` never returned.
    """
    raw_ids = [s.strip() for s in ids.split(",") if s.strip()]
    if not raw_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ids parameter is required",
        )
    if len(raw_ids) > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Max 20 ids per batch",
        )
    for rid in raw_ids:
        if not rid.startswith("CLR-") or not rid[4:].isdigit():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid strategy id {rid!r}",
            )

    repo = TaxStrategyRepository(session)
    rows = await repo.get_live_versions(raw_ids)
    visible = [r for r in rows if _visible_to_caller(r)]
    return PublicHydrationBatchResponse(data=[_to_public(r) for r in visible])


@public_router.get("/{strategy_id}/public", response_model=PublicTaxStrategy)
async def hydrate_tax_strategy(
    strategy_id: str,
    session: DbSession,
) -> PublicTaxStrategy:
    """Single-strategy hydration.

    Returns 404 when the strategy is missing, not published, or superseded —
    indistinguishable outcomes from the caller's perspective (no leak about
    draft / in-review state).
    """
    if not strategy_id.startswith("CLR-") or not strategy_id[4:].isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid strategy id",
        )
    repo = TaxStrategyRepository(session)
    strategy = await repo.get_live_version(strategy_id)
    if strategy is None or not _visible_to_caller(strategy):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not found",
        )
    return _to_public(strategy)
