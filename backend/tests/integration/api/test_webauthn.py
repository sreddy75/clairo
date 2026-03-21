"""Integration tests for WebAuthn endpoints.

Tests the biometric authentication flow:
- Registration options
- Registration verification
- Authentication options
- Authentication verification
- Credential management

Spec: 032-pwa-mobile-document-capture
"""

import base64
import json
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_webauthn_registration_response():
    """Mock WebAuthn registration response from browser."""
    # This is a simplified mock - real responses are more complex
    client_data = {
        "type": "webauthn.create",
        "challenge": "",  # Will be filled in
        "origin": "http://localhost:3000",
    }

    return {
        "id": base64.urlsafe_b64encode(b"test-credential-id").decode().rstrip("="),
        "rawId": base64.urlsafe_b64encode(b"test-credential-id").decode().rstrip("="),
        "type": "public-key",
        "response": {
            "clientDataJSON": "",  # Will be filled in
            "attestationObject": base64.urlsafe_b64encode(b"mock-attestation").decode().rstrip("="),
        },
    }


@pytest.fixture
def mock_webauthn_authentication_response():
    """Mock WebAuthn authentication response from browser."""
    return {
        "id": base64.urlsafe_b64encode(b"test-credential-id").decode().rstrip("="),
        "rawId": base64.urlsafe_b64encode(b"test-credential-id").decode().rstrip("="),
        "type": "public-key",
        "response": {
            "clientDataJSON": "",  # Will be filled in
            "authenticatorData": base64.urlsafe_b64encode(b"\x00" * 37).decode().rstrip("="),
            "signature": base64.urlsafe_b64encode(b"mock-signature").decode().rstrip("="),
        },
    }


# =============================================================================
# Biometric Status Tests
# =============================================================================


class TestBiometricStatus:
    """Tests for GET /portal/push/webauthn/status"""

    async def test_status_no_credentials(
        self,
        client: AsyncClient,
        portal_auth_headers: dict,
    ):
        """Test status when no credentials registered."""
        response = await client.get(
            "/api/v1/portal/push/webauthn/status",
            headers=portal_auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["has_credentials"] is False
        assert data["credential_count"] == 0

    async def test_status_requires_auth(self, client: AsyncClient):
        """Test that status endpoint requires authentication."""
        response = await client.get("/api/v1/portal/push/webauthn/status")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# Registration Tests
# =============================================================================


class TestWebAuthnRegistration:
    """Tests for WebAuthn registration flow."""

    async def test_get_registration_options(
        self,
        client: AsyncClient,
        portal_auth_headers: dict,
    ):
        """Test getting registration options."""
        response = await client.post(
            "/api/v1/portal/push/webauthn/register/options",
            headers=portal_auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify required fields
        assert "challenge" in data
        assert "rp" in data
        assert "user" in data
        assert "pubKeyCredParams" in data
        assert "timeout" in data
        assert "authenticatorSelection" in data

        # Verify RP info
        assert "id" in data["rp"]
        assert "name" in data["rp"]

        # Verify user info
        assert "id" in data["user"]
        assert "name" in data["user"]
        assert "displayName" in data["user"]

        # Verify authenticator selection
        assert data["authenticatorSelection"]["authenticatorAttachment"] == "platform"
        assert data["authenticatorSelection"]["userVerification"] == "preferred"

    async def test_registration_options_requires_auth(self, client: AsyncClient):
        """Test that registration options require authentication."""
        response = await client.post("/api/v1/portal/push/webauthn/register/options")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_verify_registration_invalid_challenge(
        self,
        client: AsyncClient,
        portal_auth_headers: dict,
        mock_webauthn_registration_response: dict,
    ):
        """Test registration verification with invalid challenge."""
        # Create mock client data with wrong challenge
        client_data = {
            "type": "webauthn.create",
            "challenge": base64.urlsafe_b64encode(b"wrong-challenge").decode().rstrip("="),
            "origin": "http://localhost:3000",
        }
        mock_webauthn_registration_response["response"]["clientDataJSON"] = (
            base64.urlsafe_b64encode(json.dumps(client_data).encode()).decode().rstrip("=")
        )

        response = await client.post(
            "/api/v1/portal/push/webauthn/register/verify",
            headers=portal_auth_headers,
            json={
                "credential": mock_webauthn_registration_response,
                "device_name": "Test Device",
            },
        )

        # Should fail because challenge doesn't match
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# Credential Management Tests
# =============================================================================


class TestCredentialManagement:
    """Tests for credential listing and deletion."""

    async def test_list_credentials_empty(
        self,
        client: AsyncClient,
        portal_auth_headers: dict,
    ):
        """Test listing credentials when none exist."""
        response = await client.get(
            "/api/v1/portal/push/webauthn/credentials",
            headers=portal_auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["credentials"] == []
        assert data["count"] == 0

    async def test_delete_nonexistent_credential(
        self,
        client: AsyncClient,
        portal_auth_headers: dict,
    ):
        """Test deleting a credential that doesn't exist."""
        response = await client.delete(
            f"/api/v1/portal/push/webauthn/credentials/{uuid4()}",
            headers=portal_auth_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


# =============================================================================
# Authentication Tests
# =============================================================================


class TestWebAuthnAuthentication:
    """Tests for WebAuthn authentication flow."""

    async def test_get_authentication_options_no_credentials(
        self,
        client: AsyncClient,
        portal_auth_headers: dict,
    ):
        """Test getting authentication options when no credentials registered."""
        response = await client.post(
            "/api/v1/portal/push/webauthn/authenticate/options",
            headers=portal_auth_headers,
        )

        # Should fail because no credentials exist
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "No credentials" in response.json()["detail"]

    async def test_authentication_requires_auth(self, client: AsyncClient):
        """Test that authentication options require session auth."""
        response = await client.post("/api/v1/portal/push/webauthn/authenticate/options")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# Integration Flow Tests
# =============================================================================


class TestWebAuthnIntegrationFlow:
    """End-to-end integration tests for WebAuthn flow."""

    async def test_full_registration_flow_structure(
        self,
        client: AsyncClient,
        portal_auth_headers: dict,
    ):
        """Test the structure of the registration flow."""
        # 1. Get registration options
        options_response = await client.post(
            "/api/v1/portal/push/webauthn/register/options",
            headers=portal_auth_headers,
        )

        assert options_response.status_code == status.HTTP_200_OK
        options = options_response.json()

        # 2. Verify options have correct structure for browser API
        assert len(options["challenge"]) > 0
        assert options["rp"]["id"] is not None
        assert options["user"]["id"] is not None
        assert len(options["pubKeyCredParams"]) > 0

        # Each pubKeyCredParams should have type and alg
        for param in options["pubKeyCredParams"]:
            assert param["type"] == "public-key"
            assert "alg" in param

    async def test_status_after_operations(
        self,
        client: AsyncClient,
        portal_auth_headers: dict,
    ):
        """Test that status correctly reflects credential state."""
        # Initial status should show no credentials
        status_response = await client.get(
            "/api/v1/portal/push/webauthn/status",
            headers=portal_auth_headers,
        )

        assert status_response.status_code == status.HTTP_200_OK
        assert status_response.json()["has_credentials"] is False

        # After getting registration options, status should still be false
        # (registration not completed)
        await client.post(
            "/api/v1/portal/push/webauthn/register/options",
            headers=portal_auth_headers,
        )

        status_response = await client.get(
            "/api/v1/portal/push/webauthn/status",
            headers=portal_auth_headers,
        )

        assert status_response.json()["has_credentials"] is False
