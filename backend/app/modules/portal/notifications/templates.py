"""Email templates for Client Portal notifications.

Provides HTML and plain-text templates for portal emails including:
- Portal invitations
- Document requests
- Reminders (3-day, 1-day, due today, overdue)
- Response notifications

Spec: 030-client-portal-document-requests
"""

from dataclasses import dataclass


@dataclass
class EmailTemplate:
    """Represents an email template with subject, HTML, and plain text."""

    subject: str
    html: str
    text: str


class PortalEmailTemplates:
    """Email template generator for Client Portal notifications."""

    # Brand colors and styles (Clairo coral primary)
    PRIMARY_COLOR = "#e85530"
    PRIMARY_DARK = "#ce3b16"
    TEXT_COLOR = "#1f2937"
    SECONDARY_TEXT = "#6b7280"
    BACKGROUND = "#faf9f7"
    WHITE = "#ffffff"
    WARNING_BG = "#fffbeb"
    WARNING_TEXT = "#d97706"
    DANGER_BG = "#fef2f2"
    DANGER_TEXT = "#dc2626"
    SUCCESS_BG = "#d1fae5"
    SUCCESS_TEXT = "#065f46"

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

    # =========================================================================
    # Portal Invitation Templates (T093)
    # =========================================================================

    @classmethod
    def portal_invitation(
        cls,
        business_name: str,
        practice_name: str,
        inviter_name: str,
        portal_url: str,
        expires_in: str = "7 days",
        message: str | None = None,
    ) -> EmailTemplate:
        """Generate portal invitation email for business owners.

        Sent when an accountant invites a client to access their portal.
        """
        subject = f"{practice_name} has invited you to access your documents"

        message_section = ""
        if message:
            message_section = f"""
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="background-color: #eff6ff; border-radius: 8px; padding: 16px; margin: 16px 0; width: 100%;">
    <tr>
        <td style="color: #1e40af; font-size: 14px;">
            <strong>Message from {inviter_name}:</strong><br>
            {message}
        </td>
    </tr>
</table>
"""

        content = f"""
<h1 style="color: {cls.TEXT_COLOR}; font-size: 24px; margin: 0 0 16px 0;">You've Been Invited!</h1>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Hi there,
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    <strong>{inviter_name}</strong> from <strong>{practice_name}</strong> has invited you to access your secure document portal for <strong>{business_name}</strong>.
</p>
{message_section}
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 8px 0;">
    <strong>What you can do in your portal:</strong>
</p>
<ul style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.8; padding-left: 24px; margin: 0 0 16px 0;">
    <li>View and respond to document requests</li>
    <li>Securely upload documents to your accountant</li>
    <li>Track request status and due dates</li>
</ul>
{cls._button("Access Your Portal", portal_url)}
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 16px 0 0 0;">
    This link will expire in {expires_in}. If the link expires, contact {practice_name} to request a new invitation.
</p>
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 8px 0 0 0;">
    <strong>Security tip:</strong> If you weren't expecting this email, you can safely ignore it.
</p>
"""

        text = f"""You've Been Invited!

Hi there,

{inviter_name} from {practice_name} has invited you to access your secure document portal for {business_name}.

{f"Message from {inviter_name}: {message}" if message else ""}

What you can do in your portal:
- View and respond to document requests
- Securely upload documents to your accountant
- Track request status and due dates

Access Your Portal: {portal_url}

This link will expire in {expires_in}. If the link expires, contact {practice_name} to request a new invitation.

Security tip: If you weren't expecting this email, you can safely ignore it.

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
    # Document Request Templates (T094)
    # =========================================================================

    @classmethod
    def document_request(
        cls,
        business_name: str,
        practice_name: str,
        request_title: str,
        request_description: str,
        due_date: str | None,
        portal_url: str,
        priority: str = "normal",
    ) -> EmailTemplate:
        """Generate document request notification email.

        Sent when an accountant creates a new document request.
        """
        subject = f"Document Request from {practice_name}: {request_title}"

        due_section = ""
        if due_date:
            due_section = f"""
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="background-color: {cls.WARNING_BG}; border-radius: 8px; padding: 16px; margin: 16px 0; width: 100%;">
    <tr>
        <td style="color: {cls.WARNING_TEXT}; font-size: 14px;">
            <strong>Due Date:</strong> {due_date}
        </td>
    </tr>
</table>
"""

        priority_label = ""
        if priority.upper() == "URGENT":
            priority_label = f"""
