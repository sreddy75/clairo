"""Unit tests for Xero OAuth PKCE utilities.

Tests:
- Code verifier generation
- Code challenge computation
- State generation
- Authorization URL building
"""

import base64
import hashlib
import re
from unittest.mock import MagicMock

import pytest

from app.modules.integrations.xero.oauth import (
    build_authorization_url,
    generate_code_challenge,
    generate_code_verifier,
    generate_state,
)


class TestGenerateCodeVerifier:
    """Tests for generate_code_verifier function."""

    def test_returns_string(self) -> None:
        """Should return a string."""
        verifier = generate_code_verifier()
        assert isinstance(verifier, str)

    def test_length_is_correct(self) -> None:
        """Should be 43 characters (base64url of 32 bytes)."""
        verifier = generate_code_verifier()
        assert len(verifier) == 43

    def test_is_url_safe(self) -> None:
        """Should only contain URL-safe characters."""
        verifier = generate_code_verifier()
        # URL-safe base64 uses A-Z, a-z, 0-9, -, _
        assert re.match(r"^[A-Za-z0-9_-]+$", verifier)

    def test_is_unique(self) -> None:
        """Each call should generate a unique verifier."""
        verifiers = {generate_code_verifier() for _ in range(100)}
        assert len(verifiers) == 100  # All unique


class TestGenerateCodeChallenge:
    """Tests for generate_code_challenge function."""

    def test_returns_string(self) -> None:
        """Should return a string."""
        verifier = generate_code_verifier()
        challenge = generate_code_challenge(verifier)
        assert isinstance(challenge, str)

    def test_is_base64url_encoded(self) -> None:
        """Should be base64url encoded without padding."""
        verifier = generate_code_verifier()
        challenge = generate_code_challenge(verifier)
        # Should not have padding characters
        assert "=" not in challenge
        # Should only contain base64url characters
        assert re.match(r"^[A-Za-z0-9_-]+$", challenge)

    def test_is_sha256_hash(self) -> None:
        """Should be SHA256 hash of verifier."""
        verifier = "test_verifier_12345"
        challenge = generate_code_challenge(verifier)

        # Manually compute expected hash
        expected_hash = hashlib.sha256(verifier.encode("ascii")).digest()
        expected_challenge = base64.urlsafe_b64encode(expected_hash).decode("ascii").rstrip("=")

        assert challenge == expected_challenge

    def test_same_verifier_produces_same_challenge(self) -> None:
        """Same verifier should always produce same challenge."""
        verifier = generate_code_verifier()
        challenge1 = generate_code_challenge(verifier)
        challenge2 = generate_code_challenge(verifier)
        assert challenge1 == challenge2

    def test_different_verifiers_produce_different_challenges(self) -> None:
        """Different verifiers should produce different challenges."""
        verifier1 = "verifier_one"
        verifier2 = "verifier_two"
        challenge1 = generate_code_challenge(verifier1)
        challenge2 = generate_code_challenge(verifier2)
        assert challenge1 != challenge2


class TestGenerateState:
    """Tests for generate_state function."""

    def test_returns_string(self) -> None:
        """Should return a string."""
        state = generate_state()
        assert isinstance(state, str)

    def test_length_is_correct(self) -> None:
        """Should be 43 characters (base64url of 32 bytes)."""
        state = generate_state()
        assert len(state) == 43

    def test_is_url_safe(self) -> None:
        """Should only contain URL-safe characters."""
        state = generate_state()
        assert re.match(r"^[A-Za-z0-9_-]+$", state)

    def test_is_unique(self) -> None:
        """Each call should generate a unique state."""
        states = {generate_state() for _ in range(100)}
        assert len(states) == 100  # All unique


