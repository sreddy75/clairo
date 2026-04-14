"""Unit tests for auto-reminder functionality.

Tests the reminder scheduling logic and Celery task processing.

Spec: 030-client-portal-document-requests
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.portal.enums import RequestStatus


class TestDetermineReminderType:
    """Tests for _determine_reminder_type function."""

    def test_reminder_for_due_in_3_days(self):
        """Test reminder triggered 3 days before due."""
        from app.tasks.portal.auto_reminders import _determine_reminder_type

        request = MagicMock()
        request.due_date = date.today() + timedelta(days=3)
        today = date.today()

        result = _determine_reminder_type(
            request, today, days_before_due=3, overdue_reminder_days=[1, 3, 7]
        )
        assert result == "due_in_3_days"

    def test_reminder_for_due_in_2_days(self):
        """Test reminder triggered 2 days before due."""
        from app.tasks.portal.auto_reminders import _determine_reminder_type

        request = MagicMock()
        request.due_date = date.today() + timedelta(days=2)
        today = date.today()

        result = _determine_reminder_type(
            request, today, days_before_due=3, overdue_reminder_days=[1, 3, 7]
        )
        assert result == "due_in_2_days"

    def test_reminder_for_due_today(self):
        """Test reminder triggered on due date."""
        from app.tasks.portal.auto_reminders import _determine_reminder_type

        request = MagicMock()
        request.due_date = date.today()
        today = date.today()

        result = _determine_reminder_type(
            request, today, days_before_due=3, overdue_reminder_days=[1, 3, 7]
        )
        assert result == "due_today"

    def test_reminder_for_1_day_overdue(self):
        """Test reminder triggered 1 day overdue."""
        from app.tasks.portal.auto_reminders import _determine_reminder_type

        request = MagicMock()
        request.due_date = date.today() - timedelta(days=1)
        today = date.today()

        result = _determine_reminder_type(
            request, today, days_before_due=3, overdue_reminder_days=[1, 3, 7]
        )
        assert result == "overdue_1_days"

    def test_reminder_for_3_days_overdue(self):
        """Test reminder triggered 3 days overdue."""
        from app.tasks.portal.auto_reminders import _determine_reminder_type

        request = MagicMock()
        request.due_date = date.today() - timedelta(days=3)
        today = date.today()

        result = _determine_reminder_type(
            request, today, days_before_due=3, overdue_reminder_days=[1, 3, 7]
        )
        assert result == "overdue_3_days"

    def test_reminder_for_7_days_overdue(self):
        """Test reminder triggered 7 days overdue."""
        from app.tasks.portal.auto_reminders import _determine_reminder_type

        request = MagicMock()
        request.due_date = date.today() - timedelta(days=7)
        today = date.today()

        result = _determine_reminder_type(
            request, today, days_before_due=3, overdue_reminder_days=[1, 3, 7]
        )
        assert result == "overdue_7_days"

    def test_no_reminder_for_2_days_overdue(self):
        """Test no reminder for non-scheduled overdue day."""
        from app.tasks.portal.auto_reminders import _determine_reminder_type

        request = MagicMock()
        request.due_date = date.today() - timedelta(days=2)
        today = date.today()

        result = _determine_reminder_type(
            request, today, days_before_due=3, overdue_reminder_days=[1, 3, 7]
        )
        assert result is None

    def test_no_reminder_for_far_future_due(self):
        """Test no reminder for requests due far in future."""
        from app.tasks.portal.auto_reminders import _determine_reminder_type

        request = MagicMock()
        request.due_date = date.today() + timedelta(days=10)
        today = date.today()

        result = _determine_reminder_type(
            request, today, days_before_due=3, overdue_reminder_days=[1, 3, 7]
        )
        assert result is None

    def test_no_reminder_for_no_due_date(self):
        """Test no reminder for requests without due date."""
        from app.tasks.portal.auto_reminders import _determine_reminder_type

        request = MagicMock()
        request.due_date = None
        today = date.today()

        result = _determine_reminder_type(
            request, today, days_before_due=3, overdue_reminder_days=[1, 3, 7]
        )
        assert result is None

    def test_custom_days_before_due(self):
        """Test custom days_before_due setting."""
        from app.tasks.portal.auto_reminders import _determine_reminder_type

        request = MagicMock()
        request.due_date = date.today() + timedelta(days=5)
        today = date.today()

        result = _determine_reminder_type(
            request, today, days_before_due=5, overdue_reminder_days=[1, 3, 7]
        )
        assert result == "due_in_5_days"

    def test_custom_overdue_reminder_days(self):
        """Test custom overdue_reminder_days setting."""
        from app.tasks.portal.auto_reminders import _determine_reminder_type

        request = MagicMock()
        request.due_date = date.today() - timedelta(days=14)
        today = date.today()

        result = _determine_reminder_type(
            request, today, days_before_due=3, overdue_reminder_days=[7, 14, 21]
        )
        assert result == "overdue_14_days"


class TestProcessReminders:
    """Tests for _process_reminders async function."""

    @pytest.mark.asyncio
    async def test_process_reminders_empty_list(self):
        """Test processing with no eligible requests."""
        from app.tasks.portal.auto_reminders import _process_reminders

        with patch("app.tasks.portal.auto_reminders.get_db_context") as mock_db_context:
            mock_db = MagicMock()
            mock_db.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db.__aexit__ = AsyncMock(return_value=None)
            mock_db.commit = AsyncMock()
            mock_db_context.return_value = mock_db

            with patch(
                "app.modules.portal.repository.DocumentRequestRepository"
            ) as mock_repo_class:
                mock_repo = MagicMock()
                mock_repo.get_pending_reminders = AsyncMock(return_value=[])
                mock_repo_class.return_value = mock_repo

                result = await _process_reminders(
                    days_before_due=3,
                    overdue_reminder_days=[1, 3, 7],
                    min_days_between_reminders=3,
                )

                assert result["total_eligible"] == 0
                assert result["sent"] == 0
                assert result["failed"] == 0
                assert result["skipped"] == 0

    @pytest.mark.asyncio
    async def test_process_reminders_skips_no_due_date(self):
        """Test that requests without due dates are skipped."""
        from app.tasks.portal.auto_reminders import _process_reminders

        request = MagicMock()
        request.id = uuid4()
        request.tenant_id = uuid4()
        request.due_date = None
        request.reminder_count = 0

        with patch("app.tasks.portal.auto_reminders.get_db_context") as mock_db_context:
            mock_db = MagicMock()
            mock_db.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db.__aexit__ = AsyncMock(return_value=None)
            mock_db.commit = AsyncMock()
            mock_db_context.return_value = mock_db

            with patch(
                "app.modules.portal.repository.DocumentRequestRepository"
            ) as mock_repo_class:
                mock_repo = MagicMock()
                mock_repo.get_pending_reminders = AsyncMock(return_value=[request])
                mock_repo_class.return_value = mock_repo

                with patch("app.modules.portal.requests.service.DocumentRequestService"):
                    result = await _process_reminders(
                        days_before_due=3,
                        overdue_reminder_days=[1, 3, 7],
                        min_days_between_reminders=3,
                    )

                    assert result["total_eligible"] == 1
                    assert result["skipped"] == 1
                    assert result["sent"] == 0


class TestAutoRemindToggle:
    """Tests for auto-remind toggle service method."""

    @pytest.mark.asyncio
    async def test_toggle_auto_remind_enables(self):
        """Test enabling auto-remind for a request."""
        from app.modules.portal.requests.service import DocumentRequestService

        mock_db = AsyncMock()
        service = DocumentRequestService(mock_db)

        request = MagicMock()
        request.id = uuid4()
        request.tenant_id = uuid4()
        request.auto_remind = False
        request.status = RequestStatus.PENDING.value

        with (
            patch.object(service, "request_repo") as mock_repo,
            patch.object(service, "event_repo"),
        ):
            mock_repo.get_by_id_and_tenant = AsyncMock(return_value=request)
            mock_repo.update = AsyncMock(return_value=request)

            await service.toggle_auto_remind(
                request_id=request.id,
                tenant_id=request.tenant_id,
                user_id=uuid4(),
                enabled=True,
            )

            mock_repo.update.assert_called_once()
            call_args = mock_repo.update.call_args
            assert call_args[0][1]["auto_remind"] is True

    @pytest.mark.asyncio
    async def test_toggle_auto_remind_disables(self):
        """Test disabling auto-remind for a request."""
        from app.modules.portal.requests.service import DocumentRequestService

        mock_db = AsyncMock()
        service = DocumentRequestService(mock_db)

        request = MagicMock()
        request.id = uuid4()
        request.tenant_id = uuid4()
        request.auto_remind = True
        request.status = RequestStatus.PENDING.value

        with (
            patch.object(service, "request_repo") as mock_repo,
            patch.object(service, "event_repo"),
        ):
            mock_repo.get_by_id_and_tenant = AsyncMock(return_value=request)
            mock_repo.update = AsyncMock(return_value=request)

            await service.toggle_auto_remind(
                request_id=request.id,
                tenant_id=request.tenant_id,
                user_id=uuid4(),
                enabled=False,
            )

            mock_repo.update.assert_called_once()
            call_args = mock_repo.update.call_args
            assert call_args[0][1]["auto_remind"] is False


class TestReminderSettings:
    """Tests for reminder settings schemas."""

    def test_reminder_settings_request_defaults(self):
        """Test default values for reminder settings request."""
        from app.modules.portal.schemas import ReminderSettingsRequest

        settings = ReminderSettingsRequest()
        assert settings.days_before_due == 3
        assert settings.overdue_reminder_days == [1, 3, 7]
        assert settings.min_days_between_reminders == 3
        assert settings.auto_remind_enabled is True

    def test_reminder_settings_request_custom(self):
        """Test custom values for reminder settings request."""
        from app.modules.portal.schemas import ReminderSettingsRequest

        settings = ReminderSettingsRequest(
            days_before_due=7,
            overdue_reminder_days=[1, 7, 14],
            min_days_between_reminders=5,
            auto_remind_enabled=False,
        )
        assert settings.days_before_due == 7
        assert settings.overdue_reminder_days == [1, 7, 14]
        assert settings.min_days_between_reminders == 5
        assert settings.auto_remind_enabled is False

    def test_reminder_settings_request_validation(self):
        """Test validation for reminder settings request."""
        from pydantic import ValidationError

        from app.modules.portal.schemas import ReminderSettingsRequest

        # days_before_due must be >= 1
        with pytest.raises(ValidationError):
            ReminderSettingsRequest(days_before_due=0)

        # days_before_due must be <= 14
        with pytest.raises(ValidationError):
            ReminderSettingsRequest(days_before_due=15)

        # min_days_between_reminders must be >= 1
        with pytest.raises(ValidationError):
            ReminderSettingsRequest(min_days_between_reminders=0)

        # min_days_between_reminders must be <= 7
        with pytest.raises(ValidationError):
            ReminderSettingsRequest(min_days_between_reminders=8)


class TestAutoRemindSchemas:
    """Tests for auto-remind schemas."""

    def test_auto_remind_toggle_request(self):
        """Test auto-remind toggle request schema."""
        from app.modules.portal.schemas import AutoRemindToggleRequest

        request = AutoRemindToggleRequest(enabled=True)
        assert request.enabled is True

        request = AutoRemindToggleRequest(enabled=False)
        assert request.enabled is False

    def test_auto_remind_response(self):
        """Test auto-remind response schema."""
        from datetime import datetime

        from app.modules.portal.schemas import AutoRemindResponse

        request_id = uuid4()
        last_reminder = datetime.now()

        response = AutoRemindResponse(
            request_id=request_id,
            auto_remind=True,
            last_reminder_at=last_reminder,
            reminder_count=3,
        )

        assert response.request_id == request_id
        assert response.auto_remind is True
        assert response.last_reminder_at == last_reminder
        assert response.reminder_count == 3

    def test_send_reminder_response(self):
        """Test send reminder response schema."""
        from datetime import datetime

        from app.modules.portal.schemas import SendReminderResponse

        request_id = uuid4()
        last_reminder = datetime.now()

        response = SendReminderResponse(
            request_id=request_id,
            reminder_count=5,
            last_reminder_at=last_reminder,
        )

        assert response.request_id == request_id
        assert response.reminder_count == 5
        assert response.last_reminder_at == last_reminder
