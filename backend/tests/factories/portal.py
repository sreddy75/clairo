"""Test factories for Client Portal models.

Provides factory_boy factories for:
- PortalInvitationFactory
- PortalSessionFactory
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import factory

from app.modules.portal.auth.magic_link import hash_token
from app.modules.portal.enums import InvitationStatus
from app.modules.portal.models import PortalInvitation, PortalSession


class PortalInvitationFactory(factory.Factory):
    """Factory for PortalInvitation model."""

    class Meta:
        model = PortalInvitation

    id = factory.LazyFunction(uuid4)
    tenant_id = factory.LazyFunction(uuid4)
    connection_id = factory.LazyFunction(uuid4)
    email = factory.Faker("email")
    token_hash = factory.LazyFunction(lambda: hash_token(f"token-{uuid4().hex}"))
    status = InvitationStatus.PENDING.value
    expires_at = factory.LazyFunction(lambda: datetime.now(timezone.utc) + timedelta(hours=24))
    invited_by = factory.LazyFunction(uuid4)


class SentInvitationFactory(PortalInvitationFactory):
    """Factory for a sent invitation."""

    status = InvitationStatus.SENT.value
    sent_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    email_delivered = True


class AcceptedInvitationFactory(PortalInvitationFactory):
    """Factory for an accepted invitation."""

    status = InvitationStatus.ACCEPTED.value
    sent_at = factory.LazyFunction(lambda: datetime.now(timezone.utc) - timedelta(hours=1))
    accepted_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    email_delivered = True


class ExpiredInvitationFactory(PortalInvitationFactory):
    """Factory for an expired invitation."""

    status = InvitationStatus.EXPIRED.value
    expires_at = factory.LazyFunction(lambda: datetime.now(timezone.utc) - timedelta(hours=1))


class PortalSessionFactory(factory.Factory):
    """Factory for PortalSession model."""

    class Meta:
        model = PortalSession

    id = factory.LazyFunction(uuid4)
    connection_id = factory.LazyFunction(uuid4)
    tenant_id = factory.LazyFunction(uuid4)
    refresh_token_hash = factory.LazyFunction(lambda: hash_token(f"refresh-{uuid4().hex}"))
    device_fingerprint = factory.LazyFunction(lambda: f"fp-{uuid4().hex[:8]}")
    user_agent = "Mozilla/5.0 (Test Client)"
    ip_address = "192.168.1.100"
    expires_at = factory.LazyFunction(lambda: datetime.now(timezone.utc) + timedelta(days=30))
    revoked = False
    last_active_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))


class RevokedSessionFactory(PortalSessionFactory):
    """Factory for a revoked session."""

    revoked = True
    revoked_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    revoke_reason = "Session revoked by accountant"


class ExpiredSessionFactory(PortalSessionFactory):
    """Factory for an expired session."""

    expires_at = factory.LazyFunction(lambda: datetime.now(timezone.utc) - timedelta(days=1))
