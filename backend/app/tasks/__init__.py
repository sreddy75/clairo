"""Celery background tasks for Clairo.

This package contains:
- celery_app.py: Celery application configuration
- Task modules for async operations (OCR, sync, notifications, etc.)

All tasks should be registered with autodiscover_tasks.
"""

# Import all models to ensure SQLAlchemy mappers are configured correctly
# before tasks run. This is required because Xero models have relationships
# to auth models (Tenant, PracticeUser) that need to be registered.
from app.modules.admin import models as admin_models  # noqa: F401
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.bas import models as bas_models  # noqa: F401
from app.modules.billing import models as billing_models  # noqa: F401
from app.modules.insights import models as insight_models  # noqa: F401
from app.modules.integrations.xero import models as xero_models  # noqa: F401
from app.modules.knowledge import models as knowledge_models  # noqa: F401
from app.modules.notifications import models as notification_models  # noqa: F401

# Import module-level tasks (tasks defined in module directories)
from app.modules.onboarding import (
    models as onboarding_models,  # noqa: F401
    tasks as onboarding_tasks,  # noqa: F401
)
from app.modules.portal import models as portal_models  # noqa: F401
from app.modules.quality import models as quality_models  # noqa: F401
from app.modules.tax_planning import models as tax_planning_models  # noqa: F401
from app.modules.triggers import models as trigger_models  # noqa: F401

# Import task modules to register them with Celery
from app.tasks import (
    aggregation,  # noqa: F401  Client AI context aggregations
    bas,  # noqa: F401
    insights,  # noqa: F401  Proactive insight generation
    knowledge,  # noqa: F401
    quality,  # noqa: F401
    scheduler,  # noqa: F401
    tax_planning,  # noqa: F401  Multi-agent tax planning pipeline
    triggers,  # noqa: F401  Automated trigger execution
    xero,  # noqa: F401
)

# Import tasks from subdirectories
from app.tasks.portal import (
    auto_reminders,  # noqa: F401
    send_bulk_requests,  # noqa: F401
)
