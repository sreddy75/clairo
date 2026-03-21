# Quickstart: ATOtrack Workflow Integration

**Spec**: 028-atotrack-workflow-integration
**Purpose**: Developer guide for implementing ATOtrack workflow - task creation, insight generation, notifications, response drafting, and practice management integration.

---

## Prerequisites

- Python 3.12+
- PostgreSQL 16 with existing tables from Spec 027
- Redis for Celery
- Anthropic API key for response drafting
- Existing task/insight/notification modules

---

## 1. Task Rules Engine

### Task Rule Configuration

```python
# backend/app/modules/email/atotrack/task_rules.py
from dataclasses import dataclass
from enum import Enum
from datetime import date, timedelta

from app.modules.email.ato_parsing.enums import ATONoticeType


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class TaskRule:
    """Rule for auto-creating tasks from ATO correspondence."""
    title_template: str
    default_days: int
    priority: TaskPriority
    description_template: str | None = None


TASK_RULES: dict[ATONoticeType, TaskRule] = {
    ATONoticeType.AUDIT_NOTICE: TaskRule(
        title_template="Respond to ATO audit - {client_name}",
        default_days=28,
        priority=TaskPriority.URGENT,
        description_template="ATO audit notice received. Reference: {reference_number}. Response required by {due_date}.",
    ),
    ATONoticeType.PENALTY_NOTICE: TaskRule(
        title_template="Review ATO penalty ${amount:,.2f} - {client_name}",
        default_days=21,
        priority=TaskPriority.HIGH,
        description_template="Penalty notice for ${amount:,.2f}. Consider remission request if eligible.",
    ),
    ATONoticeType.DEBT_NOTICE: TaskRule(
        title_template="Address ATO debt ${amount:,.2f} - {client_name}",
        default_days=14,
        priority=TaskPriority.HIGH,
        description_template="Debt notification for ${amount:,.2f}. Arrange payment or payment plan.",
    ),
    ATONoticeType.ACTIVITY_STATEMENT_REMINDER: TaskRule(
        title_template="Lodge Activity Statement - {client_name}",
        default_days=14,
        priority=TaskPriority.MEDIUM,
        description_template="Activity statement reminder for period {period}.",
    ),
    ATONoticeType.INFORMATION_REQUEST: TaskRule(
        title_template="Provide information to ATO - {client_name}",
        default_days=21,
        priority=TaskPriority.MEDIUM,
        description_template="ATO has requested additional information. Reference: {reference_number}.",
    ),
    ATONoticeType.OBJECTION_OUTCOME: TaskRule(
        title_template="Review objection outcome - {client_name}",
        default_days=28,
        priority=TaskPriority.MEDIUM,
        description_template="Objection decision received. Review outcome and advise client.",
    ),
    ATONoticeType.COMPLIANCE_LETTER: TaskRule(
        title_template="Address compliance issue - {client_name}",
        default_days=21,
        priority=TaskPriority.HIGH,
        description_template="Compliance letter received. Review and respond to ATO concerns.",
    ),
}

# Notice types that don't create tasks (informational only)
NO_TASK_TYPES = {
    ATONoticeType.PAYMENT_CONFIRMATION,
    ATONoticeType.REFUND_NOTIFICATION,
    ATONoticeType.REGISTRATION_CONFIRMATION,
    ATONoticeType.GENERAL_CORRESPONDENCE,
}


def get_task_rule(notice_type: ATONoticeType) -> TaskRule | None:
    """Get task rule for notice type, or None if no task should be created."""
    if notice_type in NO_TASK_TYPES:
        return None
    return TASK_RULES.get(notice_type)


def calculate_due_date(
    correspondence_due_date: date | None,
    rule: TaskRule,
) -> date:
    """Calculate task due date from correspondence or default."""
    if correspondence_due_date:
        return correspondence_due_date
    return date.today() + timedelta(days=rule.default_days)


def format_task_title(
    rule: TaskRule,
    client_name: str,
    amount: float | None = None,
    **kwargs,
) -> str:
    """Format task title with placeholders."""
    return rule.title_template.format(
        client_name=client_name or "Unknown Client",
        amount=amount or 0,
        **kwargs,
    )
```

### Task Creation Service

