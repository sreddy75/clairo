"""Unit tests for XeroWritebackService.

Spec 049: Xero Tax Code Write-Back.
Tests cover:
- get_job() raises WritebackJobNotFoundError when repo returns None
- group_overrides_by_document() groups correctly (total_count = unique docs)
- initiate_writeback() creates one item per document, not per override
- apply_overrides_to_line_items() override-mode and split-mode (Spec 049 US10/US11)
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.integrations.xero.exceptions import WritebackJobNotFoundError
from app.modules.integrations.xero.writeback_service import (
    XeroWritebackService,
    apply_overrides_to_line_items,
)

# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def mock_db():
    """Mock async database session."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


@pytest.fixture
def mock_repo():
    return AsyncMock()


@pytest.fixture
def service(mock_db, mock_repo):
    svc = XeroWritebackService(mock_db)
    svc.repo = mock_repo
    return svc


# ===========================================================================
# get_job() tests
# ===========================================================================


class TestGetJob:
    """Tests for XeroWritebackService.get_job()."""

    @pytest.mark.asyncio
    async def test_raises_not_found_when_repo_returns_none(
        self, service: XeroWritebackService, mock_repo: AsyncMock
    ) -> None:
        mock_repo.get_job.return_value = None
        job_id = uuid4()
        tenant_id = uuid4()

        with pytest.raises(WritebackJobNotFoundError) as exc_info:
            await service.get_job(job_id, tenant_id)

        mock_repo.get_job.assert_awaited_once_with(job_id, tenant_id)
        assert exc_info.value.job_id == job_id

    @pytest.mark.asyncio
    async def test_returns_job_when_found(
        self, service: XeroWritebackService, mock_repo: AsyncMock
    ) -> None:
        fake_job = MagicMock()
        mock_repo.get_job.return_value = fake_job
        job_id = uuid4()
        tenant_id = uuid4()

        result = await service.get_job(job_id, tenant_id)

        assert result is fake_job


# ===========================================================================
# initiate_writeback() grouping tests
# ===========================================================================


def _make_override(source_type: str, source_id, line_item_index: int = 0):
    """Build a minimal TaxCodeOverride mock."""
    ov = MagicMock()
    ov.id = uuid4()
    ov.source_type = source_type
    ov.source_id = source_id
    ov.line_item_index = line_item_index
    ov.original_tax_type = "G11"
    ov.override_tax_type = "GST"
    return ov


