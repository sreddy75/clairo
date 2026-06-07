"""Email templates for Clairo notifications.

Provides HTML and plain-text templates for all transactional emails.
Templates use a consistent, professional design that works across
email clients.
"""

from dataclasses import dataclass


@dataclass
class EmailTemplate:
    """Represents an email template with subject, HTML, and plain text."""

    subject: str
    html: str
    text: str


class EmailTemplates:
    """Email template generator for Clairo notifications."""

    # Brand colors and styles (Clairo coral primary)
    PRIMARY_COLOR = "#e85530"
    PRIMARY_DARK = "#ce3b16"
    TEXT_COLOR = "#1f2937"
    SECONDARY_TEXT = "#6b7280"
    BACKGROUND = "#faf9f7"
    WHITE = "#ffffff"

    # Company details for footer
    LOGO_URL = "https://www.clairo.com.au/logo-email.png?v=2"
    WEBSITE_URL = "https://www.clairo.com.au"
    SUPPORT_EMAIL = "support@clairo.com.au"
    COMPANY_NAME = "KR8IT Pty Ltd"
    COPYRIGHT_YEAR = "2026"

    @classmethod
    def _base_template(cls, content: str, footer_text: str = "") -> str:
        """Wrap content in the base email template."""
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Clairo</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: {cls.BACKGROUND};">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: {cls.BACKGROUND};">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="max-width: 600px; width: 100%;">
                    <!-- Header with Logo -->
                    <tr>
                        <td align="center" style="padding-bottom: 32px;">
                            <a href="{cls.WEBSITE_URL}" target="_blank" style="text-decoration: none;">
                                <img src="{cls.LOGO_URL}" alt="Clairo" width="96" height="96" style="display: block; border: 0; outline: none;">
                            </a>
                        </td>
                    </tr>
                    <!-- Content -->
                    <tr>
                        <td style="background-color: {cls.WHITE}; border-radius: 16px; padding: 40px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);">
                            {content}
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="padding-top: 32px; text-align: center;">
                            <p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; margin: 0 0 12px 0;">
                                {footer_text if footer_text else "See everything. Miss nothing."}
                            </p>
                            <p style="color: {cls.SECONDARY_TEXT}; font-size: 13px; margin: 0 0 8px 0;">
                                <a href="{cls.WEBSITE_URL}" style="color: {cls.PRIMARY_COLOR}; text-decoration: none;">www.clairo.com.au</a>
                                &nbsp;|&nbsp;
                                <a href="mailto:{cls.SUPPORT_EMAIL}" style="color: {cls.PRIMARY_COLOR}; text-decoration: none;">{cls.SUPPORT_EMAIL}</a>
                            </p>
                            <p style="color: {cls.SECONDARY_TEXT}; font-size: 12px; margin: 0 0 4px 0;">
                                &copy; {cls.COPYRIGHT_YEAR} Clairo. A product of {cls.COMPANY_NAME}.
                            </p>
                            <p style="color: #9ca3af; font-size: 11px; margin: 0;">
                                AI-Powered Tax &amp; Advisory Platform for Australian Accounting Practices
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

    @classmethod
    def _button(cls, text: str, url: str) -> str:
        """Generate a styled button."""
        return f"""
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin: 24px 0;">
    <tr>
        <td style="background-color: {cls.PRIMARY_COLOR}; border-radius: 8px;">
            <a href="{url}" target="_blank" style="display: inline-block; padding: 14px 28px; color: {cls.WHITE}; text-decoration: none; font-weight: 600; font-size: 16px;">
                {text}
            </a>
        </td>
    </tr>
</table>
"""

    @classmethod
    def welcome(cls, user_name: str, practice_name: str, dashboard_url: str) -> EmailTemplate:
        """Generate welcome email for new users."""
        subject = f"Welcome to Clairo, {user_name}!"

        content = f"""
<h1 style="color: {cls.TEXT_COLOR}; font-size: 24px; margin: 0 0 16px 0;">Welcome to Clairo!</h1>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Hi {user_name},
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Your practice <strong>{practice_name}</strong> is now set up on Clairo. You're ready to streamline your BAS lodgements and client management.
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 8px 0;">
    <strong>Here's what you can do next:</strong>
</p>
<ul style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.8; padding-left: 24px; margin: 0 0 16px 0;">
    <li>Connect your Xero or MYOB account</li>
    <li>Import your client list</li>
    <li>Invite team members to collaborate</li>
    <li>Start preparing BAS lodgements</li>
</ul>
{cls._button("Go to Dashboard", dashboard_url)}
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 16px 0 0 0;">
    If you have any questions, our support team is here to help.
</p>
"""

        text = f"""Welcome to Clairo!

Hi {user_name},

Your practice "{practice_name}" is now set up on Clairo. You're ready to streamline your BAS lodgements and client management.

Here's what you can do next:
- Connect your Xero or MYOB account
- Import your client list
- Invite team members to collaborate
- Start preparing BAS lodgements

Go to your dashboard: {dashboard_url}

If you have any questions, our support team is here to help.

---
Clairo - See everything. Miss nothing.
www.clairo.com.au | support@clairo.com.au
"""

        return EmailTemplate(
            subject=subject,
            html=cls._base_template(content),
            text=text,
        )

    @classmethod
    def team_invitation(
        cls,
        inviter_name: str,
        practice_name: str,
        invitee_email: str,
        invitation_url: str,
        role: str = "team member",
    ) -> EmailTemplate:
        """Generate team invitation email."""
        subject = f"{inviter_name} invited you to join {practice_name} on Clairo"

        content = f"""
<h1 style="color: {cls.TEXT_COLOR}; font-size: 24px; margin: 0 0 16px 0;">You're Invited!</h1>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Hi there,
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    <strong>{inviter_name}</strong> has invited you to join <strong>{practice_name}</strong> on Clairo as a {role}.
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Clairo helps accounting practices streamline their BAS lodgements, manage clients, and improve compliance workflows.
</p>
{cls._button("Accept Invitation", invitation_url)}
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 16px 0 0 0;">
    This invitation was sent to {invitee_email}. If you weren't expecting this email, you can safely ignore it.
</p>
"""

        text = f"""You're Invited!

Hi there,

{inviter_name} has invited you to join {practice_name} on Clairo as a {role}.

Clairo helps accounting practices streamline their BAS lodgements, manage clients, and improve compliance workflows.

Accept your invitation: {invitation_url}

This invitation was sent to {invitee_email}. If you weren't expecting this email, you can safely ignore it.

---
Clairo - See everything. Miss nothing.
www.clairo.com.au | support@clairo.com.au
"""

        return EmailTemplate(
            subject=subject,
            html=cls._base_template(content),
            text=text,
        )

    @classmethod
    def password_reset(
        cls, user_name: str, reset_url: str, expires_in: str = "1 hour"
    ) -> EmailTemplate:
        """Generate password reset email."""
        subject = "Reset your Clairo password"

        content = f"""
<h1 style="color: {cls.TEXT_COLOR}; font-size: 24px; margin: 0 0 16px 0;">Reset Your Password</h1>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Hi {user_name},
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    We received a request to reset your Clairo password. Click the button below to create a new password.
</p>
{cls._button("Reset Password", reset_url)}
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 16px 0 8px 0;">
    This link will expire in {expires_in}. If you didn't request a password reset, you can safely ignore this email.
</p>
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 0;">
    For security, this request was received from your account. If you didn't make this request, please contact our support team immediately.
</p>
"""

        text = f"""Reset Your Password

Hi {user_name},

We received a request to reset your Clairo password. Click the link below to create a new password:

{reset_url}

This link will expire in {expires_in}. If you didn't request a password reset, you can safely ignore this email.

For security, this request was received from your account. If you didn't make this request, please contact our support team immediately.

---
Clairo - See everything. Miss nothing.
www.clairo.com.au | support@clairo.com.au
"""

        return EmailTemplate(
            subject=subject,
            html=cls._base_template(content),
            text=text,
        )

    @classmethod
    def bas_reminder(
        cls,
        user_name: str,
        client_name: str,
        period: str,
        due_date: str,
        dashboard_url: str,
    ) -> EmailTemplate:
        """Generate BAS lodgement reminder email."""
        subject = f"BAS Reminder: {client_name} - {period} due {due_date}"

        content = f"""
<h1 style="color: {cls.TEXT_COLOR}; font-size: 24px; margin: 0 0 16px 0;">BAS Lodgement Reminder</h1>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Hi {user_name},
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    This is a reminder that the BAS for <strong>{client_name}</strong> for the period <strong>{period}</strong> is due on <strong>{due_date}</strong>.
</p>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="background-color: #fef3c7; border-radius: 8px; padding: 16px; margin: 16px 0; width: 100%;">
    <tr>
        <td style="color: #92400e; font-size: 14px;">
            <strong>Action Required:</strong> Please ensure the BAS is prepared and lodged before the due date to avoid penalties.
        </td>
    </tr>
</table>
{cls._button("View in Dashboard", dashboard_url)}
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 16px 0 0 0;">
    You can manage your notification preferences in your account settings.
</p>
"""

        text = f"""BAS Lodgement Reminder

Hi {user_name},

This is a reminder that the BAS for {client_name} for the period {period} is due on {due_date}.

Action Required: Please ensure the BAS is prepared and lodged before the due date to avoid penalties.

View in Dashboard: {dashboard_url}

You can manage your notification preferences in your account settings.

---
Clairo - See everything. Miss nothing.
www.clairo.com.au | support@clairo.com.au
"""

        return EmailTemplate(
            subject=subject,
            html=cls._base_template(content),
            text=text,
        )

    @classmethod
    def lodgement_confirmation(
        cls,
        user_name: str,
        client_name: str,
        period: str,
        lodgement_date: str,
        reference_number: str,
        dashboard_url: str,
        insights_section: str | None = None,
        insights_section_text: str | None = None,
    ) -> EmailTemplate:
        """Generate BAS lodgement confirmation email.

        Args:
            insights_section: Optional HTML block for "This Quarter in Numbers" (FR-021).
            insights_section_text: Matching plain-text block for the same section.
        """
        subject = f"BAS Lodged: {client_name} - {period}"

        insights_html = insights_section or ""
        content = f"""
<h1 style="color: {cls.TEXT_COLOR}; font-size: 24px; margin: 0 0 16px 0;">BAS Successfully Lodged</h1>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Hi {user_name},
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    The BAS for <strong>{client_name}</strong> for the period <strong>{period}</strong> has been successfully lodged.
</p>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="background-color: #d1fae5; border-radius: 8px; padding: 16px; margin: 16px 0; width: 100%;">
    <tr>
        <td>
            <p style="color: #065f46; font-size: 14px; margin: 0 0 8px 0;"><strong>Lodgement Details</strong></p>
            <p style="color: #065f46; font-size: 14px; margin: 0;">
                Reference: {reference_number}<br>
                Date: {lodgement_date}
            </p>
        </td>
    </tr>
</table>
{insights_html}
{cls._button("View Lodgement Details", dashboard_url)}
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 16px 0 0 0;">
    A copy of this lodgement has been saved to your records.
</p>
"""

        insights_text = f"\n{insights_section_text}\n" if insights_section_text else ""
        text = f"""BAS Successfully Lodged

Hi {user_name},

The BAS for {client_name} for the period {period} has been successfully lodged.

Lodgement Details:
- Reference: {reference_number}
- Date: {lodgement_date}
{insights_text}
View Lodgement Details: {dashboard_url}

A copy of this lodgement has been saved to your records.

---
Clairo - See everything. Miss nothing.
www.clairo.com.au | support@clairo.com.au
"""

        return EmailTemplate(
            subject=subject,
            html=cls._base_template(content),
            text=text,
        )

    @classmethod
    def usage_threshold_alert(
        cls,
        user_name: str,
        practice_name: str,
        percentage: int,
        client_count: int,
        client_limit: int,
        tier: str,
        upgrade_url: str,
    ) -> EmailTemplate:
        """Generate usage threshold alert email (80% or 90%)."""
        subject = f"You're at {percentage}% of your client limit - {practice_name}"

        # Different messaging for 80% vs 90%
        if percentage >= 90:
            urgency_message = (
                "You're almost at capacity and may not be able to add new clients soon."
            )
            urgency_color = "#dc2626"  # Red
            urgency_bg = "#fef2f2"  # Light red
        else:
            urgency_message = "Consider upgrading to ensure you have room to grow."
            urgency_color = "#d97706"  # Orange
            urgency_bg = "#fffbeb"  # Light orange

        content = f"""
<h1 style="color: {cls.TEXT_COLOR}; font-size: 24px; margin: 0 0 16px 0;">Approaching Your Client Limit</h1>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Hi {user_name},
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Your practice <strong>{practice_name}</strong> has reached <strong>{percentage}%</strong> of your client limit on the <strong>{tier.title()}</strong> plan.
</p>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="background-color: {urgency_bg}; border-radius: 8px; padding: 16px; margin: 16px 0; width: 100%;">
    <tr>
        <td>
            <p style="color: {urgency_color}; font-size: 14px; margin: 0 0 8px 0;"><strong>Current Usage</strong></p>
            <p style="color: {urgency_color}; font-size: 14px; margin: 0;">
                {client_count} of {client_limit} clients ({percentage}%)
            </p>
            <p style="color: {urgency_color}; font-size: 14px; margin: 8px 0 0 0;">
                {urgency_message}
            </p>
        </td>
    </tr>
</table>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Upgrade your plan to get more client capacity and unlock additional features.
</p>
{cls._button("Upgrade Now", upgrade_url)}
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 16px 0 0 0;">
    You can manage your subscription and billing in Settings &gt; Billing.
</p>
"""

        text = f"""Approaching Your Client Limit

Hi {user_name},

Your practice "{practice_name}" has reached {percentage}% of your client limit on the {tier.title()} plan.

Current Usage: {client_count} of {client_limit} clients ({percentage}%)

{urgency_message}

Upgrade your plan to get more client capacity and unlock additional features.

Upgrade now: {upgrade_url}

You can manage your subscription and billing in Settings > Billing.

---
Clairo - See everything. Miss nothing.
www.clairo.com.au | support@clairo.com.au
"""

        return EmailTemplate(
            subject=subject,
            html=cls._base_template(content),
            text=text,
        )

    @classmethod
    def usage_limit_reached(
        cls,
        user_name: str,
        practice_name: str,
        client_count: int,
        client_limit: int,
        tier: str,
        upgrade_url: str,
    ) -> EmailTemplate:
        """Generate usage limit reached email (100%)."""
        subject = f"You've reached your client limit - {practice_name}"

        content = f"""
<h1 style="color: {cls.TEXT_COLOR}; font-size: 24px; margin: 0 0 16px 0;">Client Limit Reached</h1>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Hi {user_name},
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Your practice <strong>{practice_name}</strong> has reached the client limit on the <strong>{tier.title()}</strong> plan.
</p>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="background-color: #fef2f2; border-radius: 8px; padding: 16px; margin: 16px 0; width: 100%;">
    <tr>
        <td>
            <p style="color: #dc2626; font-size: 14px; margin: 0 0 8px 0;"><strong>Limit Reached</strong></p>
            <p style="color: #dc2626; font-size: 14px; margin: 0;">
                {client_count} of {client_limit} clients (100%)
            </p>
            <p style="color: #dc2626; font-size: 14px; margin: 8px 0 0 0;">
                <strong>You cannot add new clients until you upgrade your plan.</strong>
            </p>
        </td>
    </tr>
</table>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 8px 0;">
    <strong>What this means:</strong>
</p>
<ul style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.8; padding-left: 24px; margin: 0 0 16px 0;">
    <li>Xero/MYOB sync will skip new clients</li>
    <li>Manual client creation is blocked</li>
    <li>Existing clients are unaffected</li>
</ul>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Upgrade now to continue growing your practice.
</p>
{cls._button("Upgrade Now", upgrade_url)}
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 16px 0 0 0;">
    Need help? Contact our support team for assistance with your upgrade.
</p>
"""

        text = f"""Client Limit Reached

Hi {user_name},

Your practice "{practice_name}" has reached the client limit on the {tier.title()} plan.

Limit Reached: {client_count} of {client_limit} clients (100%)

You cannot add new clients until you upgrade your plan.

What this means:
- Xero/MYOB sync will skip new clients
- Manual client creation is blocked
- Existing clients are unaffected

Upgrade now to continue growing your practice.

Upgrade now: {upgrade_url}

Need help? Contact our support team for assistance with your upgrade.

---
Clairo - See everything. Miss nothing.
www.clairo.com.au | support@clairo.com.au
"""

        return EmailTemplate(
            subject=subject,
            html=cls._base_template(content),
            text=text,
        )

    # =========================================================================
    # Trial Reminder Templates (Spec 021)
    # =========================================================================

    @classmethod
    def trial_reminder(
        cls,
        user_name: str,
        practice_name: str,
        days_remaining: int,
        tier: str,
        price_monthly: int,
        billing_date: str,
        billing_url: str,
    ) -> EmailTemplate:
        """Generate trial reminder email (3 days and 1 day before end).

        Spec 021: Onboarding Flow - Free Trial Experience
        """
        # Format price
        price_display = f"${price_monthly // 100}"

        # Urgency-based messaging
        if days_remaining <= 1:
            subject = f"Your Clairo trial ends tomorrow - {practice_name}"
            urgency_message = (
                "Your trial ends tomorrow. Your subscription will automatically start."
            )
            urgency_color = "#dc2626"  # Red
            urgency_bg = "#fef2f2"  # Light red
        else:
            subject = f"Your Clairo trial ends in {days_remaining} days - {practice_name}"
            urgency_message = f"Your free trial ends in {days_remaining} days."
            urgency_color = "#d97706"  # Orange
            urgency_bg = "#fffbeb"  # Light orange

        content = f"""
<h1 style="color: {cls.TEXT_COLOR}; font-size: 24px; margin: 0 0 16px 0;">Your Trial is Ending Soon</h1>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Hi {user_name},
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    {urgency_message}
</p>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="background-color: {urgency_bg}; border-radius: 8px; padding: 16px; margin: 16px 0; width: 100%;">
    <tr>
        <td>
            <p style="color: {urgency_color}; font-size: 14px; margin: 0 0 8px 0;"><strong>What Happens Next</strong></p>
            <p style="color: {urgency_color}; font-size: 14px; margin: 0;">
                Plan: {tier.title()}<br>
                Price: {price_display}/month<br>
                First billing date: {billing_date}
            </p>
        </td>
    </tr>
</table>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 8px 0;">
    <strong>No action required:</strong> Your subscription will automatically continue with the {tier.title()} plan you selected.
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    If you'd like to change your plan or update your billing details, you can do so in your account settings.
</p>
{cls._button("Manage Billing", billing_url)}
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 16px 0 0 0;">
    Questions? Contact our support team - we're here to help.
</p>
"""

        text = f"""Your Trial is Ending Soon

Hi {user_name},

{urgency_message}

What Happens Next:
- Plan: {tier.title()}
- Price: {price_display}/month
- First billing date: {billing_date}

No action required: Your subscription will automatically continue with the {tier.title()} plan you selected.

If you'd like to change your plan or update your billing details, you can do so in your account settings.

Manage Billing: {billing_url}

Questions? Contact our support team - we're here to help.

---
Clairo - See everything. Miss nothing.
www.clairo.com.au | support@clairo.com.au
"""

        return EmailTemplate(
            subject=subject,
            html=cls._base_template(content),
            text=text,
        )

    @classmethod
    def trial_converted(
        cls,
        user_name: str,
        practice_name: str,
        tier: str,
        price_monthly: int,
        next_billing_date: str,
        dashboard_url: str,
    ) -> EmailTemplate:
        """Generate trial conversion success email.

        Sent when first payment after trial is successful.
        Spec 021: Onboarding Flow - Free Trial Experience
        """
        price_display = f"${price_monthly // 100}"
        subject = f"Welcome to Clairo {tier.title()} - {practice_name}"

        content = f"""
<h1 style="color: {cls.TEXT_COLOR}; font-size: 24px; margin: 0 0 16px 0;">You're All Set!</h1>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Hi {user_name},
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Great news! Your {tier.title()} subscription for <strong>{practice_name}</strong> is now active.
</p>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="background-color: #d1fae5; border-radius: 8px; padding: 16px; margin: 16px 0; width: 100%;">
    <tr>
        <td>
            <p style="color: #065f46; font-size: 14px; margin: 0 0 8px 0;"><strong>Subscription Details</strong></p>
            <p style="color: #065f46; font-size: 14px; margin: 0;">
                Plan: {tier.title()}<br>
                Price: {price_display}/month<br>
                Next billing date: {next_billing_date}
            </p>
        </td>
    </tr>
</table>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Thank you for choosing Clairo! We're excited to help you streamline your BAS management.
</p>
{cls._button("Go to Dashboard", dashboard_url)}
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 16px 0 0 0;">
    You can manage your subscription anytime in Settings &gt; Billing.
</p>
"""

        text = f"""You're All Set!

Hi {user_name},

Great news! Your {tier.title()} subscription for "{practice_name}" is now active.

Subscription Details:
- Plan: {tier.title()}
- Price: {price_display}/month
- Next billing date: {next_billing_date}

Thank you for choosing Clairo! We're excited to help you streamline your BAS management.

Go to Dashboard: {dashboard_url}

You can manage your subscription anytime in Settings > Billing.

---
Clairo - See everything. Miss nothing.
www.clairo.com.au | support@clairo.com.au
"""

        return EmailTemplate(
            subject=subject,
            html=cls._base_template(content),
            text=text,
        )

    @classmethod
    def payment_failed(
        cls,
        user_name: str,
        practice_name: str,
        tier: str,
        grace_period_days: int,
        update_payment_url: str,
    ) -> EmailTemplate:
        """Generate payment failed email with grace period notice.

        Spec 021: Onboarding Flow - Free Trial Experience
        """
        subject = f"Action required: Payment failed - {practice_name}"

        content = f"""
<h1 style="color: {cls.TEXT_COLOR}; font-size: 24px; margin: 0 0 16px 0;">Payment Failed</h1>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Hi {user_name},
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    We couldn't process your payment for <strong>{practice_name}</strong>'s {tier.title()} subscription.
</p>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="background-color: #fef2f2; border-radius: 8px; padding: 16px; margin: 16px 0; width: 100%;">
    <tr>
        <td>
            <p style="color: #dc2626; font-size: 14px; margin: 0 0 8px 0;"><strong>Grace Period</strong></p>
            <p style="color: #dc2626; font-size: 14px; margin: 0;">
                You have <strong>{grace_period_days} days</strong> to update your payment method before your account is suspended.
            </p>
        </td>
    </tr>
</table>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Please update your payment method to continue using Clairo without interruption.
</p>
{cls._button("Update Payment Method", update_payment_url)}
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 16px 0 0 0;">
    If you're having trouble, our support team is here to help.
</p>
"""

        text = f"""Payment Failed

Hi {user_name},

We couldn't process your payment for "{practice_name}"'s {tier.title()} subscription.

Grace Period: You have {grace_period_days} days to update your payment method before your account is suspended.

Please update your payment method to continue using Clairo without interruption.

Update Payment Method: {update_payment_url}

If you're having trouble, our support team is here to help.

---
Clairo - See everything. Miss nothing.
www.clairo.com.au | support@clairo.com.au
"""

        return EmailTemplate(
            subject=subject,
            html=cls._base_template(content),
            text=text,
        )

    # =========================================================================
    # Onboarding Nudge Templates (Spec 021)
    # =========================================================================

    @classmethod
    def connect_xero_nudge(
        cls,
        user_name: str,
        practice_name: str,
        connect_url: str,
    ) -> EmailTemplate:
        """Generate Xero connection nudge email (sent 24h after signup if not connected).

        Spec 021: Onboarding Flow - Email Drip Sequence
        """
        subject = f"Connect Xero to unlock Clairo's full potential - {practice_name}"

        content = f"""
<h1 style="color: {cls.TEXT_COLOR}; font-size: 24px; margin: 0 0 16px 0;">Connect Xero to Get Started</h1>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Hi {user_name},
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    We noticed you haven't connected your Xero account yet. Connecting Xero unlocks the full power of Clairo:
</p>
<ul style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.8; padding-left: 24px; margin: 0 0 16px 0;">
    <li><strong>Auto-import clients</strong> - No manual data entry</li>
    <li><strong>Real-time data sync</strong> - Always up-to-date financials</li>
    <li><strong>AI-powered insights</strong> - Smart BAS recommendations</li>
    <li><strong>Data quality scoring</strong> - Catch issues before the ATO does</li>
</ul>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    It only takes 2 minutes to connect.
</p>
{cls._button("Connect Xero Now", connect_url)}
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 16px 0 0 0;">
    Need help? Our support team is ready to walk you through the setup.
</p>
"""

        text = f"""Connect Xero to Get Started

Hi {user_name},

We noticed you haven't connected your Xero account yet. Connecting Xero unlocks the full power of Clairo:

- Auto-import clients - No manual data entry
- Real-time data sync - Always up-to-date financials
- AI-powered insights - Smart BAS recommendations
- Data quality scoring - Catch issues before the ATO does

It only takes 2 minutes to connect.

Connect Xero Now: {connect_url}

Need help? Our support team is ready to walk you through the setup.

---
Clairo - See everything. Miss nothing.
www.clairo.com.au | support@clairo.com.au
"""

        return EmailTemplate(
            subject=subject,
            html=cls._base_template(content),
            text=text,
        )

    @classmethod
    def import_clients_nudge(
        cls,
        user_name: str,
        practice_name: str,
        import_url: str,
    ) -> EmailTemplate:
        """Generate client import nudge email (sent 48h after signup if no clients).

        Spec 021: Onboarding Flow - Email Drip Sequence
        """
        subject = f"Import your clients to start managing BAS - {practice_name}"

        content = f"""
<h1 style="color: {cls.TEXT_COLOR}; font-size: 24px; margin: 0 0 16px 0;">Import Your Clients</h1>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Hi {user_name},
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    You're almost ready to start streamlining your BAS workflow! Import your first client to see Clairo in action.
</p>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="background-color: #eff6ff; border-radius: 8px; padding: 16px; margin: 16px 0; width: 100%;">
    <tr>
        <td style="color: #1e40af; font-size: 14px;">
            <strong>Tip:</strong> You can bulk import all your clients at once from Xero Practice Manager or Xero.
        </td>
    </tr>
</table>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Once your clients are imported, you'll be able to:
</p>
<ul style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.8; padding-left: 24px; margin: 0 0 16px 0;">
    <li>View all clients in one dashboard</li>
    <li>Track BAS due dates automatically</li>
    <li>Get data quality scores for each client</li>
    <li>Receive AI-powered insights and recommendations</li>
</ul>
{cls._button("Import Clients", import_url)}
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 16px 0 0 0;">
    Questions about importing? We're here to help.
</p>
"""

        text = f"""Import Your Clients

Hi {user_name},

You're almost ready to start streamlining your BAS workflow! Import your first client to see Clairo in action.

Tip: You can bulk import all your clients at once from Xero Practice Manager or Xero.

Once your clients are imported, you'll be able to:
- View all clients in one dashboard
- Track BAS due dates automatically
- Get data quality scores for each client
- Receive AI-powered insights and recommendations

Import Clients: {import_url}

Questions about importing? We're here to help.

---
Clairo - See everything. Miss nothing.
www.clairo.com.au | support@clairo.com.au
"""

        return EmailTemplate(
            subject=subject,
            html=cls._base_template(content),
            text=text,
        )

    @classmethod
    def onboarding_complete(
        cls,
        user_name: str,
        practice_name: str,
        client_count: int,
        dashboard_url: str,
    ) -> EmailTemplate:
        """Generate onboarding complete congratulations email.

        Spec 021: Onboarding Flow - Email Drip Sequence
        """
        subject = f"You're all set up! Welcome to Clairo - {practice_name}"

        content = f"""
<h1 style="color: {cls.TEXT_COLOR}; font-size: 24px; margin: 0 0 16px 0;">Setup Complete!</h1>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Hi {user_name},
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Congratulations! <strong>{practice_name}</strong> is now fully set up on Clairo with <strong>{client_count} client{"" if client_count == 1 else "s"}</strong> imported.
</p>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="background-color: #d1fae5; border-radius: 8px; padding: 16px; margin: 16px 0; width: 100%;">
    <tr>
        <td style="color: #065f46; font-size: 14px; text-align: center;">
            <span style="font-size: 32px;">&#127881;</span><br>
            <strong>You're ready to streamline your BAS workflow!</strong>
        </td>
    </tr>
</table>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 8px 0;">
    <strong>What's next?</strong>
</p>
<ul style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.8; padding-left: 24px; margin: 0 0 16px 0;">
    <li>Review your clients' data quality scores</li>
    <li>Check upcoming BAS due dates</li>
    <li>Explore AI-powered insights for each client</li>
    <li>Start preparing your first BAS lodgement</li>
</ul>
{cls._button("Go to Dashboard", dashboard_url)}
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 16px 0 0 0;">
    Thank you for choosing Clairo. We're excited to help you save time and reduce errors in your BAS preparation.
</p>
"""

        text = f"""Setup Complete!

Hi {user_name},

Congratulations! "{practice_name}" is now fully set up on Clairo with {client_count} client{"s" if client_count != 1 else ""} imported.

You're ready to streamline your BAS workflow!

What's next?
- Review your clients' data quality scores
- Check upcoming BAS due dates
- Explore AI-powered insights for each client
- Start preparing your first BAS lodgement

Go to Dashboard: {dashboard_url}

Thank you for choosing Clairo. We're excited to help you save time and reduce errors in your BAS preparation.

---
Clairo - See everything. Miss nothing.
www.clairo.com.au | support@clairo.com.au
"""

        return EmailTemplate(
            subject=subject,
            html=cls._base_template(content),
            text=text,
        )