```python
# backend/app/modules/email/atotrack/service.py
from uuid import UUID
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.email.ato_parsing.models import ATOCorrespondence
from app.modules.tasks.repository import TaskRepository
from app.modules.tasks.schemas import TaskCreate
from app.core.audit import audit_log

from .task_rules import (
    get_task_rule,
    calculate_due_date,
    format_task_title,
)


class ATOtrackService:
    """Orchestrates ATOtrack workflow operations."""

    def __init__(
        self,
        session: AsyncSession,
        task_repo: TaskRepository,
        insight_repo: InsightRepository,
        notification_service: NotificationService,
    ):
        self.session = session
        self.task_repo = task_repo
        self.insight_repo = insight_repo
        self.notification_service = notification_service

    async def process_correspondence(
        self,
        correspondence: ATOCorrespondence,
    ) -> None:
        """Process parsed correspondence - create task, insight, schedule notifications."""
        # Step 1: Create task if applicable
        task = await self._create_task_if_needed(correspondence)
        if task:
            correspondence.task_id = task.id

        # Step 2: Create insight if applicable
        insight = await self._create_insight_if_needed(correspondence)
        if insight:
            correspondence.insight_id = insight.id

        # Step 3: Schedule notifications
        if correspondence.due_date:
            await self._schedule_notifications(correspondence)

        # Step 4: Sync to practice management (async)
        await self._trigger_pm_sync(correspondence)

        await self.session.commit()

        # Audit
        await audit_log(
            event_type="atotrack.processed",
            entity_type="correspondence",
            entity_id=correspondence.id,
            data={
                "task_created": task is not None,
                "insight_created": insight is not None,
            },
        )

    async def _create_task_if_needed(
        self,
        correspondence: ATOCorrespondence,
    ) -> Task | None:
        """Create task based on notice type rules."""
        rule = get_task_rule(correspondence.notice_type)
        if not rule:
            return None

        # Check for existing task
        existing = await self.task_repo.get_by_correspondence_id(
            correspondence.id
        )
        if existing:
            return existing

        # Get client name
        client_name = "Unknown Client"
        if correspondence.client_id:
            client = await self.client_repo.get(correspondence.client_id)
            client_name = client.name if client else "Unknown Client"

        # Create task
        due_date = calculate_due_date(correspondence.due_date, rule)
        title = format_task_title(
            rule,
            client_name=client_name,
            amount=correspondence.amount,
            reference_number=correspondence.reference_number,
            due_date=due_date.isoformat(),
            period=correspondence.period,
        )

        task = await self.task_repo.create(
            TaskCreate(
                tenant_id=correspondence.tenant_id,
                title=title,
                description=rule.description_template.format(
                    amount=correspondence.amount or 0,
                    reference_number=correspondence.reference_number or "N/A",
                    due_date=due_date.isoformat(),
                    period=correspondence.period or "N/A",
                ) if rule.description_template else None,
                due_date=due_date,
                priority=rule.priority,
                client_id=correspondence.client_id,
                correspondence_id=correspondence.id,
            )
        )

        await audit_log(
            event_type="atotrack.task.created",
            entity_type="task",
            entity_id=task.id,
            data={
                "correspondence_id": str(correspondence.id),
                "notice_type": correspondence.notice_type.value,
                "due_date": due_date.isoformat(),
            },
        )

        return task
```

---

## 2. Insight Generation

### Insight Rules