class TestBuildAuthorizationUrl:
    """Tests for build_authorization_url function."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock Xero settings."""
        settings = MagicMock()
        settings.client_id = "test_client_id"
        settings.authorization_url = "https://login.xero.com/identity/connect/authorize"
        settings.scopes = "openid profile email offline_access"
        return settings

    def test_returns_string(self, mock_settings: MagicMock) -> None:
        """Should return a string."""
        url = build_authorization_url(
            settings=mock_settings,
            state="test_state",
            code_challenge="test_challenge",
            redirect_uri="http://localhost:3000/callback",
        )
        assert isinstance(url, str)

    def test_includes_base_url(self, mock_settings: MagicMock) -> None:
        """Should start with the authorization URL."""
        url = build_authorization_url(
            settings=mock_settings,
            state="test_state",
            code_challenge="test_challenge",
            redirect_uri="http://localhost:3000/callback",
        )
        assert url.startswith("https://login.xero.com/identity/connect/authorize?")

    def test_includes_response_type(self, mock_settings: MagicMock) -> None:
        """Should include response_type=code."""
        url = build_authorization_url(
            settings=mock_settings,
            state="test_state",
            code_challenge="test_challenge",
            redirect_uri="http://localhost:3000/callback",
        )
        assert "response_type=code" in url

    def test_includes_client_id(self, mock_settings: MagicMock) -> None:
        """Should include the client ID."""
        url = build_authorization_url(
            settings=mock_settings,
            state="test_state",
            code_challenge="test_challenge",
            redirect_uri="http://localhost:3000/callback",
        )
        assert "client_id=test_client_id" in url

    def test_includes_redirect_uri(self, mock_settings: MagicMock) -> None:
        """Should include the redirect URI (URL encoded)."""
        url = build_authorization_url(
            settings=mock_settings,
            state="test_state",
            code_challenge="test_challenge",
            redirect_uri="http://localhost:3000/callback",
        )
        # URL-encoded redirect_uri
        assert "redirect_uri=http%3A%2F%2Flocalhost%3A3000%2Fcallback" in url

    def test_includes_scope(self, mock_settings: MagicMock) -> None:
        """Should include the scopes."""
        url = build_authorization_url(
            settings=mock_settings,
            state="test_state",
            code_challenge="test_challenge",
            redirect_uri="http://localhost:3000/callback",
        )
        # Scopes are URL-encoded (spaces become +)
        assert "scope=openid" in url or "scope=openid+profile" in url

    def test_includes_state(self, mock_settings: MagicMock) -> None:
        """Should include the state parameter."""
        url = build_authorization_url(
            settings=mock_settings,
            state="unique_state_token",
            code_challenge="test_challenge",
            redirect_uri="http://localhost:3000/callback",
        )
        assert "state=unique_state_token" in url

    def test_includes_code_challenge(self, mock_settings: MagicMock) -> None:
        """Should include the code challenge."""
        url = build_authorization_url(
            settings=mock_settings,
            state="test_state",
            code_challenge="unique_challenge",
            redirect_uri="http://localhost:3000/callback",
        )
        assert "code_challenge=unique_challenge" in url

    def test_includes_code_challenge_method(self, mock_settings: MagicMock) -> None:
        """Should include code_challenge_method=S256."""
        url = build_authorization_url(
            settings=mock_settings,
            state="test_state",
            code_challenge="test_challenge",
            redirect_uri="http://localhost:3000/callback",
        )
        assert "code_challenge_method=S256" in url

    def test_full_pkce_flow_integration(self, mock_settings: MagicMock) -> None:
        """Integration test: full PKCE flow should produce valid URL."""
        # Generate PKCE parameters
        verifier = generate_code_verifier()
        challenge = generate_code_challenge(verifier)
        state = generate_state()

        # Build URL
        url = build_authorization_url(
            settings=mock_settings,
            state=state,
            code_challenge=challenge,
            redirect_uri="http://localhost:3000/callback",
        )

        # Verify all components are present
        assert "response_type=code" in url
        assert "client_id=test_client_id" in url
        assert f"state={state}" in url
        assert f"code_challenge={challenge}" in url
        assert "code_challenge_method=S256" in url
