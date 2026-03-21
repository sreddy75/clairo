"""Audit logging infrastructure for compliance and security.

This module provides:
- AuditLog SQLAlchemy model for immutable audit entries
- AuditService for creating audit log entries
- @audited decorator for automatic audit logging
- Checksum generation for integrity chain

Audit logs are append-only with database-level rules preventing
updates and deletes. Each entry includes a checksum that links
to the previous entry, creating a tamper-evident chain.

Usage:
    # Using AuditService directly
    audit_service = AuditService(session)
    await audit_service.log_event(
        event_type="user.created",
        actor_id=user_id,
        resource_type="user",
        resource_id=new_user.id,
        action="create",
        outcome="success",
    )

    # Using the @audited decorator
    @audited("user.role.changed", resource_type="user")
    async def update_role(self, user_id: UUID, new_role: str) -> User:
        ...
"""

import contextlib
import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from sqlalchemy import DateTime, String, func, select
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.tenant_context import TenantContext
from app.database import Base

P = ParamSpec("P")
R = TypeVar("R")


class AuditLog(Base):
    """Immutable audit log entry.

    Stores all authentication, authorization, and data modification events
    for compliance and security purposes. This table is append-only with
    database-level rules preventing updates and deletes.

    The checksum chain provides tamper detection - each entry includes
    a SHA-256 hash of its contents plus the previous entry's checksum.

    Attributes:
        id: Unique identifier (UUID).
        event_id: Idempotency key for deduplication.
        occurred_at: When the event happened.
        actor_type: Type of actor (user, system, api_key).
        actor_id: ID of the actor (if applicable).
        actor_email: Email of the actor (masked for privacy).
        actor_ip: IP address of the actor (masked to /24).
        tenant_id: Tenant context for the event.
        request_id: Correlation ID for request tracing.
        event_category: Category (auth, data, compliance).
        event_type: Specific event type.
        resource_type: Type of resource affected.
        resource_id: ID of the resource affected.
        action: Action performed (create, read, update, delete).
        outcome: Result (success, failure).
        old_values: Previous state (for updates).
        new_values: New state (for creates/updates).
        metadata: Additional context.
        checksum: SHA-256 hash for integrity verification.
        previous_checksum: Link to previous entry (chain).

    Database Rules:
        - UPDATE and DELETE are blocked via PostgreSQL rules
        - Checksum chain provides tamper detection
    """

    __tablename__ = "audit_logs"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Idempotency
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid.uuid4,
        comment="Idempotency key for deduplication",
    )

    # Timestamp
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
        comment="When the event occurred",
    )

    # Actor information
    actor_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of actor: user, system, api_key",
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID of the actor",
    )
    actor_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Email of the actor (masked for privacy)",
    )
    actor_ip: Mapped[str | None] = mapped_column(
        INET,
        nullable=True,
        comment="IP address (masked to /24)",
    )

    # Context
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Tenant context",
    )
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Request correlation ID",
    )

    # Event classification
    event_category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Category: auth, data, compliance, integration",
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Specific event type",
    )
    resource_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Type of resource affected",
    )
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID of the resource affected",
    )

    # Action and outcome
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Action: create, read, update, delete, login, etc.",
    )
    outcome: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Result: success, failure",
    )

    # Data capture
    old_values: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Previous state for updates",
    )
    new_values: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="New state for creates/updates",
    )
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",  # Keep column name as "metadata" in DB
        JSONB,
        nullable=True,
        comment="Additional context",
    )

    # Integrity chain
    checksum: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hash for integrity",
    )
    previous_checksum: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Link to previous entry",
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<AuditLog(id={self.id}, event_type={self.event_type}, outcome={self.outcome})>"


