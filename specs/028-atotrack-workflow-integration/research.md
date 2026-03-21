# Research: ATOtrack Workflow Integration

**Feature**: 028-atotrack-workflow-integration
**Date**: 2026-01-01
**Status**: Complete

---

## Research Tasks

### 1. Task Creation Rules

**Decision**: Rule-based task creation per notice type

**Task Rules Configuration**:

```python
from dataclasses import dataclass
from enum import Enum

@dataclass
class TaskRule:
    title_template: str
    default_days: int  # Days until due if no date in notice
    priority: str  # high, medium, low
    auto_create: bool  # Auto-create or require confirmation
    category: str  # For grouping in task list

TASK_RULES = {
    ATONoticeType.AUDIT_NOTICE: TaskRule(
        title_template="Respond to ATO audit - {client_name}",
        default_days=28,
        priority="high",
        auto_create=True,
        category="compliance",
    ),
    ATONoticeType.AUDIT_OUTCOME: TaskRule(
        title_template="Review ATO audit outcome - {client_name}",
        default_days=14,
        priority="high",
        auto_create=True,
        category="compliance",
    ),
    ATONoticeType.PENALTY_NOTICE: TaskRule(
        title_template="Review ATO penalty ${amount:.2f} - {client_name}",
        default_days=21,
        priority="high",
        auto_create=True,
        category="debt",
    ),
    ATONoticeType.DEBT_NOTICE: TaskRule(
        title_template="Address ATO debt ${amount:.2f} - {client_name}",
        default_days=14,
        priority="high",
        auto_create=True,
        category="debt",
    ),
    ATONoticeType.ACTIVITY_STATEMENT_REMINDER: TaskRule(
        title_template="Lodge Activity Statement - {client_name}",
        default_days=14,
        priority="medium",
        auto_create=True,
        category="lodgement",
    ),
    ATONoticeType.TAX_RETURN_REMINDER: TaskRule(
        title_template="Lodge Tax Return - {client_name}",
        default_days=28,
        priority="medium",
        auto_create=True,
        category="lodgement",
    ),
    ATONoticeType.INFORMATION_REQUEST: TaskRule(
        title_template="Respond to ATO information request - {client_name}",
        default_days=28,
        priority="high",
        auto_create=True,
        category="compliance",
    ),
    ATONoticeType.PAYMENT_REMINDER: TaskRule(
        title_template="Process ATO payment - {client_name}",
        default_days=7,
        priority="medium",
        auto_create=True,
        category="payment",
    ),
    # Lower priority - confirmations don't need tasks
    ATONoticeType.ACTIVITY_STATEMENT_CONFIRMATION: TaskRule(
        title_template="Review lodgement confirmation - {client_name}",
        default_days=0,  # No deadline
        priority="low",
        auto_create=False,  # Don't auto-create
        category="confirmation",
    ),
    ATONoticeType.RUNNING_BALANCE_ACCOUNT: TaskRule(
        title_template="Review running balance - {client_name}",
        default_days=0,
        priority="low",
        auto_create=False,
        category="information",
    ),
}
```

**Due Date Calculation**:

```python
def calculate_due_date(
    notice_type: ATONoticeType,
    parsed_due_date: date | None,
    received_at: datetime,
) -> date | None:
    """Calculate task due date from notice or default."""
    rule = TASK_RULES.get(notice_type)

    if not rule or not rule.auto_create:
        return None

    # Use parsed due date if available
    if parsed_due_date:
        return parsed_due_date

    # Fall back to default days from rule
    if rule.default_days > 0:
        return received_at.date() + timedelta(days=rule.default_days)

    return None
```

**Rationale**: Pre-configured rules ensure consistent task creation. Default deadlines prevent items from falling through cracks.

---

### 2. Insight Generation Rules

**Decision**: Generate insights for high-priority notice types only

**Insight Severity Mapping**:

```python
from enum import Enum

class InsightSeverity(str, Enum):
    CRITICAL = "critical"  # Immediate action required
    HIGH = "high"          # Action required soon
    MEDIUM = "medium"      # Should address
    LOW = "low"            # Informational

INSIGHT_RULES = {
    ATONoticeType.AUDIT_NOTICE: {
        "generate": True,
        "severity": InsightSeverity.CRITICAL,
        "title_template": "ATO Audit Notice - Response Required",
        "description_template": "The ATO has issued an audit notice for {client_name}. Response due by {due_date}.",
    },
    ATONoticeType.PENALTY_NOTICE: {
        "generate": True,
        "severity": InsightSeverity.HIGH,
        "title_template": "ATO Penalty: ${amount:.2f}",
        "description_template": "A penalty of ${amount:.2f} has been applied to {client_name}'s account. Consider requesting remission.",
    },
    ATONoticeType.DEBT_NOTICE: {
        "generate": True,
        "severity": InsightSeverity.HIGH,
        "title_template": "ATO Debt: ${amount:.2f}",
        "description_template": "{client_name} has an outstanding ATO debt of ${amount:.2f}. Payment or arrangement required.",
    },
    ATONoticeType.ACTIVITY_STATEMENT_REMINDER: {
        "generate": True,
        "severity": InsightSeverity.MEDIUM,
        "title_template": "Activity Statement Due",
        "description_template": "Activity Statement for {client_name} is due on {due_date}.",
    },
    # Don't generate insights for confirmations, running balance, etc.
    ATONoticeType.ACTIVITY_STATEMENT_CONFIRMATION: {
        "generate": False,
    },
    ATONoticeType.RUNNING_BALANCE_ACCOUNT: {
        "generate": False,
    },
}
```

**Amount-Based Severity Adjustment**:

```python
def adjust_severity_by_amount(
    base_severity: InsightSeverity,
    amount: Decimal | None,
) -> InsightSeverity:
    """Escalate severity for large amounts."""
    if not amount:
        return base_severity

    if amount >= 10000:
        return InsightSeverity.CRITICAL
    elif amount >= 5000 and base_severity == InsightSeverity.MEDIUM:
        return InsightSeverity.HIGH

    return base_severity
```

**Rationale**: Not all notices need insights. High-priority items surface in portfolio view; confirmations don't clutter the dashboard.

---

### 3. Notification Schedule

**Decision**: Tiered notification schedule based on urgency

**Notification Triggers**:

```python
from dataclasses import dataclass

@dataclass
class NotificationTrigger:
    days_before: int
    channel: list[str]  # ["email", "push"]
    template: str
    priority: str  # high, medium, low

NOTIFICATION_SCHEDULE = [
    NotificationTrigger(
        days_before=7,
        channel=["email"],
        template="atotrack_reminder_7_days",
        priority="medium",
    ),
    NotificationTrigger(
        days_before=3,
        channel=["email", "push"],
        template="atotrack_reminder_3_days",
        priority="high",
    ),
    NotificationTrigger(
        days_before=1,
        channel=["email", "push"],
        template="atotrack_reminder_1_day",
        priority="high",
    ),
    NotificationTrigger(
        days_before=0,  # Overdue
        channel=["email", "push"],
        template="atotrack_overdue",
        priority="high",
    ),
]
```

**Notification Templates**:

```python
NOTIFICATION_TEMPLATES = {
    "atotrack_reminder_7_days": {
        "subject": "ATO matter due in 7 days: {title}",
        "body": """
Hi {user_name},

This is a reminder that the following ATO matter is due in 7 days:

Client: {client_name}
Notice: {notice_type}
Due Date: {due_date}

{action_url}

Best regards,
Clairo
""",
    },
    "atotrack_reminder_3_days": {
        "subject": "URGENT: ATO matter due in 3 days - {title}",
        "body": """...""",
    },
    "atotrack_overdue": {
        "subject": "OVERDUE: ATO matter past due date - {title}",
        "body": """...""",
    },
}
```

**Notification Aggregation**:

```python
async def aggregate_notifications(
    user_id: UUID,
    notifications: list[PendingNotification],
) -> list[Notification]:
    """Aggregate multiple notifications into digest."""
    # If more than 5 notifications pending, send digest instead
    if len(notifications) > 5:
        return [create_digest_notification(notifications)]

    return [create_individual_notification(n) for n in notifications]
```

**Rationale**: Tiered schedule ensures timely reminders without spam. Aggregation prevents notification fatigue.

---

### 4. AI Response Drafting

**Decision**: Claude with RAG from ATO knowledge base

**Response Types**:

```python
class ResponseType(str, Enum):
    AUDIT_RESPONSE = "audit_response"
    REMISSION_REQUEST = "remission_request"
    PAYMENT_PLAN_REQUEST = "payment_plan_request"
    INFORMATION_RESPONSE = "information_response"
    GENERAL_RESPONSE = "general_response"
```

**Drafting Prompt**:

```python
RESPONSE_PROMPTS = {
    ResponseType.AUDIT_RESPONSE: """
You are a professional accountant drafting a response to an ATO audit notice.

<notice>
{notice_content}
</notice>

<client_context>
Client: {client_name}
ABN: {client_abn}
Industry: {client_industry}
</client_context>

<relevant_guidance>
{rag_context}
</relevant_guidance>

Draft a professional response that:
1. Acknowledges the audit notice
2. Confirms the client's cooperation
3. Outlines the information/documents being provided
4. Requests any necessary clarifications
5. Provides a timeline for full response

Keep the tone professional and cooperative. The accountant will review and edit before sending.
""",
    ResponseType.REMISSION_REQUEST: """
You are a professional accountant drafting a penalty remission request to the ATO.

<penalty_notice>
{notice_content}
Penalty Amount: ${amount}
Reference: {reference_number}
</penalty_notice>

<client_context>
Client: {client_name}
ABN: {client_abn}
Compliance History: {compliance_history}
</client_context>

<relevant_guidance>
{rag_context}
</relevant_guidance>

Draft a remission request that:
1. Acknowledges the penalty
2. Explains the circumstances that led to the issue
3. Outlines steps taken to prevent recurrence
4. Highlights the client's otherwise good compliance history
5. Requests full or partial remission

Focus on genuine circumstances. Do not make false claims.
""",
}
```

**RAG Integration**:

```python
async def get_rag_context(
    response_type: ResponseType,
    notice_type: ATONoticeType,
) -> str:
    """Retrieve relevant ATO guidance from knowledge base."""
    # Search Qdrant for relevant guidance
    query = f"{response_type.value} {notice_type.value} ATO guidelines"

    results = await knowledge_service.search(
        collection="ato_guidance",
        query=query,
        limit=3,
    )

    return "\n\n".join([r.content for r in results])
```

**Rationale**: Claude with RAG produces professional drafts grounded in ATO guidance. Human review is always required.

---

### 5. Practice Management Integration

**Decision**: Optional async sync to Karbon and XPM

**Karbon API Integration**:

```python
from httpx import AsyncClient

class KarbonClient:
    """Karbon practice management API client."""

    BASE_URL = "https://api.karbonhq.com/v3"

    def __init__(self, access_token: str):
        self.access_token = access_token

    async def create_task(
        self,
        title: str,
        due_date: date,
        assignee_email: str,
        client_key: str | None,
        notes: str,
    ) -> dict:
        """Create a task in Karbon."""
        async with AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/Tasks",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "Title": title,
                    "DueDate": due_date.isoformat(),
                    "AssigneeEmailAddress": assignee_email,
                    "ClientKey": client_key,
                    "Notes": notes,
                    "Status": "NotStarted",
                },
            )
            response.raise_for_status()
            return response.json()

    async def complete_task(self, task_key: str) -> None:
        """Mark a Karbon task as complete."""
        async with AsyncClient() as client:
            response = await client.patch(
                f"{self.BASE_URL}/Tasks/{task_key}",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json={"Status": "Completed"},
            )
            response.raise_for_status()
```

**XPM API Integration**:

```python
class XPMClient:
    """Xero Practice Manager API client."""

    BASE_URL = "https://api.xero.com/practicemanager/3.0"

    def __init__(self, access_token: str):
        self.access_token = access_token

    async def create_job(
        self,
        name: str,
        client_id: str,
        due_date: date,
        manager_id: str,
        description: str,
    ) -> dict:
        """Create a job in XPM."""
        async with AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/Jobs",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "Name": name,
                    "ClientID": client_id,
                    "DueDate": due_date.isoformat(),
                    "ManagerID": manager_id,
                    "Description": description,
                    "State": "Planned",
                },
            )
            response.raise_for_status()
            return response.json()
```

**Sync Strategy**:

```python
async def sync_to_practice_management(
    correspondence: ATOCorrespondence,
    task: Task,
    tenant: Tenant,
):
    """Sync task to connected practice management systems."""
    # Check tenant integrations
    integrations = await get_tenant_integrations(tenant.id)

    for integration in integrations:
        try:
            if integration.type == "karbon":
                await sync_to_karbon(correspondence, task, integration)
            elif integration.type == "xpm":
                await sync_to_xpm(correspondence, task, integration)
        except Exception as e:
            # Log error but don't fail - async retry later
            logger.error(f"PM sync failed: {e}")
            await queue_retry(correspondence.id, integration.id)
```

**Rationale**: Async sync prevents PM issues from blocking core workflow. Retry mechanism handles transient failures.

---

### 6. Dashboard Aggregation

**Decision**: Pre-computed summaries with real-time updates

**Dashboard Query**:

```python
async def get_dashboard_data(tenant_id: UUID) -> DashboardData:
    """Get ATOtrack dashboard data."""

    # Summary counts
    counts = await db.execute(
        select(
            func.count().filter(
                ATOCorrespondence.due_date < date.today(),
                ATOCorrespondence.status != CorrespondenceStatus.RESOLVED,
            ).label("overdue"),
            func.count().filter(
                ATOCorrespondence.due_date.between(
                    date.today(),
                    date.today() + timedelta(days=7)
                ),
                ATOCorrespondence.status != CorrespondenceStatus.RESOLVED,
            ).label("due_soon"),
            func.count().filter(
                ATOCorrespondence.status == CorrespondenceStatus.RESOLVED,
            ).label("handled"),
            func.count().filter(
                ATOCorrespondence.client_id.is_(None),
                ATOCorrespondence.status != CorrespondenceStatus.IGNORED,
            ).label("triage"),
        )
        .where(ATOCorrespondence.tenant_id == tenant_id)
    )

    # Requires attention (top 10 urgent items)
    requires_attention = await db.execute(
        select(ATOCorrespondence)
        .where(
            ATOCorrespondence.tenant_id == tenant_id,
            ATOCorrespondence.status.in_([
                CorrespondenceStatus.NEW,
                CorrespondenceStatus.REVIEWED,
            ]),
        )
        .order_by(
            # Overdue first
            case(
                (ATOCorrespondence.due_date < date.today(), 0),
                else_=1
            ),
            # Then by due date
            ATOCorrespondence.due_date.asc().nullslast(),
            # Then by severity
            ATOCorrespondence.notice_type,
        )
        .limit(10)
    )

    return DashboardData(
        summary=counts,
        requires_attention=requires_attention.scalars().all(),
    )
```

**Caching Strategy**:

```python
from functools import lru_cache
import redis

DASHBOARD_CACHE_TTL = 60  # 1 minute

async def get_cached_dashboard(tenant_id: UUID) -> DashboardData:
    """Get dashboard with caching."""
    cache_key = f"atotrack:dashboard:{tenant_id}"

    # Try cache first
    cached = await redis.get(cache_key)
    if cached:
        return DashboardData.model_validate_json(cached)

    # Compute and cache
    data = await get_dashboard_data(tenant_id)
    await redis.setex(cache_key, DASHBOARD_CACHE_TTL, data.model_dump_json())

    return data

async def invalidate_dashboard_cache(tenant_id: UUID):
    """Invalidate dashboard cache on changes."""
    cache_key = f"atotrack:dashboard:{tenant_id}"
    await redis.delete(cache_key)
```

**Rationale**: Aggregated queries are efficient for dashboard. Short TTL cache provides fast loads while staying current.

---

## Summary of Decisions

| Area | Decision |
|------|----------|
| Task Creation | Rule-based per notice type with defaults |
| Insight Generation | High-priority notices only, severity by type |
| Notifications | Tiered schedule: 7, 3, 1, 0 days |
| Response Drafting | Claude + RAG from ATO knowledge base |
| PM Integration | Optional async sync to Karbon/XPM |
| Dashboard | Aggregated queries with 1-minute cache |

---

## Sources

- [Karbon API Documentation](https://developers.karbonhq.com/)
- [Xero Practice Manager API](https://developer.xero.com/documentation/api/practicemanager/overview)
- [ATO Remission Guidelines](https://www.ato.gov.au/General/Interest-and-penalties/Penalties/)
- [ATO Audit Process](https://www.ato.gov.au/General/The-fight-against-tax-crime/Our-compliance-approach/)