```python
# backend/app/modules/email/atotrack/insight_rules.py
from dataclasses import dataclass
from enum import Enum

from app.modules.email.ato_parsing.enums import ATONoticeType
from app.modules.insights.enums import InsightSeverity


@dataclass
class InsightRule:
    """Rule for generating insights from ATO correspondence."""
    title_template: str
    severity: InsightSeverity
    description_template: str


INSIGHT_RULES: dict[ATONoticeType, InsightRule] = {
    ATONoticeType.AUDIT_NOTICE: InsightRule(
        title_template="ATO Audit Notice - Response Required",
        severity=InsightSeverity.CRITICAL,
        description_template="ATO audit initiated for {client_name}. Reference: {reference_number}. Immediate attention required.",
    ),
    ATONoticeType.PENALTY_NOTICE: InsightRule(
        title_template="ATO Penalty: ${amount:,.2f}",
        severity=InsightSeverity.HIGH,
        description_template="Penalty of ${amount:,.2f} issued for {client_name}. Review for remission eligibility.",
    ),
    ATONoticeType.DEBT_NOTICE: InsightRule(
        title_template="ATO Debt: ${amount:,.2f}",
        severity=InsightSeverity.HIGH,
        description_template="Outstanding debt of ${amount:,.2f} for {client_name}. Payment arrangement may be needed.",
    ),
    ATONoticeType.COMPLIANCE_LETTER: InsightRule(
        title_template="ATO Compliance Concern",
        severity=InsightSeverity.HIGH,
        description_template="Compliance issue flagged by ATO for {client_name}. Review and address.",
    ),
    ATONoticeType.OBJECTION_OUTCOME: InsightRule(
        title_template="Objection Decision Received",
        severity=InsightSeverity.MEDIUM,
        description_template="ATO has made a decision on objection for {client_name}.",
    ),
}

# High-value thresholds for severity escalation
AMOUNT_THRESHOLDS = {
    10_000: InsightSeverity.CRITICAL,  # >= $10k
    5_000: InsightSeverity.HIGH,       # >= $5k
    1_000: InsightSeverity.MEDIUM,     # >= $1k
}


def get_insight_rule(notice_type: ATONoticeType) -> InsightRule | None:
    """Get insight rule for notice type."""
    return INSIGHT_RULES.get(notice_type)


def calculate_severity(
    base_severity: InsightSeverity,
    amount: float | None,
) -> InsightSeverity:
    """Escalate severity based on amount if applicable."""
    if amount is None:
        return base_severity

    for threshold, escalated_severity in sorted(
        AMOUNT_THRESHOLDS.items(), reverse=True
    ):
        if amount >= threshold:
            # Return the higher severity
            if escalated_severity.value > base_severity.value:
                return escalated_severity
            break

    return base_severity
```

### Insight Creation

```python
# In ATOtrackService

async def _create_insight_if_needed(
    self,
    correspondence: ATOCorrespondence,
) -> Insight | None:
    """Create insight based on notice type rules."""
    rule = get_insight_rule(correspondence.notice_type)
    if not rule:
        return None

    # Check for existing insight
    existing = await self.insight_repo.get_by_correspondence_id(
        correspondence.id
    )
    if existing:
        return existing

    # Get client name
    client_name = "Unknown Client"
    if correspondence.client_id:
        client = await self.client_repo.get(correspondence.client_id)
        client_name = client.name if client else "Unknown Client"

    # Calculate severity (may escalate based on amount)
    severity = calculate_severity(rule.severity, correspondence.amount)

    # Create insight
    insight = await self.insight_repo.create(
        InsightCreate(
            tenant_id=correspondence.tenant_id,
            title=rule.title_template.format(
                amount=correspondence.amount or 0,
            ),
            description=rule.description_template.format(
                client_name=client_name,
                amount=correspondence.amount or 0,
                reference_number=correspondence.reference_number or "N/A",
            ),
            severity=severity,
            client_id=correspondence.client_id,
            action_url=f"/atotrack/{correspondence.id}",
            due_date=correspondence.due_date,
            correspondence_id=correspondence.id,
        )
    )

    await audit_log(
        event_type="atotrack.insight.created",
        entity_type="insight",
        entity_id=insight.id,
        data={
            "correspondence_id": str(correspondence.id),
            "severity": severity.value,
        },
    )

    return insight
```

---

## 3. Notification Scheduling

### Notification Configuration

```python
# backend/app/modules/email/atotrack/notification_rules.py
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum


class NotificationType(str, Enum):
    SEVEN_DAYS = "7_days"
    THREE_DAYS = "3_days"
    ONE_DAY = "1_day"
    OVERDUE = "overdue"


@dataclass
class NotificationSchedule:
    """Schedule for deadline notifications."""
    notification_type: NotificationType
    days_before: int  # Negative for overdue
    email_template: str
    push_enabled: bool
    urgency: str


NOTIFICATION_SCHEDULE = [
    NotificationSchedule(
        notification_type=NotificationType.SEVEN_DAYS,
        days_before=7,
        email_template="atotrack/reminder_7_days",
        push_enabled=False,
        urgency="normal",
    ),
    NotificationSchedule(
        notification_type=NotificationType.THREE_DAYS,
        days_before=3,
        email_template="atotrack/reminder_3_days",
        push_enabled=True,
        urgency="high",
    ),
    NotificationSchedule(
        notification_type=NotificationType.ONE_DAY,
        days_before=1,
        email_template="atotrack/reminder_1_day",
        push_enabled=True,
        urgency="urgent",
    ),
    NotificationSchedule(
        notification_type=NotificationType.OVERDUE,
        days_before=-1,  # 1 day after due
        email_template="atotrack/overdue",
        push_enabled=True,
        urgency="critical",
    ),
]


def calculate_notification_dates(
    due_date: date,
) -> list[tuple[date, NotificationSchedule]]:
    """Calculate notification dates based on due date."""
    today = date.today()
    notifications = []

    for schedule in NOTIFICATION_SCHEDULE:
        notification_date = due_date - timedelta(days=schedule.days_before)

        # Only schedule future notifications
        if notification_date >= today:
            notifications.append((notification_date, schedule))

    return notifications
```