<span style="background-color: {cls.DANGER_BG}; color: {cls.DANGER_TEXT}; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; text-transform: uppercase;">URGENT</span>
"""
        elif priority.upper() == "HIGH":
            priority_label = f"""
<span style="background-color: {cls.WARNING_BG}; color: {cls.WARNING_TEXT}; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; text-transform: uppercase;">HIGH PRIORITY</span>
"""

        content = f"""
<h1 style="color: {cls.TEXT_COLOR}; font-size: 24px; margin: 0 0 16px 0;">Document Request {priority_label}</h1>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Hi there,
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    <strong>{practice_name}</strong> has requested documents for <strong>{business_name}</strong>.
</p>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="background-color: #f3f4f6; border-radius: 8px; padding: 16px; margin: 16px 0; width: 100%;">
    <tr>
        <td>
            <p style="color: {cls.TEXT_COLOR}; font-size: 16px; font-weight: bold; margin: 0 0 8px 0;">{request_title}</p>
            <p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; margin: 0;">{request_description}</p>
        </td>
    </tr>
</table>
{due_section}
{cls._button("View Request & Upload Documents", portal_url)}
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 16px 0 0 0;">
    Click the button above to view the full request details and upload your documents securely.
</p>
"""

        text = f"""Document Request{" [URGENT]" if priority.upper() == "URGENT" else ""}

Hi there,

{practice_name} has requested documents for {business_name}.

Request: {request_title}
Details: {request_description}
{f"Due Date: {due_date}" if due_date else ""}

View Request & Upload Documents: {portal_url}

Click the link above to view the full request details and upload your documents securely.

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
    # Reminder Templates (T095)
    # =========================================================================

    @classmethod
    def reminder_days_before(
        cls,
        business_name: str,
        practice_name: str,
        request_title: str,
        due_date: str,
        days_remaining: int,
        portal_url: str,
    ) -> EmailTemplate:
        """Generate reminder email for approaching due date.

        Sent 3 days, 2 days, 1 day before due date.
        """
        if days_remaining == 1:
            subject = f"Reminder: Document due TOMORROW - {request_title}"
            urgency_text = "is due <strong>tomorrow</strong>"
            urgency_bg = cls.WARNING_BG
            urgency_color = cls.WARNING_TEXT
        else:
            subject = f"Reminder: Document due in {days_remaining} days - {request_title}"
            urgency_text = f"is due in <strong>{days_remaining} days</strong>"
            urgency_bg = "#eff6ff"
            urgency_color = "#1e40af"

        content = f"""
<h1 style="color: {cls.TEXT_COLOR}; font-size: 24px; margin: 0 0 16px 0;">Document Request Reminder</h1>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Hi there,
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    This is a friendly reminder that the document request for <strong>{business_name}</strong> {urgency_text}.
</p>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="background-color: {urgency_bg}; border-radius: 8px; padding: 16px; margin: 16px 0; width: 100%;">
    <tr>
        <td>
            <p style="color: {urgency_color}; font-size: 14px; font-weight: bold; margin: 0 0 8px 0;">{request_title}</p>
            <p style="color: {urgency_color}; font-size: 14px; margin: 0;">
                Due: {due_date}
            </p>
        </td>
    </tr>
</table>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Please upload the requested documents before the due date.
</p>
{cls._button("Upload Documents Now", portal_url)}
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 16px 0 0 0;">
    If you've already submitted your documents, you can ignore this reminder.
</p>
"""

        text = f"""Document Request Reminder

Hi there,

This is a friendly reminder that the document request for {business_name} is due in {days_remaining} day{"s" if days_remaining > 1 else ""}.

Request: {request_title}
Due Date: {due_date}

Please upload the requested documents before the due date.

Upload Documents Now: {portal_url}

If you've already submitted your documents, you can ignore this reminder.

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
    def reminder_due_today(
        cls,
        business_name: str,
        practice_name: str,
        request_title: str,
        portal_url: str,
    ) -> EmailTemplate:
        """Generate reminder email for document due today."""
        subject = f"URGENT: Document due TODAY - {request_title}"

        content = f"""
<h1 style="color: {cls.TEXT_COLOR}; font-size: 24px; margin: 0 0 16px 0;">
    <span style="background-color: {cls.DANGER_BG}; color: {cls.DANGER_TEXT}; padding: 4px 8px; border-radius: 4px; font-size: 14px; font-weight: bold;">DUE TODAY</span>
    Document Request
