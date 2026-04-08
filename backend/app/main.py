"""FastAPI application entry point for Clairo.

This module creates and configures the main FastAPI application with:
- Lifespan management for startup/shutdown
- CORS middleware
- Exception handlers for domain errors
- Health check endpoint
- Conditional API documentation
- Sentry error tracking (when configured)

Usage:
    # Development with hot reload
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

    # Production
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
"""

import contextlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.core.exceptions import DomainError
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


def init_sentry() -> None:
    """Initialize Sentry error tracking if configured.

    Sentry provides real-time error tracking, performance monitoring,
    and distributed tracing. Only initializes if SENTRY_DSN is set.
    """
    settings = get_settings()

    if not settings.sentry.is_configured:
        logger.info("Sentry not configured, skipping initialization")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.redis import RedisIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=settings.sentry.dsn,
            environment=settings.sentry.environment,
            traces_sample_rate=settings.sentry.traces_sample_rate,
            profiles_sample_rate=settings.sentry.profiles_sample_rate,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                RedisIntegration(),
                CeleryIntegration(),
            ],
            # Send user info for debugging (respects privacy settings)
            send_default_pii=False,
            # Set release version
            release=f"clairo@{settings.app_version}",
        )

        logger.info(
            "Sentry initialized",
            environment=settings.sentry.environment,
            traces_sample_rate=settings.sentry.traces_sample_rate,
        )
    except ImportError:
        logger.warning("sentry-sdk not installed, skipping Sentry initialization")
    except Exception as e:
        logger.error("Failed to initialize Sentry", error=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager.

    Handles startup and shutdown events for the application.
    """
    # Startup
    settings = get_settings()
    setup_logging()

    # Initialize error tracking first (to catch startup errors)
    init_sentry()

    logger.info(
        "Application starting",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        debug=settings.debug,
    )

    # Initialize database connection
    try:
        from app.database import init_db

        await init_db()
        logger.info("Database connection established")
    except Exception as e:
        logger.warning("Database initialization skipped", error=str(e))

    yield

    # Shutdown
    logger.info("Application shutting down")

    try:
        from app.database import close_db

        await close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.warning("Database cleanup error", error=str(e))


def create_application() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    # Create app with conditional documentation
    app = FastAPI(
        title=settings.app_name,
        description="AI-Powered Tax & Advisory Platform for Australian Accounting Practices",
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json",  # Always available for type generation
    )

    # Add authentication and tenant context middleware
    # Order matters: TenantMiddleware runs after JWTMiddleware
    # (added in reverse order due to ASGI middleware chain)
    try:
        from app.modules.auth.clerk import get_clerk_client
        from app.modules.auth.middleware import JWTMiddleware, TenantMiddleware

        clerk_client = get_clerk_client()

        # TenantMiddleware - sets tenant context for RLS
        app.add_middleware(TenantMiddleware)

        # JWTMiddleware - validates tokens and sets user context
        app.add_middleware(
            JWTMiddleware,
            clerk_client=clerk_client,
        )

        logger.info("Authentication middleware registered")
    except Exception as e:
        logger.warning("Auth middleware registration skipped", error=str(e))

    # Configure CORS - MUST be added AFTER auth middleware
    # so it runs FIRST (handles OPTIONS preflight before auth)
    cors_settings = settings.cors
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_settings.origins,
        allow_credentials=cors_settings.allow_credentials,
        allow_methods=cors_settings.allow_methods,
        allow_headers=cors_settings.allow_headers,
    )

    # Register exception handlers
    register_exception_handlers(app)

    # Register routes
    register_routes(app)

    return app


def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers."""

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        """Handle domain-specific errors with consistent JSON response."""
        logger.warning(
            "Domain error",
            error_code=exc.code,
            error_message=exc.message,
            path=str(request.url.path),
            method=request.method,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all handler to ensure unhandled exceptions return JSON, not plain text."""
        logger.error(
            "Unhandled exception",
            error=str(exc),
            error_type=type(exc).__name__,
            path=str(request.url.path),
            method=request.method,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred. Please try again.",
                }
            },
        )


def register_routes(app: FastAPI) -> None:
    """Register application routes."""
    settings = get_settings()

    @app.get("/", tags=["root"])
    async def root() -> dict[str, Any]:
        """Root endpoint with application info."""
        return {
            "app": settings.app_name,
            "version": settings.app_version,
            "status": "running",
            "docs": "/docs" if settings.debug else None,
        }

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, Any]:
        """Health check endpoint.

        Returns application health status for load balancers and monitoring.
        """
        return {
            "status": "healthy",
            "version": settings.app_version,
            "environment": settings.environment,
        }

    @app.get("/health/ready", tags=["health"])
    async def readiness() -> dict[str, Any]:
        """Readiness probe for Kubernetes/container orchestration.

        Checks if the application is ready to accept traffic.
        """
        checks: dict[str, str] = {}

        # Check database connectivity
        try:
            from sqlalchemy import text

            from app.database import get_db_context

            async with get_db_context() as db:
                await db.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as e:
            checks["database"] = f"error: {e}"

        # Check Redis connectivity
        try:
            import redis.asyncio as aioredis

            redis_client = aioredis.from_url(settings.redis.url)  # type: ignore[no-untyped-call]
            await redis_client.ping()
            await redis_client.close()
            checks["redis"] = "ok"
        except Exception as e:
            checks["redis"] = f"error: {e}"

        # Determine overall status
        all_ok = all(v == "ok" for v in checks.values())

        return {
            "status": "ready" if all_ok else "not_ready",
            "checks": checks,
        }

    @app.get("/api/v1/public/stats", tags=["public"])
    async def public_stats() -> dict[str, Any]:
        """Public platform stats for the landing page.

        Returns aggregate counts — no auth required, no tenant-scoped data.
        """
        try:
            from sqlalchemy import text

            from app.database import get_db_context

            async with get_db_context() as db:
                clients_result = await db.execute(
                    text("SELECT count(*) FROM xero_connections WHERE status = 'active'")
                )
                clients_managed = clients_result.scalar_one()

                tenants_result = await db.execute(text("SELECT count(*) FROM tenants"))
                practices = tenants_result.scalar_one()

                tax_plans_result = await db.execute(text("SELECT count(*) FROM tax_plans"))
                tax_plans = tax_plans_result.scalar_one()

                # Count BAS periods generated (any status)
                bas_result = await db.execute(text("SELECT count(*) FROM bas_periods"))
                bas_generated = bas_result.scalar_one()

                # Count AI scenarios modelled
                scenarios_result = await db.execute(text("SELECT count(*) FROM tax_scenarios"))
                scenarios = scenarios_result.scalar_one()

            return {
                "clients_managed": clients_managed,
                "practices": practices,
                "tax_plans": tax_plans,
                "bas_generated": bas_generated,
                "scenarios_modelled": scenarios,
            }
        except Exception:
            return {
                "clients_managed": 0,
                "practices": 0,
                "tax_plans": 0,
                "bas_generated": 0,
                "scenarios_modelled": 0,
            }

    # Pre-import notification models so SQLAlchemy can resolve relationships
    # when auth models are loaded (PracticeUser.notifications references Notification)
    with contextlib.suppress(ImportError):
        from app.modules.notifications.models import Notification  # noqa: F401

    # Pre-import admin models so SQLAlchemy can resolve FeatureFlagOverride relationship
    # when auth models are loaded (Tenant.feature_flag_overrides references FeatureFlagOverride)
    with contextlib.suppress(ImportError):
        from app.modules.admin.models import FeatureFlagOverride  # noqa: F401

    # Pre-import tax planning models for Alembic migration discovery
    with contextlib.suppress(ImportError):
        from app.modules.tax_planning.models import (  # noqa: F401
            TaxPlan,
            TaxPlanMessage,
            TaxRateConfig,
            TaxScenario,
        )

    # Include module routers
    try:
        from app.modules.auth.router import router as auth_router

        app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
        logger.info("Auth router registered at /api/v1/auth")
    except Exception as e:
        logger.warning("Auth router registration skipped", error=str(e))

    try:
        from app.modules.integrations.xero.router import router as xero_router

        app.include_router(xero_router, prefix="/api/v1", tags=["integrations"])
        logger.info("Xero router registered at /api/v1/integrations/xero")
    except Exception as e:
        logger.warning("Xero router registration skipped", error=str(e))

    try:
        from app.modules.dashboard.router import router as dashboard_router

        app.include_router(dashboard_router, prefix="/api/v1", tags=["dashboard"])
        logger.info("Dashboard router registered at /api/v1/dashboard")
    except Exception as e:
        logger.warning("Dashboard router registration skipped", error=str(e))

    try:
        from app.modules.clients.router import router as clients_router

        app.include_router(clients_router, prefix="/api/v1", tags=["clients"])
        logger.info("Clients router registered at /api/v1/clients")
    except Exception as e:
        logger.warning("Clients router registration skipped", error=str(e))

    try:
        from app.modules.quality.router import router as quality_router

        app.include_router(quality_router, prefix="/api/v1", tags=["quality"])
        logger.info("Quality router registered at /api/v1/clients/{id}/quality")
    except Exception as e:
        logger.warning("Quality router registration skipped", error=str(e))

    try:
        from app.modules.bas.router import router as bas_router, workboard_router

        app.include_router(bas_router, prefix="/api/v1", tags=["bas"])
        app.include_router(workboard_router, prefix="/api/v1", tags=["bas-workboard"])
        logger.info("BAS router registered at /api/v1/clients/{id}/bas")
        logger.info("BAS Workboard router registered at /api/v1/bas/workboard")
    except Exception as e:
        logger.warning("BAS router registration skipped", error=str(e))

    try:
        from app.modules.notifications.router import router as notifications_router

        app.include_router(notifications_router, prefix="/api/v1", tags=["notifications"])
        logger.info("Notifications router registered at /api/v1/notifications")
    except Exception as e:
        logger.warning("Notifications router registration skipped", error=str(e))

    try:
        from app.modules.knowledge.router import router as knowledge_router

        app.include_router(knowledge_router, tags=["knowledge-admin"])
        logger.info("Knowledge router registered at /api/v1/admin/knowledge")
    except Exception as e:
        logger.warning("Knowledge router registration skipped", error=str(e))

    try:
        from app.modules.knowledge.router import public_router as knowledge_public_router

        app.include_router(knowledge_public_router, tags=["knowledge"])
        logger.info("Knowledge public router registered at /api/v1/knowledge")
    except Exception as e:
        logger.warning("Knowledge public router registration skipped", error=str(e))

    try:
        from app.modules.knowledge.client_chat_router import router as client_chat_router

        app.include_router(client_chat_router, tags=["client-chat"])
        logger.info("Client chat router registered at /api/v1/knowledge/client-chat")
    except Exception as e:
        logger.warning("Client chat router registration skipped", error=str(e))

    try:
        from app.modules.agents.router import router as agents_router

        app.include_router(agents_router, tags=["agents"])
        logger.info("Agents router registered at /api/v1/agents")
    except Exception as e:
        logger.warning("Agents router registration skipped", error=str(e))

    try:
        from app.modules.insights.router import platform_router, router as insights_router

        app.include_router(insights_router, tags=["insights"])
        app.include_router(platform_router, tags=["platform"])
        logger.info("Insights router registered at /api/v1/insights")
        logger.info("Platform router registered at /api/v1/platform")
    except Exception as e:
        logger.warning("Insights router registration skipped", error=str(e))

    try:
        from app.modules.action_items.router import router as action_items_router

        app.include_router(action_items_router, tags=["action-items"])
        logger.info("Action Items router registered at /api/v1/action-items")
    except Exception as e:
        logger.warning("Action Items router registration skipped", error=str(e))

    try:
        from app.modules.feedback.router import router as feedback_router

        app.include_router(feedback_router, tags=["feedback"])
        logger.info("Feedback router registered at /api/v1/feedback")
    except Exception as e:
        logger.warning("Feedback router registration skipped", error=str(e))

    try:
        from app.modules.triggers.router import router as triggers_router

        app.include_router(triggers_router, tags=["triggers"])
        logger.info("Triggers router registered at /api/v1/triggers")
    except Exception as e:
        logger.warning("Triggers router registration skipped", error=str(e))

    try:
        from app.modules.billing.router import router as billing_router

        app.include_router(billing_router, prefix="/api/v1", tags=["billing"])
        logger.info("Billing router registered at /api/v1")
    except Exception as e:
        logger.warning("Billing router registration skipped", error=str(e))

    try:
        from app.modules.admin.router import router as admin_router

        app.include_router(admin_router, prefix="/api/v1", tags=["admin"])
        logger.info("Admin router registered at /api/v1/admin")
    except Exception as e:
        logger.warning("Admin router registration skipped", error=str(e))

    try:
        from app.modules.onboarding.router import router as onboarding_router

        app.include_router(onboarding_router, prefix="/api/v1", tags=["onboarding"])
        logger.info("Onboarding router registered at /api/v1/onboarding")
    except Exception as e:
        logger.warning("Onboarding router registration skipped", error=str(e))

    try:
        from app.modules.queries.router import router as queries_router

        app.include_router(queries_router, prefix="/api/v1", tags=["queries"])
        logger.info("Queries router registered at /api/v1/queries")
    except Exception as e:
        logger.warning("Queries router registration skipped", error=str(e))

    try:
        from app.modules.productivity.router import router as productivity_router

        app.include_router(productivity_router, prefix="/api/v1", tags=["productivity"])
        logger.info("Productivity router registered at /api/v1/productivity")
    except Exception as e:
        logger.warning("Productivity router registration skipped", error=str(e))

    # Tax Planning router (Spec 049 - AI Tax Planning & Advisory)
    try:
        from app.modules.tax_planning.router import router as tax_planning_router

        app.include_router(tax_planning_router, prefix="/api/v1", tags=["tax-planning"])
        logger.info("Tax Planning router registered at /api/v1/tax-plans")
    except Exception as e:
        logger.warning("Tax Planning router registration skipped", error=str(e))

    # Portal routers (Spec 030 - Client Portal Foundation + Document Requests)
    try:
        from app.modules.portal.auth.router import router as portal_auth_router
        from app.modules.portal.dashboard.router import router as portal_dashboard_router
        from app.modules.portal.documents.router import router as portal_documents_router
        from app.modules.portal.requests.client_router import (
            router as portal_client_requests_router,
        )
        from app.modules.portal.requests.router import (
            requests_router as portal_doc_requests_router,
            router as portal_requests_router,
        )
        from app.modules.portal.router import (
            client_router as portal_client_router,
            router as portal_router,
        )

        app.include_router(portal_router, prefix="/api/v1", tags=["portal"])
        app.include_router(portal_client_router, prefix="/api/v1", tags=["client-portal"])
        # Auth router is nested under client-portal for magic link authentication
        app.include_router(
            portal_auth_router, prefix="/api/v1/client-portal", tags=["client-portal-auth"]
        )
        # Dashboard router for client portal dashboard
        app.include_router(portal_dashboard_router, prefix="/api/v1", tags=["portal-dashboard"])
        # Requests router for document request templates
        app.include_router(portal_requests_router, prefix="/api/v1", tags=["portal-templates"])
        # Document requests router for document request CRUD operations
        app.include_router(portal_doc_requests_router, prefix="/api/v1", tags=["document-requests"])
        # Client-facing requests router (portal view)
        app.include_router(
            portal_client_requests_router, prefix="/api/v1", tags=["portal-requests"]
        )
        # Document upload router (portal view)
        app.include_router(portal_documents_router, prefix="/api/v1", tags=["portal-documents"])
        logger.info("Portal routers registered at /api/v1/portal and /api/v1/client-portal")
    except Exception as e:
        logger.warning("Portal router registration skipped", error=str(e))

    # Client classification router (Spec 047)
    try:
        from app.modules.portal.classification_router import router as classification_client_router

        app.include_router(
            classification_client_router, prefix="/api/v1", tags=["portal-classification"]
        )
        logger.info("Classification client router registered at /api/v1/client-portal/classify")
    except Exception as e:
        logger.warning("Classification client router registration skipped", error=str(e))

    # Push notification routers (Spec 032 - PWA & Mobile Document Capture)
    try:
        from app.modules.notifications.push.router import router as push_router

        app.include_router(push_router, prefix="/api/v1", tags=["portal-push"])
        logger.info("Push notification router registered at /api/v1/portal/push")
    except Exception as e:
        logger.warning("Push notification router registration skipped", error=str(e))


# Create the application instance
app = create_application()
