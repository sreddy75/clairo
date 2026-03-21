"""Celery application configuration for Clairo.

Configures Celery for background task processing with Redis as the
broker and result backend.

Usage:
    # Start worker
    celery -A app.tasks.celery_app worker --loglevel=info

    # Start beat scheduler (for periodic tasks)
    celery -A app.tasks.celery_app beat --loglevel=info

    # Call a task
    from app.tasks.celery_app import example_task
    result = example_task.delay("hello")
"""

import logging
from typing import Any

from celery import Celery, Task
from celery.signals import worker_shutting_down

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
celery_settings = settings.celery

# Create Celery application
celery_app = Celery(
    "clairo",
    broker=celery_settings.broker_url,
    backend=celery_settings.result_backend,
)

# Configure Celery
celery_app.conf.update(
    # Task settings
    task_default_queue=celery_settings.task_default_queue,
    task_time_limit=celery_settings.task_time_limit,
    task_soft_time_limit=celery_settings.task_soft_time_limit,
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,  # Requeue if worker dies
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    result_extended=True,  # Store additional task metadata
    # Worker settings
    worker_prefetch_multiplier=1,  # Fair distribution
    worker_concurrency=4,  # Number of worker processes
    worker_max_tasks_per_child=1000,  # Restart worker after N tasks
    # Task tracking
    task_track_started=True,
    task_send_sent_event=True,
    # Beat scheduler: use RedBeat (Redis-backed) instead of file-based
    # PersistentScheduler. Railway's ephemeral filesystem loses the
    # celerybeat-schedule file on every deploy/restart.
    beat_scheduler="redbeat.RedBeatScheduler",
    redbeat_redis_url=celery_settings.broker_url,
)

# Auto-discover tasks from app.tasks package
celery_app.autodiscover_tasks(["app.tasks"])


@worker_shutting_down.connect
def on_worker_shutting_down(sig, how, exitcode, **kwargs):  # type: ignore[no-untyped-def]
    """Handle worker SIGTERM for graceful shutdown.

    Logs shutdown event so Railway/monitoring can observe clean exits.
    Celery's warm shutdown (SIGTERM) already stops accepting new tasks
    and waits for in-flight tasks to finish (up to task_time_limit).
    """
    logger.info(
        "Celery worker shutting down (signal=%s, how=%s, exitcode=%s). "
        "Finishing in-flight tasks...",
        sig,
        how,
        exitcode,
    )