</h1>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Hi there,
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    The document request for <strong>{business_name}</strong> is due <strong>today</strong>.
</p>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="background-color: {cls.DANGER_BG}; border-radius: 8px; padding: 16px; margin: 16px 0; width: 100%;">
    <tr>
        <td style="color: {cls.DANGER_TEXT}; font-size: 14px;">
            <strong>{request_title}</strong><br><br>
            Please submit your documents as soon as possible to avoid delays.
        </td>
    </tr>
</table>
{cls._button("Upload Documents Now", portal_url)}
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 16px 0 0 0;">
    If you need more time, please contact {practice_name} directly.
</p>
"""

        text = f"""URGENT: Document Due TODAY

Hi there,

The document request for {business_name} is due TODAY.

Request: {request_title}

Please submit your documents as soon as possible to avoid delays.

Upload Documents Now: {portal_url}

If you need more time, please contact {practice_name} directly.

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
    def reminder_overdue(
        cls,
        business_name: str,
        practice_name: str,
        request_title: str,
        due_date: str,
        days_overdue: int,
        portal_url: str,
    ) -> EmailTemplate:
        """Generate reminder email for overdue document request."""
        subject = f"OVERDUE: Document was due {days_overdue} day{'s' if days_overdue > 1 else ''} ago - {request_title}"

        content = f"""
<h1 style="color: {cls.TEXT_COLOR}; font-size: 24px; margin: 0 0 16px 0;">
    <span style="background-color: {cls.DANGER_BG}; color: {cls.DANGER_TEXT}; padding: 4px 8px; border-radius: 4px; font-size: 14px; font-weight: bold;">OVERDUE</span>
    Document Request
</h1>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Hi there,
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    The document request for <strong>{business_name}</strong> is now <strong>{days_overdue} day{"s" if days_overdue > 1 else ""} overdue</strong>.
</p>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="background-color: {cls.DANGER_BG}; border-radius: 8px; padding: 16px; margin: 16px 0; width: 100%;">
    <tr>
        <td>
            <p style="color: {cls.DANGER_TEXT}; font-size: 14px; font-weight: bold; margin: 0 0 8px 0;">{request_title}</p>
            <p style="color: {cls.DANGER_TEXT}; font-size: 14px; margin: 0;">
                Was due: {due_date}<br>
                <strong>Please submit immediately</strong>
            </p>
        </td>
    </tr>
</table>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Your accountant at {practice_name} is waiting for these documents. Please upload them as soon as possible.
</p>
{cls._button("Upload Documents Now", portal_url)}
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 16px 0 0 0;">
    If you're having trouble gathering these documents, please contact {practice_name} directly.
</p>
"""

        text = f"""OVERDUE: Document Request

Hi there,

The document request for {business_name} is now {days_overdue} day{"s" if days_overdue > 1 else ""} overdue.

Request: {request_title}
Was Due: {due_date}

Please submit immediately.

Your accountant at {practice_name} is waiting for these documents. Please upload them as soon as possible.

Upload Documents Now: {portal_url}

If you're having trouble gathering these documents, please contact {practice_name} directly.

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
    # Response Notification Templates (T096)
    # =========================================================================

    @classmethod
    def response_received(
        cls,
        accountant_name: str,
        business_name: str,
        request_title: str,
        response_summary: str,
        document_count: int,
        dashboard_url: str,
    ) -> EmailTemplate:
        """Generate notification email when client responds to a request.

        Sent to the accountant when the business owner submits a response.
        """
        subject = f"Response received: {request_title} - {business_name}"

        document_text = f"{document_count} document{'s' if document_count != 1 else ''}"

        content = f"""
<h1 style="color: {cls.TEXT_COLOR}; font-size: 24px; margin: 0 0 16px 0;">Response Received</h1>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Hi {accountant_name},
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    <strong>{business_name}</strong> has responded to your document request.
</p>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="background-color: {cls.SUCCESS_BG}; border-radius: 8px; padding: 16px; margin: 16px 0; width: 100%;">
    <tr>
        <td>
            <p style="color: {cls.SUCCESS_TEXT}; font-size: 14px; font-weight: bold; margin: 0 0 8px 0;">{request_title}</p>
            <p style="color: {cls.SUCCESS_TEXT}; font-size: 14px; margin: 0;">
                {document_text} uploaded
            </p>
        </td>
    </tr>
</table>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 8px 0;">
    <strong>Response Summary:</strong>
</p>
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 0 0 16px 0; padding: 12px; background-color: #f9fafb; border-radius: 8px;">
    {response_summary if response_summary else "(No message provided)"}
