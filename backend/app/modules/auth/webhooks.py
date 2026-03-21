"""Clerk webhook handlers.

This module handles Clerk webhook events for:
- user.created: Sync user metadata
- user.updated: Sync user metadata changes (including MFA status)
- user.deleted: Deactivate user
- session.created: Log login event
- session.ended: Log logout event

All webhooks are verified using Clerk's webhook signing secret (Svix).

Usage:
    from app.modules.auth.webhooks import ClerkWebhookHandler, verify_webhook_signature

    # In the webhook endpoint
    if not verify_webhook_signature(body, headers, secret):
        raise HTTPException(401, "Invalid signature")

    handler = ClerkWebhookHandler(session=db_session)
    await handler.handle_event(event)
"""

import hashlib
import hmac
import time
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditService
from app.core.logging import get_logger

from .repository import PracticeUserRepository, UserRepository

logger = get_logger(__name__)


# Tolerance window for timestamp validation (5 minutes)
TIMESTAMP_TOLERANCE_SECONDS = 300


class WebhookEvent(BaseModel):
    """Pydantic model for Clerk webhook event.

    Attributes:
        type: Event type (e.g., "user.created", "session.created").
        data: Event payload data.
        object: Object type (always "event").
    """

    type: str = Field(..., description="Event type")
    data: dict[str, Any] = Field(default_factory=dict, description="Event data")
    object: str = Field(default="event", description="Object type")


def verify_webhook_signature(
    body: str,
    headers: dict[str, str],
    secret: str,
    tolerance_seconds: int = TIMESTAMP_TOLERANCE_SECONDS,
) -> bool:
    """Verify Clerk webhook signature using Svix format.

    Clerk uses Svix for webhook delivery which includes:
    - svix-id: Unique message ID
    - svix-timestamp: Unix timestamp
    - svix-signature: HMAC signature

    Args:
        body: Raw request body as string.
        headers: Request headers (case-insensitive dict).
        secret: Webhook signing secret.
        tolerance_seconds: Maximum age of webhook in seconds.

    Returns:
        True if signature is valid, False otherwise.
    """
    try:
        # Get required headers (handle case-insensitivity)
        svix_id = headers.get("svix-id") or headers.get("Svix-Id")
        svix_timestamp = headers.get("svix-timestamp") or headers.get("Svix-Timestamp")
        svix_signature = headers.get("svix-signature") or headers.get("Svix-Signature")

        if not svix_id or not svix_timestamp or not svix_signature:
            logger.warning("Missing required Svix headers")
            return False

        # Validate timestamp is within tolerance
        try:
            timestamp = int(svix_timestamp)
            current_time = int(time.time())

            if abs(current_time - timestamp) > tolerance_seconds:
                logger.warning(
                    "Webhook timestamp out of tolerance",
                    timestamp=timestamp,
                    current_time=current_time,
                    tolerance=tolerance_seconds,
                )
                return False
        except ValueError:
            logger.warning("Invalid timestamp format", timestamp=svix_timestamp)
            return False

        # Build the signed payload
        to_sign = f"{svix_timestamp}.{body}"

        # Extract the expected signature
        # Format: "v1,signature1 v1,signature2" (space-separated, multiple signatures)
        signatures = svix_signature.split(" ")

        for sig in signatures:
            if not sig.startswith("v1,"):
                continue

            expected_sig = sig[3:]  # Remove "v1," prefix

            # Compute HMAC
            computed_sig = hmac.new(
                secret.encode(),
                to_sign.encode(),
                hashlib.sha256,
            ).hexdigest()

            # Constant-time comparison
            if hmac.compare_digest(computed_sig, expected_sig):
                return True

        logger.warning("No matching signature found")
        return False

    except Exception as e:
        logger.error("Signature verification error", error=str(e))
        return False


