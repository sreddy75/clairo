"""Unit tests for document request templates.

Tests cover:
- System template definitions
- Template ID generation (deterministic)
- Template lookup functions

Spec: 030-client-portal-document-requests
"""

from uuid import UUID

from app.modules.portal.enums import RequestPriority
from app.modules.portal.requests.templates import (
    SYSTEM_TEMPLATES,
    SystemTemplate,
    _make_template_id,
    get_system_template_by_id,
    get_system_template_by_name,
    get_system_templates,
)


class TestSystemTemplates:
    """Tests for system template definitions."""

    def test_system_templates_not_empty(self) -> None:
        """System templates list is not empty."""
        assert len(SYSTEM_TEMPLATES) > 0

    def test_all_templates_have_unique_ids(self) -> None:
        """All system templates have unique IDs."""
        ids = [t.id for t in SYSTEM_TEMPLATES]
        assert len(ids) == len(set(ids))

    def test_all_templates_have_unique_names(self) -> None:
        """All system templates have unique names."""
        names = [t.name for t in SYSTEM_TEMPLATES]
        assert len(names) == len(set(names))

    def test_all_templates_have_required_fields(self) -> None:
        """All system templates have required fields."""
        for template in SYSTEM_TEMPLATES:
            assert isinstance(template.id, UUID)
            assert template.name
            assert template.description_template
            assert isinstance(template.expected_document_types, list)
            assert template.icon
            assert isinstance(template.default_priority, RequestPriority)
            assert template.default_due_days > 0

    def test_template_ids_are_deterministic(self) -> None:
        """Template IDs are generated deterministically from names."""
        # Same name should always generate same ID
        id1 = _make_template_id("bank-statements")
        id2 = _make_template_id("bank-statements")
        assert id1 == id2

        # Different names should generate different IDs
        id3 = _make_template_id("invoices")
        assert id1 != id3

    def test_bank_statements_template_exists(self) -> None:
        """Bank Statements template is properly defined."""
        template = get_system_template_by_name("Bank Statements")
        assert template is not None
        assert template.name == "Bank Statements"
        assert "bank_statement" in template.expected_document_types
        assert template.default_priority == RequestPriority.NORMAL

    def test_bas_supporting_template_is_high_priority(self) -> None:
        """BAS Supporting Documents template has high priority."""
        template = get_system_template_by_name("BAS Supporting Documents")
        assert template is not None
        assert template.default_priority == RequestPriority.HIGH
        assert template.default_due_days <= 7  # Should be quick turnaround

    def test_ato_correspondence_template_is_urgent(self) -> None:
        """ATO Correspondence template has urgent priority."""
        template = get_system_template_by_name("ATO Correspondence")
        assert template is not None
        assert template.default_priority == RequestPriority.URGENT
        assert template.default_due_days <= 3  # Very quick turnaround


class TestGetSystemTemplates:
    """Tests for get_system_templates function."""

    def test_returns_all_templates(self) -> None:
        """Returns all system templates."""
        templates = get_system_templates()
        assert templates == SYSTEM_TEMPLATES

    def test_returns_list_of_system_template(self) -> None:
        """Returns list of SystemTemplate objects."""
        templates = get_system_templates()
        assert all(isinstance(t, SystemTemplate) for t in templates)


class TestGetSystemTemplateById:
    """Tests for get_system_template_by_id function."""

    def test_returns_template_for_valid_id(self) -> None:
        """Returns template for valid ID."""
        expected = SYSTEM_TEMPLATES[0]
        result = get_system_template_by_id(expected.id)
        assert result == expected

    def test_returns_none_for_invalid_id(self) -> None:
        """Returns None for invalid ID."""
        from uuid import uuid4

        result = get_system_template_by_id(uuid4())
        assert result is None


class TestGetSystemTemplateByName:
    """Tests for get_system_template_by_name function."""

    def test_returns_template_for_valid_name(self) -> None:
        """Returns template for valid name."""
        result = get_system_template_by_name("Bank Statements")
        assert result is not None
        assert result.name == "Bank Statements"

    def test_case_insensitive(self) -> None:
        """Name lookup is case insensitive."""
        result1 = get_system_template_by_name("bank statements")
        result2 = get_system_template_by_name("BANK STATEMENTS")
        result3 = get_system_template_by_name("Bank Statements")

        assert result1 is not None
        assert result1 == result2 == result3

    def test_returns_none_for_invalid_name(self) -> None:
        """Returns None for invalid name."""
        result = get_system_template_by_name("Nonexistent Template")
        assert result is None


class TestSystemTemplateToDict:
    """Tests for SystemTemplate.to_dict method."""

    def test_converts_to_dict(self) -> None:
        """Converts template to dictionary."""
        template = SYSTEM_TEMPLATES[0]
        d = template.to_dict()

        assert d["id"] == template.id
        assert d["name"] == template.name
        assert d["description_template"] == template.description_template
        assert d["expected_document_types"] == template.expected_document_types
        assert d["icon"] == template.icon
        assert d["default_priority"] == template.default_priority.value
        assert d["default_due_days"] == template.default_due_days
        assert d["is_system"] is True
        assert d["is_active"] is True
        assert d["tenant_id"] is None
        assert d["created_by"] is None

    def test_priority_is_string_value(self) -> None:
        """Priority is converted to string value."""
        template = SYSTEM_TEMPLATES[0]
        d = template.to_dict()

        assert isinstance(d["default_priority"], str)
        assert d["default_priority"] in ["low", "normal", "high", "urgent"]


class TestTemplateDocumentTypes:
    """Tests for template expected document types."""

    def test_all_templates_have_document_types(self) -> None:
        """All templates have at least one expected document type."""
        for template in SYSTEM_TEMPLATES:
            assert len(template.expected_document_types) >= 1

    def test_document_types_are_strings(self) -> None:
        """All document types are strings."""
        for template in SYSTEM_TEMPLATES:
            for doc_type in template.expected_document_types:
                assert isinstance(doc_type, str)
                assert len(doc_type) > 0

    def test_document_types_are_snake_case(self) -> None:
        """Document types follow snake_case convention."""
        import re

        snake_case_pattern = re.compile(r"^[a-z][a-z0-9_]*$")

        for template in SYSTEM_TEMPLATES:
            for doc_type in template.expected_document_types:
                assert snake_case_pattern.match(doc_type), (
                    f"Document type '{doc_type}' in template '{template.name}' is not snake_case"
                )
