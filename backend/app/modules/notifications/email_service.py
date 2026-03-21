"""Email service using Resend for transactional emails.

Provides a high-level interface for sending emails through Resend's API.
Handles templating, error handling, and logging.
"""

from functools import lru_cache
from typing import Any

import resend
import structlog

from app.config import get_settings
from app.modules.notifications.templates import EmailTemplate, EmailTemplates

logger = structlog.get_logger(__name__)


class EmailServiceError(Exception):
    """Base exception for email service errors."""

    pass


class EmailDeliveryError(EmailServiceError):
    """Raised when email delivery fails."""

    def __init__(self, message: str, email_id: str | None = None):
        super().__init__(message)
        self.email_id = email_id


class EmailService:
    """Service for sending transactional emails via Resend.

    This service provides methods for sending various types of emails
    including welcome emails, invitations, password resets, and
    BAS-related notifications.

    Attributes:
        templates: Email template generator.
        from_email: Default sender email address.
        enabled: Whether email sending is enabled.
    """

    def __init__(self) -> None:
        """Initialize the email service with Resend configuration."""
        settings = get_settings()
        self.templates = EmailTemplates
        self.from_email = settings.resend.from_email
        self.reply_to = settings.resend.reply_to
        self.enabled = settings.resend.enabled

        # Configure Resend SDK
        resend.api_key = settings.resend.api_key.get_secret_value()

        logger.info(
            "Email service initialized",
            enabled=self.enabled,
            from_email=self.from_email,
        )

    async def send_email(
        self,
        to: str | list[str],
        template: EmailTemplate,
        tags: list[dict[str, str]] | None = None,
    ) -> str | None:
        """Send an email using the provided template.

        Args:
            to: Recipient email address(es).
            template: Email template with subject, HTML, and text content.
            tags: Optional Resend tags for tracking.

        Returns:
            Email ID if sent successfully, None if disabled.

        Raises:
            EmailDeliveryError: If email delivery fails.
        """
        if not self.enabled:
            logger.info(
                "Email sending disabled, skipping",
                to=to,
                subject=template.subject,
            )
            return None

        recipients = [to] if isinstance(to, str) else to

        try:
            params: dict[str, Any] = {
                "from": self.from_email,
                "to": recipients,
                "subject": template.subject,
                "html": template.html,
                "text": template.text,
            }

            if self.reply_to:
                params["reply_to"] = self.reply_to

            if tags:
                params["tags"] = tags

            response = resend.Emails.send(params)
            email_id = response.get("id") if isinstance(response, dict) else None

            logger.info(
                "Email sent successfully",
                email_id=email_id,
                to=recipients,
                subject=template.subject,
            )

            return email_id

        except Exception as e:
            logger.error(
                "Failed to send email",
                error=str(e),
                to=recipients,
                subject=template.subject,
            )
            raise EmailDeliveryError(f"Failed to send email: {e}") from e

    async def send_welcome_email(
        self,
        to: str,
        user_name: str,
        practice_name: str,
        dashboard_url: str = "https://app.clairo.com.au/dashboard",
    ) -> str | None:
        """Send welcome email to a new user.

        Args:
            to: Recipient email address.
            user_name: User's display name.
            practice_name: Name of the practice they created.
            dashboard_url: URL to their dashboard.

        Returns:
            Email ID if sent successfully.
        """
        template = self.templates.welcome(
            user_name=user_name,
            practice_name=practice_name,
            dashboard_url=dashboard_url,
        )

        return await self.send_email(
            to=to,
            template=template,
            tags=[
                {"name": "category", "value": "welcome"},
                {"name": "type", "value": "onboarding"},
            ],
        )

    async def send_team_invitation(
        self,
        to: str,
        inviter_name: str,
        practice_name: str,
        invitation_url: str,
        role: str = "team member",
    ) -> str | None:
        """Send team invitation email.

        Args:
            to: Invitee's email address.
            inviter_name: Name of the person sending the invitation.
            practice_name: Name of the practice.
            invitation_url: URL to accept the invitation.
            role: Role being offered (e.g., "accountant", "admin").

        Returns:
            Email ID if sent successfully.
        """
        template = self.templates.team_invitation(
            inviter_name=inviter_name,
            practice_name=practice_name,
            invitee_email=to,
            invitation_url=invitation_url,
            role=role,
        )

        return await self.send_email(
            to=to,
            template=template,
            tags=[
                {"name": "category", "value": "invitation"},
                {"name": "type", "value": "team"},
            ],
        )

    async def send_password_reset(
        self,
        to: str,
        user_name: str,
        reset_url: str,
        expires_in: str = "1 hour",
    ) -> str | None:
        """Send password reset email.

        Args:
            to: User's email address.
            user_name: User's display name.
            reset_url: URL to reset password.
            expires_in: Human-readable expiration time.

        Returns:
            Email ID if sent successfully.
        """
        template = self.templates.password_reset(
            user_name=user_name,
            reset_url=reset_url,
            expires_in=expires_in,
        )

        return await self.send_email(
            to=to,
            template=template,
            tags=[
                {"name": "category", "value": "security"},
                {"name": "type", "value": "password_reset"},
            ],
        )

    async def send_bas_reminder(
        self,
        to: str,
        user_name: str,
        client_name: str,
        period: str,
        due_date: str,
        dashboard_url: str,
    ) -> str | None:
        """Send BAS lodgement reminder email.

        Args:
            to: User's email address.
            user_name: User's display name.
            client_name: Client's name.
            period: BAS period (e.g., "Q2 2024").
            due_date: Due date for the lodgement.
            dashboard_url: URL to view the BAS in dashboard.

        Returns:
            Email ID if sent successfully.
        """
        template = self.templates.bas_reminder(
            user_name=user_name,
            client_name=client_name,
            period=period,
            due_date=due_date,
            dashboard_url=dashboard_url,
        )

        return await self.send_email(
            to=to,
            template=template,
            tags=[
                {"name": "category", "value": "reminder"},
                {"name": "type", "value": "bas"},
            ],
        )

    async def send_lodgement_confirmation(
        self,
        to: str,
        user_name: str,
        client_name: str,
        period: str,
        lodgement_date: str,
        reference_number: str,
        dashboard_url: str,
    ) -> str | None:
        """Send BAS lodgement confirmation email.

        Args:
            to: User's email address.
            user_name: User's display name.
            client_name: Client's name.
            period: BAS period (e.g., "Q2 2024").
            lodgement_date: Date the BAS was lodged.
            reference_number: ATO reference number.
            dashboard_url: URL to view the lodgement details.

        Returns:
            Email ID if sent successfully.
        """
        template = self.templates.lodgement_confirmation(
            user_name=user_name,
            client_name=client_name,
            period=period,
            lodgement_date=lodgement_date,
            reference_number=reference_number,
            dashboard_url=dashboard_url,
        )

        return await self.send_email(
            to=to,
            template=template,
            tags=[
                {"name": "category", "value": "confirmation"},
                {"name": "type", "value": "lodgement"},
            ],
        )

    async def send_usage_threshold_alert(
        self,
        to: str,
        user_name: str,
        practice_name: str,
        percentage: int,
        client_count: int,
        client_limit: int,
        tier: str,
        upgrade_url: str = "https://app.clairo.com.au/settings/billing",
    ) -> str | None:
        """Send usage threshold alert email (80% or 90%).

        Args:
            to: User's email address.
            user_name: User's display name.
            practice_name: Name of the practice.
            percentage: Current usage percentage (80 or 90).
            client_count: Current number of clients.
            client_limit: Maximum clients allowed on tier.
            tier: Current subscription tier.
            upgrade_url: URL to upgrade subscription.

        Returns:
            Email ID if sent successfully.
        """
        template = self.templates.usage_threshold_alert(
            user_name=user_name,
            practice_name=practice_name,
            percentage=percentage,
            client_count=client_count,
            client_limit=client_limit,
            tier=tier,
            upgrade_url=upgrade_url,
        )

        return await self.send_email(
            to=to,
            template=template,
            tags=[
                {"name": "category", "value": "usage"},
                {"name": "type", "value": "threshold_alert"},
                {"name": "threshold", "value": str(percentage)},
            ],
        )

    async def send_usage_limit_reached(
        self,
        to: str,
        user_name: str,
        practice_name: str,
        client_count: int,
        client_limit: int,
        tier: str,
        upgrade_url: str = "https://app.clairo.com.au/settings/billing",
    ) -> str | None:
        """Send usage limit reached email (100%).

        Args:
            to: User's email address.
            user_name: User's display name.
            practice_name: Name of the practice.
            client_count: Current number of clients.
            client_limit: Maximum clients allowed on tier.
            tier: Current subscription tier.
            upgrade_url: URL to upgrade subscription.

        Returns:
            Email ID if sent successfully.
        """
        template = self.templates.usage_limit_reached(
            user_name=user_name,
            practice_name=practice_name,
            client_count=client_count,
            client_limit=client_limit,
            tier=tier,
            upgrade_url=upgrade_url,
        )

        return await self.send_email(
            to=to,
            template=template,
            tags=[
                {"name": "category", "value": "usage"},
                {"name": "type", "value": "limit_reached"},
            ],
        )


@lru_cache
def get_email_service() -> EmailService:
    """Get a cached instance of the email service.

    Returns:
        EmailService: The singleton email service instance.
    """
    return EmailService()
