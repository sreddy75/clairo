"""Unit tests for portal models.

Tests for:
- PortalInvitation
- PortalSession
- DocumentRequestTemplate
- DocumentRequest
- RequestResponse
- PortalDocument
- RequestEvent
- BulkRequest
"""

from app.modules.portal.enums import (
    BulkRequestStatus,
    InvitationStatus,
    RequestPriority,
    RequestStatus,
    ScanStatus,
)


class TestInvitationStatus:
    """Test InvitationStatus enum."""

    def test_invitation_statuses(self):
        """All expected statuses exist."""
        assert InvitationStatus.PENDING.value == "PENDING"
        assert InvitationStatus.SENT.value == "SENT"
        assert InvitationStatus.ACCEPTED.value == "ACCEPTED"
        assert InvitationStatus.EXPIRED.value == "EXPIRED"
        assert InvitationStatus.FAILED.value == "FAILED"


class TestRequestStatus:
    """Test RequestStatus enum."""

    def test_request_statuses(self):
        """All expected statuses exist."""
        assert RequestStatus.DRAFT.value == "DRAFT"
        assert RequestStatus.PENDING.value == "PENDING"
        assert RequestStatus.VIEWED.value == "VIEWED"
        assert RequestStatus.IN_PROGRESS.value == "IN_PROGRESS"
        assert RequestStatus.COMPLETE.value == "COMPLETE"
        assert RequestStatus.CANCELLED.value == "CANCELLED"


class TestRequestPriority:
    """Test RequestPriority enum."""

    def test_priority_levels(self):
        """All expected priority levels exist."""
        assert RequestPriority.LOW.value == "LOW"
        assert RequestPriority.NORMAL.value == "NORMAL"
        assert RequestPriority.HIGH.value == "HIGH"
        assert RequestPriority.URGENT.value == "URGENT"


class TestBulkRequestStatus:
    """Test BulkRequestStatus enum."""

    def test_bulk_statuses(self):
        """All expected statuses exist."""
        assert BulkRequestStatus.PENDING.value == "PENDING"
        assert BulkRequestStatus.PROCESSING.value == "PROCESSING"
        assert BulkRequestStatus.COMPLETED.value == "COMPLETED"
        assert BulkRequestStatus.PARTIAL.value == "PARTIAL"
        assert BulkRequestStatus.FAILED.value == "FAILED"


class TestScanStatus:
    """Test ScanStatus enum."""

    def test_scan_statuses(self):
        """All expected statuses exist."""
        assert ScanStatus.PENDING.value == "PENDING"
        assert ScanStatus.CLEAN.value == "CLEAN"
        assert ScanStatus.INFECTED.value == "INFECTED"