### Notification Service Integration

```python
# In ATOtrackService

async def _schedule_notifications(
    self,
    correspondence: ATOCorrespondence,
) -> None:
    """Schedule deadline notifications for correspondence."""
    if not correspondence.due_date:
        return

    notifications = calculate_notification_dates(correspondence.due_date)

    for notification_date, schedule in notifications:
        await self.notification_service.schedule(
            ScheduledNotification(
                tenant_id=correspondence.tenant_id,
                entity_type="correspondence",
                entity_id=correspondence.id,
                notification_type=schedule.notification_type.value,
                scheduled_at=notification_date,
                email_template=schedule.email_template,
                push_enabled=schedule.push_enabled,
                context={
                    "correspondence_id": str(correspondence.id),
                    "title": correspondence.title,
                    "due_date": correspondence.due_date.isoformat(),
                    "client_name": await self._get_client_name(correspondence),
                    "urgency": schedule.urgency,
                },
            )
        )
```

---

## 4. Response Drafting with AI

### Response Drafter Service

```python
# backend/app/modules/email/atotrack/response_drafter.py
from uuid import UUID
import anthropic

from app.modules.knowledge.rag import RAGService
from app.modules.email.ato_parsing.models import ATOCorrespondence

from .models import ResponseDraft, ResponseDraftType, ResponseDraftStatus


# Prompt templates for different response types
PROMPTS = {
    ResponseDraftType.AUDIT_RESPONSE: """
You are a professional tax agent drafting a response to an ATO audit notice.

Client: {client_name}
Reference: {reference_number}
Audit Period: {period}
Notice Summary: {summary}

Relevant ATO Guidelines:
{rag_context}

Draft a professional response that:
1. Acknowledges receipt of the audit notice
2. Confirms the client's intention to cooperate
3. Requests specific information about what records are needed
4. Proposes a timeline for providing documentation
5. Notes any concerns or clarifications needed

Use formal business letter format. Do not make up specific facts about the client.
""",

    ResponseDraftType.REMISSION_REQUEST: """
You are a professional tax agent drafting a penalty remission request to the ATO.

Client: {client_name}
Penalty Amount: ${amount:,.2f}
Reference: {reference_number}
Penalty Reason: {summary}

Relevant ATO Guidelines on Remission:
{rag_context}

Draft a remission request that:
1. Clearly identifies the penalty and reference number
2. Explains the circumstances (use placeholders for specific details)
3. Demonstrates the client's compliance history (placeholder)
4. Cites relevant remission grounds
5. Requests full or partial remission

Use formal business letter format. Include [PLACEHOLDER] markers for information the accountant needs to add.
""",

    ResponseDraftType.EXTENSION_REQUEST: """
You are a professional tax agent requesting an extension from the ATO.

Client: {client_name}
Reference: {reference_number}
Current Due Date: {due_date}
Matter: {summary}

Relevant ATO Guidelines:
{rag_context}

Draft an extension request that:
1. Identifies the matter and current deadline
2. Explains why an extension is needed (use placeholders)
3. Proposes a new deadline
4. Commits to providing required information by the new date

Keep the tone professional and cooperative.
""",
}


class ResponseDrafter:
    """AI-powered response drafting for ATO correspondence."""

    def __init__(
        self,
        anthropic_client: anthropic.AsyncAnthropic,
        rag_service: RAGService,
    ):
        self.client = anthropic_client
        self.rag = rag_service

    async def generate_draft(
        self,
        correspondence: ATOCorrespondence,
        draft_type: ResponseDraftType,
        client_name: str,
        additional_context: str | None = None,
    ) -> ResponseDraft:
        """Generate AI response draft."""
        # Step 1: Get relevant context from RAG
        rag_query = self._build_rag_query(correspondence, draft_type)
        rag_results = await self.rag.query(
            tenant_id=correspondence.tenant_id,
            collection="ato_guidelines",
            query=rag_query,
            top_k=5,
        )
        rag_context = "\n\n".join(
            f"- {r.content}" for r in rag_results
        )

        # Step 2: Build prompt
        prompt_template = PROMPTS.get(draft_type)
        if not prompt_template:
            raise ValueError(f"No template for draft type: {draft_type}")

        prompt = prompt_template.format(
            client_name=client_name,
            reference_number=correspondence.reference_number or "N/A",
            period=correspondence.period or "N/A",
            summary=correspondence.summary or "See attached notice",
            amount=correspondence.amount or 0,
            due_date=correspondence.due_date.isoformat() if correspondence.due_date else "N/A",
            rag_context=rag_context or "No specific guidelines found.",
        )

        if additional_context:
            prompt += f"\n\nAdditional context from accountant: {additional_context}"

        # Step 3: Generate with Claude
        start_time = time.time()
        response = await self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        generation_time_ms = int((time.time() - start_time) * 1000)

        # Step 4: Create draft record
        draft = ResponseDraft(
            tenant_id=correspondence.tenant_id,
            correspondence_id=correspondence.id,
            draft_type=draft_type,
            status=ResponseDraftStatus.DRAFT,
            content=response.content[0].text,
            model_used="claude-3-5-sonnet-20241022",
            rag_sources=[r.source_id for r in rag_results],
            generation_time_ms=generation_time_ms,
        )

        return draft

    def _build_rag_query(
        self,
        correspondence: ATOCorrespondence,
        draft_type: ResponseDraftType,
    ) -> str:
        """Build RAG query for relevant guidelines."""
        queries = {
            ResponseDraftType.AUDIT_RESPONSE: f"ATO audit response requirements {correspondence.notice_type.value}",
            ResponseDraftType.REMISSION_REQUEST: "ATO penalty remission grounds criteria",
            ResponseDraftType.EXTENSION_REQUEST: "ATO extension request requirements",
        }
        return queries.get(draft_type, f"ATO {correspondence.notice_type.value} response guidelines")
```