@celery_app.task(  # type: ignore[misc]
    bind=True,
    name="app.tasks.example_task",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def example_task(self: Task, message: str) -> dict[str, Any]:
    """Example task demonstrating Celery configuration.

    This task shows:
    - Automatic retry with exponential backoff
    - Task binding for accessing self.request
    - Return value serialization

    Args:
        message: A message to process.

    Returns:
        Dict with processed message and task metadata.
    """
    return {
        "message": f"Processed: {message}",
        "task_id": self.request.id,
        "retries": self.request.retries,
    }


# Use crontab for the schedule
from celery.schedules import crontab  # noqa: E402

# Define periodic tasks (beat schedule)
celery_app.conf.beat_schedule = {
    # Daily sync of all Xero connections (runs at 2am UTC = 12pm/1pm AEST)
    "sync-all-connections-daily": {
        "task": "app.tasks.scheduler.sync_all_stale_connections",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": celery_settings.task_default_queue},
    },
    # Daily BAS deadline notification check (runs at 20:00 UTC = 6am AEST)
    # Spec 011: Notifies accountants of approaching BAS lodgement deadlines
    "check-bas-deadlines-daily": {
        "task": "app.tasks.bas.check_lodgement_deadlines",
        "schedule": crontab(hour=20, minute=0),
        "options": {"queue": celery_settings.task_default_queue},
    },
    # Weekly knowledge base ingestion (runs Sunday 3am UTC = 1pm/2pm AEST)
    # Spec 012: Refreshes knowledge base from ATO and other sources
    "ingest-knowledge-weekly": {
        "task": "app.tasks.knowledge.ingest_all_sources",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),
        "options": {"queue": celery_settings.task_default_queue},
    },
    # Daily insight generation for all tenants (runs at 4am UTC = 2pm/3pm AEST)
    # Spec 016: Generates proactive insights after sync
    "generate-insights-daily": {
        "task": "app.tasks.insights.generate_for_all_tenants",
        "schedule": crontab(hour=4, minute=0),
        "options": {"queue": celery_settings.task_default_queue},
    },
    # Daily cleanup of expired insights (runs at 5am UTC = 3pm/4pm AEST)
    # Spec 016: Marks expired insights for cleanup
    "cleanup-expired-insights-daily": {
        "task": "app.tasks.insights.cleanup_expired",
        "schedule": crontab(hour=5, minute=0),
        "options": {"queue": celery_settings.task_default_queue},
    },
    # Run time-scheduled triggers (runs at 20:00 UTC = 6am AEST)
    # Spec 017: Executes time-based triggers (morning check, BAS reminders)
    "run-time-triggers-daily": {
        "task": "app.tasks.triggers.run_time_triggers",
        "schedule": crontab(hour=20, minute=0),
        "options": {"queue": celery_settings.task_default_queue},
    },
    # Run time-scheduled triggers again (runs at 23:00 UTC = 9am AEST)
    # Spec 017: Second run for BAS deadline reminders
    "run-time-triggers-morning": {
        "task": "app.tasks.triggers.run_time_triggers",
        "schedule": crontab(hour=23, minute=0),
        "options": {"queue": celery_settings.task_default_queue},
    },
    # Daily usage snapshot capture (runs at midnight UTC)
    # Spec 020: Captures usage data for historical trend analysis
    "capture-usage-snapshots-daily": {
        "task": "app.tasks.usage.capture_daily_usage_snapshots",
        "schedule": crontab(hour=0, minute=0),
        "options": {"queue": celery_settings.task_default_queue},
    },
    # Monthly usage counter reset (runs 1st of month at 00:05 UTC)
    # Spec 020: Resets ai_queries_month and documents_month counters
    "reset-usage-counters-monthly": {
        "task": "app.tasks.usage.reset_monthly_usage_counters",
        "schedule": crontab(day_of_month=1, hour=0, minute=5),
        "options": {"queue": celery_settings.task_default_queue},
    },
    # Daily trial reminder check (runs at 22:00 UTC = 9am AEDT)
    # Spec 021: Sends trial ending reminders at 3 days and 1 day
    "check-trial-reminders-daily": {
        "task": "app.modules.onboarding.tasks.check_trial_reminders",
        "schedule": crontab(hour=22, minute=0),
        "options": {"queue": celery_settings.task_default_queue},
    },
    # Daily onboarding drip emails (runs at 22:30 UTC = 9:30am AEDT)
    # Spec 021: Sends nudge emails for incomplete onboardings
    "send-onboarding-drip-emails-daily": {
        "task": "app.modules.onboarding.tasks.send_onboarding_drip_emails",
        "schedule": crontab(hour=22, minute=30),
        "options": {"queue": celery_settings.task_default_queue},
    },
    # Nightly report sync (runs at 3:00 UTC = 2pm AEDT, 1pm AEST)
    # Spec 023: Syncs financial reports from Xero for all active connections
    "sync-reports-nightly": {
        "task": "app.tasks.reports.nightly_report_sync",
        "schedule": crontab(hour=3, minute=0),
        "options": {"queue": celery_settings.task_default_queue},
    },
    # Daily portal auto-reminders (runs at 21:00 UTC = 8am AEDT)
    # Spec 030: Sends automatic reminders for pending document requests
    "send-portal-auto-reminders-daily": {
        "task": "portal.send_auto_reminders",
        "schedule": crontab(hour=21, minute=0),
        "options": {"queue": celery_settings.task_default_queue},
    },
    # Clean up stuck sync jobs every 15 minutes
    # Spec 043: Finds jobs stuck in pending/in_progress for >60 minutes
    # and marks them as failed so new syncs can proceed
    "cleanup-stuck-sync-jobs": {
        "task": "app.tasks.scheduler.cleanup_stuck_sync_jobs",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": celery_settings.task_default_queue},
    },
    # --- Spec 045: Knowledge base freshness monitoring ---
    # Check ATO RSS for new rulings every 4 hours
    "monitor-ato-rss": {
        "task": "app.tasks.knowledge.monitor_ato_rss",
        "schedule": crontab(minute=0, hour="*/4"),
        "options": {"queue": celery_settings.task_default_queue},
    },
    # Weekly delta crawl of ATO Legal Database (Sunday 4am UTC)
    "delta-crawl-ato-legal-db-weekly": {
        "task": "app.tasks.knowledge.delta_crawl_ato_legal_db",
        "schedule": crontab(hour=4, minute=30, day_of_week=0),
        "options": {"queue": celery_settings.task_default_queue},
    },
    # Monthly legislation sync — detect amended acts (1st of month 5am UTC)
    "sync-legislation-monthly": {
        "task": "app.tasks.knowledge.sync_legislation",
        "schedule": crontab(day_of_month=1, hour=5, minute=0),
        "options": {"queue": celery_settings.task_default_queue},
    },
    # Daily check for new tax judgments from Federal Court RSS (6am UTC)
    "monitor-federal-court-rss-daily": {
        "task": "app.tasks.knowledge.monitor_federal_court_rss",
        "schedule": crontab(hour=6, minute=0),
        "options": {"queue": celery_settings.task_default_queue},
    },
    # Weekly check for superseded rulings (Monday 3am UTC)
    "check-supersessions-weekly": {
        "task": "app.tasks.knowledge.check_supersessions",
        "schedule": crontab(hour=3, minute=0, day_of_week=1),
        "options": {"queue": celery_settings.task_default_queue},
    },
}