</p>
{cls._button("View Response", dashboard_url)}
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 16px 0 0 0;">
    You can review the submitted documents and mark the request as complete in your dashboard.
</p>
"""

        text = f"""Response Received

Hi {accountant_name},

{business_name} has responded to your document request.

Request: {request_title}
Documents Uploaded: {document_text}

Response Summary:
{response_summary if response_summary else "(No message provided)"}

View Response: {dashboard_url}

You can review the submitted documents and mark the request as complete in your dashboard.

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
    def request_completed(
        cls,
        business_name: str,
        practice_name: str,
        request_title: str,
        completed_by: str,
        portal_url: str,
        note: str | None = None,
    ) -> EmailTemplate:
        """Generate notification email when request is marked complete.

        Sent to the business owner when their submission is accepted.
        """
        subject = f"Request completed: {request_title}"

        note_section = ""
        if note:
            note_section = f"""
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="background-color: #eff6ff; border-radius: 8px; padding: 16px; margin: 16px 0; width: 100%;">
    <tr>
        <td style="color: #1e40af; font-size: 14px;">
            <strong>Note from {completed_by}:</strong><br>
            {note}
        </td>
    </tr>
</table>
"""

        content = f"""
<h1 style="color: {cls.TEXT_COLOR}; font-size: 24px; margin: 0 0 16px 0;">
    <span style="color: {cls.SUCCESS_TEXT};">&#10003;</span> Request Completed
</h1>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Hi there,
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Great news! Your document submission for <strong>{business_name}</strong> has been received and marked as complete.
</p>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="background-color: {cls.SUCCESS_BG}; border-radius: 8px; padding: 16px; margin: 16px 0; width: 100%;">
    <tr>
        <td style="color: {cls.SUCCESS_TEXT}; font-size: 14px;">
            <strong>{request_title}</strong><br><br>
            Completed by: {completed_by} at {practice_name}
        </td>
    </tr>
</table>
{note_section}
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Thank you for your prompt response!
</p>
{cls._button("View in Portal", portal_url)}
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 16px 0 0 0;">
    You can view your completed requests and any new requests in your portal.
</p>
"""

        text = f"""Request Completed

Hi there,

Great news! Your document submission for {business_name} has been received and marked as complete.

Request: {request_title}
Completed by: {completed_by} at {practice_name}

{f"Note from {completed_by}: {note}" if note else ""}

Thank you for your prompt response!

View in Portal: {portal_url}

You can view your completed requests and any new requests in your portal.

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
    def document_uploaded(
        cls,
        accountant_name: str,
        business_name: str,
        request_title: str,
        document_name: str,
        document_count: int,
        dashboard_url: str,
    ) -> EmailTemplate:
        """Generate notification email when a document is uploaded.

        Sent to the accountant when a new document is uploaded to a request.
        """
        subject = f"New document uploaded: {document_name} - {business_name}"

        content = f"""
<h1 style="color: {cls.TEXT_COLOR}; font-size: 24px; margin: 0 0 16px 0;">New Document Uploaded</h1>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Hi {accountant_name},
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    <strong>{business_name}</strong> has uploaded a new document to their request.
</p>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="background-color: #f3f4f6; border-radius: 8px; padding: 16px; margin: 16px 0; width: 100%;">
    <tr>
        <td>
            <p style="color: {cls.TEXT_COLOR}; font-size: 14px; font-weight: bold; margin: 0 0 8px 0;">{request_title}</p>
            <p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; margin: 0;">
                Document: {document_name}<br>
                Total documents: {document_count}
            </p>
        </td>
    </tr>
</table>
{cls._button("View Document", dashboard_url)}
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 16px 0 0 0;">
    All uploaded documents are virus scanned for security.
</p>
"""

        text = f"""New Document Uploaded

Hi {accountant_name},

{business_name} has uploaded a new document to their request.

Request: {request_title}
Document: {document_name}
Total documents: {document_count}

View Document: {dashboard_url}

