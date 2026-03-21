"""Notifications module for Clairo.

Handles email notifications, in-app notifications, and other
communication channels.
"""

from app.modules.notifications.email_service import EmailService, get_email_service
from app.modules.notifications.models import Notification, NotificationType
from app.modules.notifications.service import NotificationService
from app.modules.notifications.templates import EmailTemplate, EmailTemplates

__all__ = [
    "EmailService",
    "EmailTemplate",
    "EmailTemplates",
    "Notification",
    "NotificationService",
    "NotificationType",
    "get_email_service",
]