class ClerkWebhookHandler:
    """Handler for Clerk webhook events.

    Processes webhook events and performs appropriate actions:
    - User lifecycle: create, update, delete
    - Session lifecycle: login, logout

    Attributes:
        session: Async database session.
        practice_user_repo: Practice user repository.
        user_repo: Base user repository.
        audit_service: Audit logging service.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the webhook handler.

        Args:
            session: Async database session.
        """
        self.session = session
        self.practice_user_repo = PracticeUserRepository(session)
        self.user_repo = UserRepository(session)
        self.audit_service = AuditService(session)

    async def handle_event(self, event: WebhookEvent) -> dict[str, Any]:
        """Route webhook event to appropriate handler.

        Args:
            event: Parsed webhook event.

        Returns:
            Result dict with status and any relevant data.
        """
        handlers = {
            "user.created": self.handle_user_created,
            "user.updated": self.handle_user_updated,
            "user.deleted": self.handle_user_deleted,
            "session.created": self.handle_session_created,
            "session.ended": self.handle_session_ended,
            "session.revoked": self.handle_session_ended,  # Treat revoked like ended
        }

        handler = handlers.get(event.type)

        if handler is None:
            logger.info("Unhandled webhook event type", event_type=event.type)
            return {"status": "ignored", "reason": f"Unhandled event type: {event.type}"}

        try:
            result = await handler(event)
            logger.info(
                "Webhook event processed",
                event_type=event.type,
                result=result,
            )
            return {"status": "success", "result": result}

        except Exception as e:
            logger.error(
                "Webhook handler error",
                event_type=event.type,
                error=str(e),
            )
            return {"status": "error", "error": str(e)}

    async def handle_user_created(self, event: WebhookEvent) -> dict[str, Any]:
        """Handle user.created webhook event.

        This event is triggered when a new user signs up in Clerk.
        We log the event but don't create the user yet - that happens
        during registration when they provide a tenant name or invitation.

        Args:
            event: Webhook event with user data.

        Returns:
            Result dict.
        """
        user_data = event.data
        clerk_id = user_data.get("id")
        email_addresses = user_data.get("email_addresses", [])
        email = email_addresses[0]["email_address"] if email_addresses else None

        logger.info(
            "User created in Clerk",
            clerk_id=clerk_id,
            email=email,
        )

        # We don't create the user here - registration is handled separately
        # Just log that we received the event

        return {
            "action": "logged",
            "clerk_id": clerk_id,
            "email": email,
            "note": "User will be created during registration",
        }

    async def handle_user_updated(self, event: WebhookEvent) -> dict[str, Any]:
        """Handle user.updated webhook event.

        Syncs user metadata from Clerk, including:
        - MFA status changes
        - Profile updates

        Args:
            event: Webhook event with updated user data.

        Returns:
            Result dict.
        """
        user_data = event.data
        clerk_id = user_data.get("id")

        if not clerk_id:
            return {"action": "skipped", "reason": "No clerk_id in event"}

        # Find the practice user
        practice_user = await self.practice_user_repo.get_by_clerk_id(clerk_id)

        if practice_user is None:
            logger.debug(
                "User not found for update webhook",
                clerk_id=clerk_id,
            )
            return {"action": "skipped", "reason": "User not registered yet"}

        # Check for MFA status change
        mfa_enabled = user_data.get("two_factor_enabled", False)
        old_mfa_status = practice_user.mfa_enabled

        updates: dict[str, Any] = {}

        if mfa_enabled != old_mfa_status:
            updates["mfa_enabled"] = mfa_enabled

            # Log MFA change event
            event_type = "auth.mfa.enabled" if mfa_enabled else "auth.mfa.disabled"
            await self.audit_service.log_event(
                event_type=event_type,
                event_category="auth",
                actor_type="user",
                actor_id=practice_user.user_id,
                tenant_id=practice_user.tenant_id,
                resource_type="user",
                resource_id=practice_user.user_id,
                action="update",
                outcome="success",
                old_values={"mfa_enabled": old_mfa_status},
                new_values={"mfa_enabled": mfa_enabled},
            )

            logger.info(
                "User MFA status updated",
                clerk_id=clerk_id,
                old_mfa_status=old_mfa_status,
                new_mfa_status=mfa_enabled,
            )

        # Apply updates if any
        if updates:
            await self.practice_user_repo.update(practice_user.id, **updates)

        return {
            "action": "updated" if updates else "no_changes",
            "clerk_id": clerk_id,
            "updates": updates,
        }

    async def handle_user_deleted(self, event: WebhookEvent) -> dict[str, Any]:
        """Handle user.deleted webhook event.

        Deactivates the user in our system when they're deleted from Clerk.

        Args:
            event: Webhook event with deleted user data.

        Returns:
            Result dict.
        """
        user_data = event.data
        clerk_id = user_data.get("id")

        if not clerk_id:
            return {"action": "skipped", "reason": "No clerk_id in event"}

        # Find the practice user
        practice_user = await self.practice_user_repo.get_by_clerk_id(
            clerk_id,
            load_relations=True,
        )

        if practice_user is None:
            logger.debug(
                "User not found for delete webhook",
                clerk_id=clerk_id,
            )
            return {"action": "skipped", "reason": "User not found"}

        # Deactivate the base user
        if practice_user.user.is_active:
            await self.user_repo.update(
                practice_user.user_id,
                is_active=False,
            )

            # Log deactivation event
            await self.audit_service.log_event(
                event_type="user.deactivated",
                event_category="auth",
                actor_type="system",
                tenant_id=practice_user.tenant_id,
                resource_type="user",
                resource_id=practice_user.user_id,
                action="deactivate",
                outcome="success",
                metadata={
                    "reason": "Deleted from Clerk",
                    "source": "webhook",
                },
            )

            logger.info(
                "User deactivated via webhook",
                clerk_id=clerk_id,
                user_id=str(practice_user.user_id),
            )

            return {
                "action": "deactivated",
                "clerk_id": clerk_id,
                "user_id": str(practice_user.user_id),
            }

        return {
            "action": "already_inactive",
            "clerk_id": clerk_id,
        }

    async def handle_session_created(self, event: WebhookEvent) -> dict[str, Any]:
        """Handle session.created webhook event.

        Logs a login event when a new session is created in Clerk.

        Args:
            event: Webhook event with session data.

        Returns:
            Result dict.
        """
        session_data = event.data
        session_id = session_data.get("id")
        clerk_user_id = session_data.get("user_id")

        if not clerk_user_id:
            return {"action": "skipped", "reason": "No user_id in session"}

        # Find the practice user
        practice_user = await self.practice_user_repo.get_by_clerk_id(clerk_user_id)

        if practice_user is None:
            logger.debug(
                "User not found for session webhook",
                clerk_id=clerk_user_id,
            )
            return {"action": "skipped", "reason": "User not registered yet"}

        # Update last login timestamp
        await self.practice_user_repo.update_last_login(practice_user.id)

        # Log login event
        await self.audit_service.log_event(
            event_type="auth.login.success",
            event_category="auth",
            actor_type="user",
            actor_id=practice_user.user_id,
            tenant_id=practice_user.tenant_id,
            resource_type="session",
            resource_id=None,  # Session ID is from Clerk
            action="login",
            outcome="success",
            metadata={
                "clerk_session_id": session_id,
                "source": "webhook",
            },
        )

        logger.info(
            "Login event logged via webhook",
            clerk_id=clerk_user_id,
            session_id=session_id,
        )

        return {
            "action": "login_logged",
            "clerk_id": clerk_user_id,
            "session_id": session_id,
        }

    async def handle_session_ended(self, event: WebhookEvent) -> dict[str, Any]:
        """Handle session.ended/session.revoked webhook event.

        Logs a logout event when a session ends in Clerk.

        Args:
            event: Webhook event with session data.

        Returns:
            Result dict.
        """
        session_data = event.data
        session_id = session_data.get("id")
        clerk_user_id = session_data.get("user_id")

        if not clerk_user_id:
            return {"action": "skipped", "reason": "No user_id in session"}

        # Find the practice user
        practice_user = await self.practice_user_repo.get_by_clerk_id(clerk_user_id)

        if practice_user is None:
            logger.debug(
                "User not found for session end webhook",
                clerk_id=clerk_user_id,
            )
            return {"action": "skipped", "reason": "User not found"}

        # Log logout event
        await self.audit_service.log_event(
            event_type="auth.logout",
            event_category="auth",
            actor_type="user",
            actor_id=practice_user.user_id,
            tenant_id=practice_user.tenant_id,
            resource_type="session",
            resource_id=None,
            action="logout",
            outcome="success",
            metadata={
                "clerk_session_id": session_id,
                "source": "webhook",
                "event_type": event.type,  # session.ended or session.revoked
            },
        )

        logger.info(
            "Logout event logged via webhook",
            clerk_id=clerk_user_id,
            session_id=session_id,
            event_type=event.type,
        )

        return {
            "action": "logout_logged",
            "clerk_id": clerk_user_id,
            "session_id": session_id,
        }