All uploaded documents are virus scanned for security.

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
    # Transaction Classification Templates (Spec 047)
    # =========================================================================

    @classmethod
    def transaction_classification_request(
        cls,
        business_name: str,
        practice_name: str,
        accountant_name: str,
        portal_url: str,
        transaction_count: int,
        expires_in: str = "7 days",
        message: str | None = None,
    ) -> EmailTemplate:
        """Generate email asking client to classify their transactions.

        Sent when an accountant requests the client to classify unresolved
        transactions during BAS preparation.
        """
        subject = f"{practice_name} needs you to classify {transaction_count} transaction{'s' if transaction_count != 1 else ''}"

        message_section = ""
        if message:
            message_section = f"""
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="background-color: #eff6ff; border-radius: 8px; padding: 16px; margin: 16px 0; width: 100%;">
    <tr>
        <td style="color: #1e40af; font-size: 14px;">
            <strong>Message from {accountant_name}:</strong><br>
            {message}
        </td>
    </tr>
</table>
"""

        content = f"""
<h1 style="color: {cls.TEXT_COLOR}; font-size: 24px; margin: 0 0 16px 0;">Action Required: Classify Your Transactions</h1>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Hi there,
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    <strong>{accountant_name}</strong> from <strong>{practice_name}</strong> is preparing the BAS for
    <strong>{business_name}</strong> and needs your help classifying
    <strong>{transaction_count} transaction{"s" if transaction_count != 1 else ""}</strong>.
</p>
{message_section}
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 8px 0;">
    <strong>What you need to do:</strong>
</p>
<ul style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.8; padding-left: 24px; margin: 0 0 16px 0;">
    <li>Click the button below to view the transactions</li>
    <li>For each one, select what it was for (e.g. office supplies, travel, personal)</li>
    <li>Some transactions may need a receipt or invoice &mdash; you can upload these too</li>
    <li>It should take less than 5 minutes</li>
</ul>
{cls._button("Classify Your Transactions", portal_url)}
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="background-color: {cls.WARNING_BG}; border-radius: 8px; padding: 12px 16px; margin: 16px 0; width: 100%;">
    <tr>
        <td style="color: {cls.WARNING_TEXT}; font-size: 14px;">
            &#128206; <strong>Receipts:</strong> Some transactions may require you to attach a receipt or invoice for tax compliance.
        </td>
    </tr>
</table>
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 16px 0 0 0;">
    This link will expire in {expires_in}. You can save your progress and come back later.
</p>
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 8px 0 0 0;">
    <strong>Security tip:</strong> If you weren't expecting this email, you can safely ignore it.
</p>
"""

        text = f"""Action Required: Classify Your Transactions

Hi there,

{accountant_name} from {practice_name} is preparing the BAS for {business_name} and needs your help classifying {transaction_count} transaction{"s" if transaction_count != 1 else ""}.

{f"Message from {accountant_name}: {message}" if message else ""}

What you need to do:
- Click the link below to view the transactions
- For each one, select what it was for (e.g. office supplies, travel, personal)
- Some transactions may need a receipt or invoice - you can upload these too
- It should take less than 5 minutes

Classify Your Transactions: {portal_url}

This link will expire in {expires_in}. You can save your progress and come back later.

Security tip: If you weren't expecting this email, you can safely ignore it.

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
    # Portal Login Templates (Self-Serve)
    # =========================================================================

    @classmethod
    def portal_login(
        cls,
        portal_url: str,
        expires_in: str = "24 hours",
    ) -> EmailTemplate:
        """Generate portal login email for self-serve access.

        Sent when a client requests a magic link from the login page.
        """
        subject = "Your Clairo Portal Login Link"

        content = f"""
<h1 style="color: {cls.TEXT_COLOR}; font-size: 24px; margin: 0 0 16px 0;">Portal Login</h1>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    Hi there,
</p>
<p style="color: {cls.TEXT_COLOR}; font-size: 16px; line-height: 1.6; margin: 0 0 16px 0;">
    You requested a login link for your Clairo portal. Click the button below to access your account.
</p>
{cls._button("Log In to Your Portal", portal_url)}
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 16px 0 0 0;">
    This link will expire in {expires_in}. If it expires, you can request a new one from the login page.
</p>
<p style="color: {cls.SECONDARY_TEXT}; font-size: 14px; line-height: 1.6; margin: 8px 0 0 0;">
    <strong>Security tip:</strong> If you didn&rsquo;t request this link, you can safely ignore this email.
</p>
"""

        text = f"""Portal Login

Hi there,

You requested a login link for your Clairo portal. Click the link below to access your account.

Log In to Your Portal: {portal_url}

This link will expire in {expires_in}. If it expires, you can request a new one from the login page.

Security tip: If you didn't request this link, you can safely ignore this email.

---
Clairo - See everything. Miss nothing.
www.clairo.com.au | support@clairo.com.au
"""

        return EmailTemplate(
            subject=subject,
            html=cls._base_template(content),
            text=text,
        )