---

## 5. Dashboard Aggregation

### Dashboard Service

```python
# backend/app/modules/email/atotrack/dashboard.py
from datetime import date, timedelta
from dataclasses import dataclass

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.email.ato_parsing.models import ATOCorrespondence
from app.modules.email.ato_parsing.enums import CorrespondenceStatus


@dataclass
class DashboardSummary:
    overdue: int
    due_soon: int  # Within 7 days
    in_progress: int
    triage: int
    resolved_this_month: int


@dataclass
class DashboardData:
    summary: DashboardSummary
    requires_attention: list[ATOCorrespondence]
    recent_resolved: list[ATOCorrespondence]


class ATOtrackDashboard:
    """Dashboard aggregation for ATOtrack."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_dashboard(
        self,
        tenant_id: UUID,
    ) -> DashboardData:
        """Get aggregated dashboard data."""
        today = date.today()
        week_from_now = today + timedelta(days=7)
        month_start = today.replace(day=1)

        # Base query for active correspondence
        base_query = select(ATOCorrespondence).where(
            and_(
                ATOCorrespondence.tenant_id == tenant_id,
                ATOCorrespondence.status != CorrespondenceStatus.RESOLVED,
            )
        )

        # Summary counts
        summary = await self._get_summary_counts(
            tenant_id, today, week_from_now, month_start
        )

        # Requires attention (sorted by urgency)
        requires_attention = await self._get_requires_attention(
            tenant_id, today, limit=10
        )

        # Recent resolved
        recent_resolved = await self._get_recent_resolved(
            tenant_id, limit=5
        )

        return DashboardData(
            summary=summary,
            requires_attention=requires_attention,
            recent_resolved=recent_resolved,
        )

    async def _get_summary_counts(
        self,
        tenant_id: UUID,
        today: date,
        week_from_now: date,
        month_start: date,
    ) -> DashboardSummary:
        """Get summary card counts."""
        # Overdue count
        overdue_result = await self.session.execute(
            select(func.count(ATOCorrespondence.id)).where(
                and_(
                    ATOCorrespondence.tenant_id == tenant_id,
                    ATOCorrespondence.status != CorrespondenceStatus.RESOLVED,
                    ATOCorrespondence.due_date < today,
                )
            )
        )
        overdue = overdue_result.scalar() or 0

        # Due soon count (within 7 days, not overdue)
        due_soon_result = await self.session.execute(
            select(func.count(ATOCorrespondence.id)).where(
                and_(
                    ATOCorrespondence.tenant_id == tenant_id,
                    ATOCorrespondence.status != CorrespondenceStatus.RESOLVED,
                    ATOCorrespondence.due_date >= today,
                    ATOCorrespondence.due_date <= week_from_now,
                )
            )
        )
        due_soon = due_soon_result.scalar() or 0

        # In progress count
        in_progress_result = await self.session.execute(
            select(func.count(ATOCorrespondence.id)).where(
                and_(
                    ATOCorrespondence.tenant_id == tenant_id,
                    ATOCorrespondence.status == CorrespondenceStatus.IN_PROGRESS,
                )
            )
        )
        in_progress = in_progress_result.scalar() or 0

        # Triage count (needs review)
        triage_result = await self.session.execute(
            select(func.count(ATOCorrespondence.id)).where(
                and_(
                    ATOCorrespondence.tenant_id == tenant_id,
                    ATOCorrespondence.needs_triage == True,
                )
            )
        )
        triage = triage_result.scalar() or 0

        # Resolved this month
        resolved_result = await self.session.execute(
            select(func.count(ATOCorrespondence.id)).where(
                and_(
                    ATOCorrespondence.tenant_id == tenant_id,
                    ATOCorrespondence.status == CorrespondenceStatus.RESOLVED,
                    ATOCorrespondence.resolved_at >= month_start,
                )
            )
        )
        resolved_this_month = resolved_result.scalar() or 0

        return DashboardSummary(
            overdue=overdue,
            due_soon=due_soon,
            in_progress=in_progress,
            triage=triage,
            resolved_this_month=resolved_this_month,
        )

    async def _get_requires_attention(
        self,
        tenant_id: UUID,
        today: date,
        limit: int = 10,
    ) -> list[ATOCorrespondence]:
        """Get items requiring attention, sorted by urgency."""
        result = await self.session.execute(
            select(ATOCorrespondence)
            .where(
                and_(
                    ATOCorrespondence.tenant_id == tenant_id,
                    ATOCorrespondence.status != CorrespondenceStatus.RESOLVED,
                )
            )
            .order_by(
                # Overdue first, then by due date
                (ATOCorrespondence.due_date < today).desc(),
                ATOCorrespondence.due_date.asc().nulls_last(),
                ATOCorrespondence.created_at.desc(),
            )
            .limit(limit)
        )
        return list(result.scalars().all())
```

