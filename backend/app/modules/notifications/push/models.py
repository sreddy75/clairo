"""PWA models for push subscriptions and WebAuthn credentials.

Spec: 032-pwa-mobile-document-capture
"""

from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class NotificationType(str, Enum):
    """Types of push notifications."""

    NEW_REQUEST = "new_request"
    URGENT_REQUEST = "urgent_request"
    REQUEST_REMINDER = "request_reminder"
    REQUEST_OVERDUE = "request_overdue"
    NEW_MESSAGE = "new_message"
    BAS_READY = "bas_ready"
    UPLOAD_COMPLETE = "upload_complete"


class PWAEventType(str, Enum):
    """Types of PWA installation events."""

    INSTALL_PROMPT_SHOWN = "install_prompt_shown"
    INSTALL_PROMPT_ACCEPTED = "install_prompt_accepted"
    INSTALL_PROMPT_DISMISSED = "install_prompt_dismissed"
    APP_INSTALLED = "app_installed"
    PUSH_PERMISSION_GRANTED = "push_permission_granted"
    PUSH_PERMISSION_DENIED = "push_permission_denied"
    BIOMETRIC_REGISTERED = "biometric_registered"


class PushSubscription(Base):
    """Web Push subscription for a client device.

    Stores the subscription data needed to send push notifications
    via the Web Push API (FCM for cross-platform delivery).
    """

    __tablename__ = "push_subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Web Push subscription data
    endpoint = Column(Text, nullable=False)
    p256dh_key = Column(String(255), nullable=False)  # Base64 encoded public key
    auth_key = Column(String(255), nullable=False)  # Base64 encoded auth secret

    # Device info
    user_agent = Column(Text, nullable=True)
    device_name = Column(String(255), nullable=True)  # e.g., "iPhone 14"

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    notification_logs = relationship(
        "PushNotificationLog",
        back_populates="subscription",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("endpoint", name="uq_push_subscriptions_endpoint"),
        Index("ix_push_subscriptions_tenant_client", "tenant_id", "client_id"),
    )

    def __repr__(self) -> str:
        return f"<PushSubscription {self.id} client={self.client_id}>"


class WebAuthnCredential(Base):
    """WebAuthn credential for biometric authentication.

    Stores passkey/biometric credentials (Face ID, Touch ID, fingerprint)
    for passwordless authentication in the PWA.
    """

    __tablename__ = "webauthn_credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # WebAuthn credential data
    credential_id = Column(LargeBinary, nullable=False, unique=True)
    public_key = Column(LargeBinary, nullable=False)
    sign_count = Column(Integer, default=0, nullable=False)

    # Credential metadata
    device_name = Column(String(255), nullable=True)  # e.g., "Face ID", "Touch ID"
    aaguid = Column(LargeBinary, nullable=True)  # Authenticator identifier

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_webauthn_credentials_credential_id", "credential_id"),
        Index("ix_webauthn_credentials_tenant_client", "tenant_id", "client_id"),
    )

    def __repr__(self) -> str:
        return f"<WebAuthnCredential {self.id} device={self.device_name}>"


class PushNotificationLog(Base):
    """Log of push notifications sent.

    Tracks delivery status and engagement metrics for push notifications.
    """

    __tablename__ = "push_notification_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    subscription_id = Column(
        UUID(as_uuid=True),
        ForeignKey("push_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Notification content
    notification_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    data = Column(JSONB, default=dict)  # Click action, deep link, etc.

    # Delivery tracking
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    clicked_at = Column(DateTime(timezone=True), nullable=True)

    # Error tracking
    fcm_message_id = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    subscription = relationship("PushSubscription", back_populates="notification_logs")

    __table_args__ = (
        Index("ix_push_notification_logs_sent_at", "sent_at"),
        Index("ix_push_notification_logs_type_sent", "notification_type", "sent_at"),
    )

    def __repr__(self) -> str:
        return f"<PushNotificationLog {self.id} type={self.notification_type}>"


class PWAInstallationEvent(Base):
    """PWA installation and permission events for analytics.

    Tracks PWA adoption metrics: installs, push permission grants, etc.
    """

    __tablename__ = "pwa_installation_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Event details
    event_type = Column(String(50), nullable=False)
    user_agent = Column(Text, nullable=True)
    platform = Column(String(50), nullable=True)  # ios, android, desktop

    # Additional event data (named event_metadata to avoid SQLAlchemy reserved 'metadata')
    event_metadata = Column("metadata", JSONB, default=dict)

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_pwa_events_tenant_type", "tenant_id", "event_type"),
        Index("ix_pwa_events_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<PWAInstallationEvent {self.id} type={self.event_type}>"
