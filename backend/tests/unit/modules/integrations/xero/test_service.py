"""Unit tests for Xero services.

Tests:
- XeroOAuthService
- XeroConnectionService
"""

import pytest

# Tests will be implemented in US1-US3


class TestXeroOAuthService:
    """Tests for XeroOAuthService."""

    @pytest.mark.skip(reason="Implementation pending - US1 T017")
    def test_generate_auth_url_creates_valid_url(self) -> None:
        """Should generate valid Xero authorization URL."""
        pass

    @pytest.mark.skip(reason="Implementation pending - US1 T017")
    def test_generate_auth_url_stores_state(self) -> None:
        """Should store state with code_verifier."""
        pass

    @pytest.mark.skip(reason="Implementation pending - US1 T017")
    def test_handle_callback_validates_state(self) -> None:
        """Should validate state parameter."""
        pass

    @pytest.mark.skip(reason="Implementation pending - US1 T017")
    def test_handle_callback_exchanges_code(self) -> None:
        """Should exchange code for tokens."""
        pass


class TestXeroConnectionService:
    """Tests for XeroConnectionService."""

    @pytest.mark.skip(reason="Implementation pending - US2 T031")
    def test_list_connections(self) -> None:
        """Should list tenant's connections."""
        pass

    @pytest.mark.skip(reason="Implementation pending - US2 T031")
    def test_disconnect(self) -> None:
        """Should disconnect and revoke tokens."""
        pass

    @pytest.mark.skip(reason="Implementation pending - US3 T041")
    def test_refresh_tokens(self) -> None:
        """Should refresh tokens before expiry."""
        pass