---

## 6. Practice Management Integration

### Karbon Integration

```python
# backend/app/modules/email/atotrack/integrations/karbon.py
import httpx
from dataclasses import dataclass


@dataclass
class KarbonTask:
    title: str
    description: str | None
    due_date: str  # ISO format
    assignee_email: str | None
    client_key: str | None


class KarbonClient:
    """Karbon API client for task sync."""

    BASE_URL = "https://api.karbonhq.com/v3"

    def __init__(self, api_key: str, access_key: str):
        self.api_key = api_key
        self.access_key = access_key

    async def create_task(self, task: KarbonTask) -> dict:
        """Create a task in Karbon."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/Tasks",
                headers=self._headers(),
                json={
                    "Title": task.title,
                    "Description": task.description,
                    "DueDate": task.due_date,
                    "AssigneeEmailAddress": task.assignee_email,
                    "ClientKey": task.client_key,
                    "TaskType": "WorkItem",
                },
            )
            response.raise_for_status()
            return response.json()

    async def complete_task(self, task_key: str) -> dict:
        """Mark a Karbon task as complete."""
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.BASE_URL}/Tasks/{task_key}",
                headers=self._headers(),
                json={"Status": "Completed"},
            )
            response.raise_for_status()
            return response.json()

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "AccessKey": self.access_key,
            "Content-Type": "application/json",
        }
```

### XPM Integration

```python
# backend/app/modules/email/atotrack/integrations/xpm.py
import httpx
from datetime import date


class XPMClient:
    """Xero Practice Manager API client."""

    BASE_URL = "https://api.xero.com/practicemanager/3.0"

    def __init__(self, access_token: str):
        self.access_token = access_token

    async def create_job(
        self,
        client_id: str,
        name: str,
        description: str | None,
        due_date: date,
    ) -> dict:
        """Create a job in XPM."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/job.api/add",
                headers=self._headers(),
                json={
                    "Job": {
                        "ClientID": client_id,
                        "Name": name,
                        "Description": description,
                        "DueDate": due_date.isoformat(),
                        "State": "Planned",
                    }
                },
            )
            response.raise_for_status()
            return response.json()

    async def complete_job(self, job_id: str) -> dict:
        """Complete a job in XPM."""
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.BASE_URL}/job.api/{job_id}",
                headers=self._headers(),
                json={
                    "Job": {
                        "State": "Completed",
                    }
                },
            )
            response.raise_for_status()
            return response.json()

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
```