class TestInitiateWritebackGrouping:
    """Tests that initiate_writeback groups overrides correctly."""

    @pytest.mark.asyncio
    async def test_one_item_per_document_not_per_override(
        self, service: XeroWritebackService, mock_db: AsyncMock, mock_repo: AsyncMock
    ) -> None:
        """Three overrides on two documents → two items, total_count=2."""
        doc_a = uuid4()
        doc_b = uuid4()

        # Two overrides on doc_a, one on doc_b
        overrides = [
            _make_override("invoice", doc_a, 0),
            _make_override("invoice", doc_a, 1),
            _make_override("invoice", doc_b, 0),
        ]

        # Mock session fetch
        fake_session = MagicMock()
        fake_session.status = "in_progress"  # any non-draft status
        fake_session.period = MagicMock()
        fake_session.period.connection_id = uuid4()

        # Mock connection fetch
        fake_connection = MagicMock()
        fake_connection.id = uuid4()

        # Mock repo
        mock_repo.list_jobs_for_session.return_value = []

        fake_job = MagicMock()
        fake_job.id = uuid4()
        mock_repo.create_job.return_value = fake_job
        mock_repo.create_item = AsyncMock()

        # Patch internal helper methods
        with (
            patch.object(service, "_get_session", return_value=fake_session),
            patch.object(service, "_get_connection", return_value=fake_connection),
            patch.object(service, "_get_pending_overrides", return_value=overrides),
            patch.object(service, "_resolve_xero_document_id", return_value=str(uuid4())),
            patch("app.modules.integrations.xero.writeback_service.enqueue_writeback_task"),
            patch(
                "app.modules.bas.repository.BASRepository",
                return_value=AsyncMock(),
            ),
        ):
            await service.initiate_writeback(
                session_id=uuid4(),
                triggered_by=uuid4(),
                tenant_id=uuid4(),
            )

        # total_count should be 2 (unique documents), not 3 (overrides)
        mock_repo.create_job.assert_awaited_once()
        call_kwargs = mock_repo.create_job.call_args.kwargs
        assert call_kwargs["total_count"] == 2

        # create_item should be called exactly twice
        assert mock_repo.create_item.await_count == 2

    @pytest.mark.asyncio
    async def test_one_item_for_single_document_multiple_overrides(
        self, service: XeroWritebackService, mock_db: AsyncMock, mock_repo: AsyncMock
    ) -> None:
        """Five overrides on one document → one item, total_count=1."""
        doc_id = uuid4()
        overrides = [_make_override("invoice", doc_id, i) for i in range(5)]

        fake_session = MagicMock()
        fake_session.status = "in_progress"
        fake_session.period = MagicMock()
        fake_session.period.connection_id = uuid4()

        fake_connection = MagicMock()
        fake_connection.id = uuid4()

        mock_repo.list_jobs_for_session.return_value = []
        fake_job = MagicMock()
        fake_job.id = uuid4()
        mock_repo.create_job.return_value = fake_job
        mock_repo.create_item = AsyncMock()

        with (
            patch.object(service, "_get_session", return_value=fake_session),
            patch.object(service, "_get_connection", return_value=fake_connection),
            patch.object(service, "_get_pending_overrides", return_value=overrides),
            patch.object(service, "_resolve_xero_document_id", return_value=str(uuid4())),
            patch("app.modules.integrations.xero.writeback_service.enqueue_writeback_task"),
            patch(
                "app.modules.bas.repository.BASRepository",
                return_value=AsyncMock(),
            ),
        ):
            await service.initiate_writeback(
                session_id=uuid4(),
                triggered_by=uuid4(),
                tenant_id=uuid4(),
            )

        call_kwargs = mock_repo.create_job.call_args.kwargs
        assert call_kwargs["total_count"] == 1
        assert mock_repo.create_item.await_count == 1


# ===========================================================================
# apply_overrides_to_line_items() — two-mode handling (Spec 049 US10/US11)
# ===========================================================================


def _make_line_override(
    line_item_index: int,
    override_tax_type: str,
    is_new_split: bool = False,
    is_deleted: bool = False,
    line_amount: Decimal | None = None,
    line_description: str | None = None,
    line_account_code: str | None = None,
) -> MagicMock:
    """Build a MagicMock TaxCodeOverride for apply_overrides_to_line_items tests."""
    ov = MagicMock()
    ov.line_item_index = line_item_index
    ov.override_tax_type = override_tax_type
    ov.is_new_split = is_new_split
    ov.is_deleted = is_deleted
    ov.line_amount = line_amount
    ov.line_description = line_description
    ov.line_account_code = line_account_code
    return ov