def generate_checksum(
    event_id: uuid.UUID,
    occurred_at: datetime,
    event_type: str,
    actor_id: uuid.UUID | None,
    tenant_id: uuid.UUID,
    resource_id: uuid.UUID | None,
    action: str,
    outcome: str,
    previous_checksum: str | None,
) -> str:
    """Generate SHA-256 checksum for audit log entry.

    Creates a hash of the key audit log fields plus the previous
    entry's checksum to form an integrity chain.

    Args:
        event_id: Unique event identifier.
        occurred_at: Event timestamp.
        event_type: Type of event.
        actor_id: ID of the actor.
        tenant_id: Tenant context.
        resource_id: ID of affected resource.
        action: Action performed.
        outcome: Result of action.
        previous_checksum: Checksum of previous entry.

    Returns:
        64-character hexadecimal SHA-256 hash.
    """
    data = {
        "event_id": str(event_id),
        "occurred_at": occurred_at.isoformat(),
        "event_type": event_type,
        "actor_id": str(actor_id) if actor_id else None,
        "tenant_id": str(tenant_id),
        "resource_id": str(resource_id) if resource_id else None,
        "action": action,
        "outcome": outcome,
        "previous_checksum": previous_checksum,
    }
    content = json.dumps(data, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()


def mask_ip(ip: str | None) -> str | None:
    """Mask IP address to /24 subnet for privacy.

    Args:
        ip: Full IP address.

    Returns:
        IP address with last octet set to 0, or None if input is None.
    """
    if ip is None:
        return None

    parts = ip.split(".")
    if len(parts) == 4:
        # IPv4: mask last octet
        parts[3] = "0"
        return ".".join(parts)

    # IPv6 or other: return as-is for now
    return ip


def mask_email(email: str | None) -> str | None:
    """Mask email address for privacy.

    Keeps first 2 characters and domain visible.

    Args:
        email: Full email address.

    Returns:
        Masked email or None if input is None.
    """
    if email is None:
        return None

    parts = email.split("@")
    if len(parts) != 2:
        return "***"

    username = parts[0]
    domain = parts[1]

    if len(username) <= 2:
        masked_username = "*" * len(username)
    else:
        masked_username = username[:2] + "*" * (len(username) - 2)

    return f"{masked_username}@{domain}"


class AuditService:
    """Service for creating audit log entries.

    Provides a high-level interface for logging audit events with
    automatic context capture and checksum generation.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the audit service.

        Args:
            session: Async database session for audit log storage.
        """
        self.session = session

    async def _get_previous_checksum(self, tenant_id: uuid.UUID) -> str | None:
        """Get the checksum of the most recent audit log for the tenant.

        Args:
            tenant_id: Tenant to get previous checksum for.

        Returns:
            Previous checksum or None if no previous entries.
        """
        result = await self.session.execute(
            select(AuditLog.checksum)
            .where(AuditLog.tenant_id == tenant_id)
            .order_by(AuditLog.occurred_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row

    async def log_event(
        self,
        event_type: str,
        event_category: str = "auth",
        actor_type: str = "user",
        actor_id: uuid.UUID | None = None,
        actor_email: str | None = None,
        actor_ip: str | None = None,
        tenant_id: uuid.UUID | None = None,
        request_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: uuid.UUID | None = None,
        action: str = "access",
        outcome: str = "success",
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Create an audit log entry.

        Args:
            event_type: Type of event (e.g., "user.created").
            event_category: Category (auth, data, compliance).
            actor_type: Type of actor (user, system, api_key).
            actor_id: ID of the actor.
            actor_email: Email of the actor (will be masked).
            actor_ip: IP address of the actor (will be masked).
            tenant_id: Tenant context (defaults to current context).
            request_id: Request correlation ID.
            resource_type: Type of resource affected.
            resource_id: ID of resource affected.
            action: Action performed.
            outcome: Result of action.
            old_values: Previous state for updates.
            new_values: New state for creates/updates.
            metadata: Additional context.

        Returns:
            The created AuditLog entry.

        Raises:
            RuntimeError: If no tenant context is available.
        """
        # Get tenant ID from context if not provided
        if tenant_id is None:
            tenant_id = TenantContext.get_current_tenant_id()

        if tenant_id is None:
            raise RuntimeError("Tenant ID is required for audit logging")

        # Get request ID from context if not provided
        if request_id is None:
            request_id = TenantContext.get_current_request_id()

        # Generate event ID
        event_id = uuid.uuid4()
        occurred_at = datetime.now(UTC)

        # Get previous checksum for chain
        previous_checksum = await self._get_previous_checksum(tenant_id)

        # Generate checksum
        checksum = generate_checksum(
            event_id=event_id,
            occurred_at=occurred_at,
            event_type=event_type,
            actor_id=actor_id,
            tenant_id=tenant_id,
            resource_id=resource_id,
            action=action,
            outcome=outcome,
            previous_checksum=previous_checksum,
        )

        # Create audit log entry
        audit_log = AuditLog(
            id=uuid.uuid4(),
            event_id=event_id,
            occurred_at=occurred_at,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_email=mask_email(actor_email),
            actor_ip=mask_ip(actor_ip),
            tenant_id=tenant_id,
            request_id=request_id,
            event_category=event_category,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            outcome=outcome,
            old_values=old_values,
            new_values=new_values,
            event_metadata=metadata,  # Uses event_metadata attribute, maps to "metadata" column
            checksum=checksum,
            previous_checksum=previous_checksum,
        )

        self.session.add(audit_log)
        await self.session.flush()

        return audit_log


def audited(
    event_type: str,
    event_category: str = "auth",
    resource_type: str | None = None,
    action: str = "access",
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator for automatic audit logging.

    Wraps an async method to automatically create an audit log entry
    after the method completes (success or failure).

    The decorated method's class must have a `session` attribute for
    database access and optionally `actor_id` and `actor_email` for
    actor information.

    Usage:
        class UserService:
            def __init__(self, session: AsyncSession, actor_id: UUID):
                self.session = session
                self.actor_id = actor_id

            @audited("user.role.changed", resource_type="user", action="update")
            async def update_role(self, user_id: UUID, new_role: str) -> User:
                ...

    Args:
        event_type: Type of event to log.
        event_category: Category of event.
        resource_type: Type of resource being modified.
        action: Action being performed.

    Returns:
        Decorated function that logs audit events.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Get self (first argument should be the service instance)
            self = args[0] if args else None

            if self is None or not hasattr(self, "session"):
                raise RuntimeError("@audited requires a class with 'session' attribute")

            # Extract actor info from self if available
            actor_id = getattr(self, "actor_id", None)
            actor_email = getattr(self, "actor_email", None)

            outcome = "success"
            result = None
            error_message = None

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                outcome = "failure"
                error_message = str(e)
                raise
            finally:
                # Create audit service and log event
                audit_service = AuditService(self.session)

                # Try to extract resource_id from result or kwargs
                resource_id = None
                if result is not None and hasattr(result, "id"):
                    resource_id = result.id
                elif "user_id" in kwargs:
                    resource_id = kwargs["user_id"]

                # Build metadata
                audit_metadata = None
                if error_message:
                    audit_metadata = {"error": error_message}

                with contextlib.suppress(Exception):
                    # Don't let audit logging failure break the main operation
                    # In production, this should be logged/monitored
                    await audit_service.log_event(
                        event_type=event_type,
                        event_category=event_category,
                        actor_type="user",
                        actor_id=actor_id,
                        actor_email=actor_email,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        action=action,
                        outcome=outcome,
                        metadata=audit_metadata,
                    )

        return wrapper  # type: ignore

    return decorator