---

## 7. Resolution Flow

### Resolve Correspondence

```python
# In ATOtrackService

async def resolve_correspondence(
    self,
    correspondence_id: UUID,
    user_id: UUID,
    resolution_notes: str | None = None,
) -> ResolveResult:
    """Resolve correspondence and all linked items."""
    correspondence = await self.correspondence_repo.get(correspondence_id)
    if not correspondence:
        raise CorrespondenceNotFoundError(correspondence_id)

    # Update correspondence status
    correspondence.status = CorrespondenceStatus.RESOLVED
    correspondence.resolved_at = datetime.utcnow()
    correspondence.resolved_by = user_id
    correspondence.resolution_notes = resolution_notes

    # Complete linked task
    task_completed = False
    if correspondence.task_id:
        task = await self.task_repo.get(correspondence.task_id)
        if task and task.status != TaskStatus.COMPLETED:
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            task_completed = True

    # Dismiss linked insight
    insight_dismissed = False
    if correspondence.insight_id:
        insight = await self.insight_repo.get(correspondence.insight_id)
        if insight and insight.status != InsightStatus.DISMISSED:
            insight.status = InsightStatus.DISMISSED
            insight.dismissed_at = datetime.utcnow()
            insight_dismissed = True

    # Cancel pending notifications
    notifications_cancelled = await self.notification_service.cancel_for_entity(
        entity_type="correspondence",
        entity_id=correspondence_id,
    )

    await self.session.commit()

    # Audit
    await audit_log(
        event_type="atotrack.resolved",
        entity_type="correspondence",
        entity_id=correspondence_id,
        user_id=user_id,
        data={
            "task_completed": task_completed,
            "insight_dismissed": insight_dismissed,
            "notifications_cancelled": notifications_cancelled,
        },
    )

    return ResolveResult(
        correspondence_id=correspondence_id,
        status=CorrespondenceStatus.RESOLVED,
        task_completed=task_completed,
        insight_dismissed=insight_dismissed,
        notifications_cancelled=notifications_cancelled,
    )
```

---

## 8. API Router

```python
# backend/app/modules/email/atotrack/router.py
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_current_user
from app.core.dependencies import get_atotrack_service

from .schemas import (
    DashboardResponse,
    CorrespondenceListResponse,
    CorrespondenceDetailResponse,
    ResolveRequest,
    ResolveResponse,
    GenerateDraftRequest,
    DraftJobResponse,
)

router = APIRouter(prefix="/atotrack", tags=["ATOtrack"])


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    service: ATOtrackService = Depends(get_atotrack_service),
):
    """Get ATOtrack dashboard data."""
    data = await service.get_dashboard(current_user.tenant_id)
    return DashboardResponse.from_domain(data)


@router.get("/correspondence", response_model=CorrespondenceListResponse)
async def list_correspondence(
    status: CorrespondenceStatus | None = None,
    client_id: UUID | None = None,
    notice_type: ATONoticeType | None = None,
    urgency: UrgencyLevel | None = None,
    due_before: date | None = None,
    due_after: date | None = None,
    search: str | None = None,
    page: int = 1,
    per_page: int = 25,
    sort_by: str = "due_date",
    sort_order: str = "asc",
    current_user: User = Depends(get_current_user),
    service: ATOtrackService = Depends(get_atotrack_service),
):
    """List correspondence with filters."""
    result = await service.list_correspondence(
        tenant_id=current_user.tenant_id,
        filters=CorrespondenceFilters(
            status=status,
            client_id=client_id,
            notice_type=notice_type,
            urgency=urgency,
            due_before=due_before,
            due_after=due_after,
            search=search,
        ),
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return CorrespondenceListResponse.from_domain(result)


@router.get("/correspondence/{id}", response_model=CorrespondenceDetailResponse)
async def get_correspondence(
    id: UUID,
    current_user: User = Depends(get_current_user),
    service: ATOtrackService = Depends(get_atotrack_service),
):
    """Get correspondence detail."""
    result = await service.get_correspondence(
        correspondence_id=id,
        tenant_id=current_user.tenant_id,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Correspondence not found")
    return CorrespondenceDetailResponse.from_domain(result)


@router.post("/correspondence/{id}/resolve", response_model=ResolveResponse)
async def resolve_correspondence(
    id: UUID,
    request: ResolveRequest,
    current_user: User = Depends(get_current_user),
    service: ATOtrackService = Depends(get_atotrack_service),
):
    """Mark correspondence as resolved."""
    result = await service.resolve_correspondence(
        correspondence_id=id,
        user_id=current_user.id,
        resolution_notes=request.resolution_notes,
    )
    return ResolveResponse.from_domain(result)


@router.post("/correspondence/{id}/draft", response_model=DraftJobResponse)
async def generate_draft(
    id: UUID,
    request: GenerateDraftRequest,
    current_user: User = Depends(get_current_user),
    service: ATOtrackService = Depends(get_atotrack_service),
):
    """Generate AI response draft."""
    job = await service.generate_response_draft(
        correspondence_id=id,
        draft_type=request.draft_type,
        additional_context=request.additional_context,
        user_id=current_user.id,
    )
    return DraftJobResponse(
        job_id=job.id,
        status="processing",
        estimated_completion=30,
    )
```