class TestApplyOverridesToLineItems:
    """Tests for apply_overrides_to_line_items() covering both override-mode and split-mode."""

    def test_override_mode_patches_existing_tax_type(self) -> None:
        """Patching TaxType on an existing line item updates before/after dicts."""
        line_items = [
            {"TaxType": "INPUT", "LineAmount": 100.0},
            {"TaxType": "BASEXCLUDED", "LineAmount": 200.0},
        ]
        overrides = [_make_line_override(1, "OUTPUT")]

        result, before, after = apply_overrides_to_line_items(line_items, overrides)

        assert result[1]["TaxType"] == "OUTPUT"
        assert before["1"] == "BASEXCLUDED"
        assert after["1"] == "OUTPUT"
        # Unchanged item
        assert result[0]["TaxType"] == "INPUT"

    def test_override_mode_removes_tax_amount(self) -> None:
        """TaxAmount should be removed so Xero can recalculate it."""
        line_items = [{"TaxType": "INPUT", "TaxAmount": 9.09, "LineAmount": 100.0}]
        overrides = [_make_line_override(0, "BASEXCLUDED")]

        result, _, _ = apply_overrides_to_line_items(line_items, overrides)

        assert "TaxAmount" not in result[0]

    def test_override_mode_applies_line_amount_override(self) -> None:
        """When line_amount is set on the override, it overwrites LineAmount."""
        line_items = [{"TaxType": "INPUT", "LineAmount": 100.0}]
        overrides = [_make_line_override(0, "OUTPUT", line_amount=Decimal("75.00"))]

        result, _, _ = apply_overrides_to_line_items(line_items, overrides)

        assert result[0]["LineAmount"] == pytest.approx(75.0)

    def test_override_mode_snake_case_normalised(self) -> None:
        """snake_case line items are normalised to PascalCase before patching."""
        line_items = [{"tax_type": "INPUT", "line_amount": 50.0}]
        overrides = [_make_line_override(0, "OUTPUT")]

        result, _, _ = apply_overrides_to_line_items(line_items, overrides)

        assert result[0]["TaxType"] == "OUTPUT"
        assert "tax_type" not in result[0]

    def test_override_mode_out_of_range_index_skipped(self) -> None:
        """An override with an index >= len(items) is silently skipped."""
        line_items = [{"TaxType": "INPUT"}]
        overrides = [_make_line_override(5, "OUTPUT")]

        result, before, after = apply_overrides_to_line_items(line_items, overrides)

        assert len(result) == 1
        assert before == {}
        assert after == {}

    def test_split_mode_appends_alongside_originals(self) -> None:
        """is_new_split=True overrides are appended; original line items are retained."""
        line_items = [{"TaxType": "INPUT", "LineAmount": 100.0, "AccountCode": "400"}]
        overrides = [
            _make_line_override(
                1,
                "OUTPUT",
                is_new_split=True,
                line_amount=Decimal("50.00"),
                line_description="GST portion",
            )
        ]

        result, before, after = apply_overrides_to_line_items(line_items, overrides)

        # Original is retained; new split appended
        assert len(result) == 2
        assert result[0]["TaxType"] == "INPUT"
        assert result[1]["TaxType"] == "OUTPUT"
        assert result[1]["LineAmount"] == pytest.approx(50.0)
        assert result[1]["Description"] == "GST portion"
        assert before["1"] == "NONE"
        assert after["1"] == "OUTPUT"

    def test_multiple_splits_append_to_originals(self) -> None:
        """Multiple new splits are all appended after the original line items."""
        line_items = [
            {"TaxType": "BASEXCLUDED", "LineAmount": 158.50, "AccountCode": "449"},
        ]
        overrides = [
            _make_line_override(1, "INPUT", is_new_split=True, line_amount=Decimal("80.00")),
            _make_line_override(2, "BASEXCLUDED", is_new_split=True, line_amount=Decimal("78.50")),
        ]

        result, before, after = apply_overrides_to_line_items(line_items, overrides)

        assert len(result) == 3
        assert result[0]["TaxType"] == "BASEXCLUDED"
        assert result[1]["TaxType"] == "INPUT"
        assert result[2]["TaxType"] == "BASEXCLUDED"

    def test_delete_original_excludes_it_from_output(self) -> None:
        """is_new_split=False, is_deleted=True removes that original line item."""
        line_items = [
            {"TaxType": "INPUT", "LineAmount": 100.0},
            {"TaxType": "BASEXCLUDED", "LineAmount": 50.0},
        ]
        overrides = [_make_line_override(0, "INPUT", is_deleted=True)]

        result, before, after = apply_overrides_to_line_items(line_items, overrides)

        assert len(result) == 1
        assert result[0]["TaxType"] == "BASEXCLUDED"

    def test_edit_and_delete_composable(self) -> None:
        """Edit one original, delete another — result contains only the edited item."""
        line_items = [
            {"TaxType": "INPUT", "LineAmount": 100.0},
            {"TaxType": "BASEXCLUDED", "LineAmount": 50.0},
        ]
        overrides = [
            _make_line_override(0, "OUTPUT"),  # edit: change TaxType
            _make_line_override(1, "BASEXCLUDED", is_deleted=True),  # delete
        ]

        result, before, after = apply_overrides_to_line_items(line_items, overrides)

        assert len(result) == 1
        assert result[0]["TaxType"] == "OUTPUT"
        assert after["0"] == "OUTPUT"

    def test_new_split_appended_alongside_edit_and_delete(self) -> None:
        """Edit, delete, and add new split all compose correctly."""
        line_items = [
            {"TaxType": "INPUT", "LineAmount": 80.0, "AccountCode": "449"},
            {"TaxType": "BASEXCLUDED", "LineAmount": 78.50},
        ]
        overrides = [
            _make_line_override(0, "OUTPUT"),  # edit existing
            _make_line_override(1, "BASEXCLUDED", is_deleted=True),  # delete
            _make_line_override(2, "INPUT", is_new_split=True, line_amount=Decimal("50.00")),  # new
        ]

        result, before, after = apply_overrides_to_line_items(line_items, overrides)

        # Retained: edited item 0 + new split
        assert len(result) == 2
        assert result[0]["TaxType"] == "OUTPUT"
        assert result[1]["TaxType"] == "INPUT"
        assert result[1]["LineAmount"] == pytest.approx(50.0)

    def test_mixed_edit_and_new_split(self) -> None:
        """Both patch and split overrides compose — originals not discarded."""
        line_items = [
            {"TaxType": "INPUT", "LineAmount": 100.0},
            {"TaxType": "BASEXCLUDED", "LineAmount": 50.0},
        ]
        overrides = [
            _make_line_override(0, "OUTPUT"),  # patch existing
            _make_line_override(
                2, "EXEMPTEXPENSES", is_new_split=True, line_amount=Decimal("25.00")
            ),  # new split
        ]

        result, before, after = apply_overrides_to_line_items(line_items, overrides)

        assert len(result) == 3
        assert result[0]["TaxType"] == "OUTPUT"  # patched
        assert result[1]["TaxType"] == "BASEXCLUDED"  # unchanged original
        assert result[2]["TaxType"] == "EXEMPTEXPENSES"  # new split

    def test_original_line_items_not_mutated(self) -> None:
        """apply_overrides_to_line_items must deep-copy input — originals unchanged."""
        line_items = [{"TaxType": "INPUT", "LineAmount": 100.0}]
        overrides = [_make_line_override(0, "OUTPUT")]

        apply_overrides_to_line_items(line_items, overrides)

        assert line_items[0]["TaxType"] == "INPUT"

    def test_split_with_account_code(self) -> None:
        """line_account_code from split override is written to AccountCode on the new item."""
        line_items = [{"TaxType": "INPUT", "LineAmount": 200.0}]
        overrides = [
            _make_line_override(
                1,
                "OUTPUT",
                is_new_split=True,
                line_amount=Decimal("100.00"),
                line_account_code="400",
            )
        ]

        result, _, _ = apply_overrides_to_line_items(line_items, overrides)

        # Original retained + new split appended
        assert len(result) == 2
        assert result[1]["AccountCode"] == "400"

    def test_split_inherits_account_code_from_original(self) -> None:
        """When split has no explicit account code, inherits from first original line item."""
        line_items = [{"TaxType": "INPUT", "LineAmount": 200.0, "AccountCode": "449"}]
        overrides = [
            _make_line_override(1, "OUTPUT", is_new_split=True, line_amount=Decimal("100.00"))
        ]

        result, _, _ = apply_overrides_to_line_items(line_items, overrides)

        assert result[1]["AccountCode"] == "449"