---

## Testing

### Unit Test Example

```python
# backend/tests/unit/modules/email/atotrack/test_task_rules.py
import pytest
from datetime import date, timedelta

from app.modules.email.ato_parsing.enums import ATONoticeType
from app.modules.email.atotrack.task_rules import (
    get_task_rule,
    calculate_due_date,
    format_task_title,
    TaskPriority,
)


class TestTaskRules:
    def test_audit_notice_creates_urgent_task(self):
        rule = get_task_rule(ATONoticeType.AUDIT_NOTICE)

        assert rule is not None
        assert rule.priority == TaskPriority.URGENT
        assert rule.default_days == 28

    def test_payment_confirmation_no_task(self):
        rule = get_task_rule(ATONoticeType.PAYMENT_CONFIRMATION)

        assert rule is None

    def test_calculate_due_date_uses_correspondence_date(self):
        rule = get_task_rule(ATONoticeType.AUDIT_NOTICE)
        correspondence_due = date.today() + timedelta(days=14)

        due_date = calculate_due_date(correspondence_due, rule)

        assert due_date == correspondence_due

    def test_calculate_due_date_uses_default(self):
        rule = get_task_rule(ATONoticeType.AUDIT_NOTICE)

        due_date = calculate_due_date(None, rule)

        assert due_date == date.today() + timedelta(days=28)

    def test_format_task_title(self):
        rule = get_task_rule(ATONoticeType.PENALTY_NOTICE)

        title = format_task_title(
            rule,
            client_name="Acme Corp",
            amount=1500.00,
        )

        assert title == "Review ATO penalty $1,500.00 - Acme Corp"
```

### Integration Test Example

```python
# backend/tests/integration/api/test_atotrack.py
import pytest
from httpx import AsyncClient


class TestATOtrackDashboard:
    @pytest.mark.asyncio
    async def test_get_dashboard(
        self,
        client: AsyncClient,
        auth_headers: dict,
        sample_correspondence: list,
    ):
        response = await client.get(
            "/api/v1/atotrack/dashboard",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert "summary" in data
        assert "requires_attention" in data
        assert "recent_resolved" in data

        assert isinstance(data["summary"]["overdue"], int)
        assert isinstance(data["summary"]["due_soon"], int)


class TestResolveCorrespondence:
    @pytest.mark.asyncio
    async def test_resolve_completes_task_and_insight(
        self,
        client: AsyncClient,
        auth_headers: dict,
        correspondence_with_task_and_insight: dict,
    ):
        correspondence_id = correspondence_with_task_and_insight["id"]

        response = await client.post(
            f"/api/v1/atotrack/correspondence/{correspondence_id}/resolve",
            headers=auth_headers,
            json={"resolution_notes": "Responded to ATO"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "resolved"
        assert data["task_completed"] is True
        assert data["insight_dismissed"] is True
        assert data["notifications_cancelled"] >= 0
```

---

## Performance Considerations

1. **Dashboard Caching**: Cache dashboard aggregation for 5 minutes per tenant
2. **Notification Batching**: Batch notification scheduling to reduce DB writes
3. **AI Rate Limiting**: Rate limit draft generation to 10/minute per tenant
4. **PM Sync Async**: All practice management sync runs via Celery, never blocking
5. **Pagination**: Always paginate correspondence list (max 100 per page)
