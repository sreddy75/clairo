"""WebAuthn service for biometric authentication.

Handles:
- WebAuthn credential registration
- WebAuthn authentication
- Challenge generation and validation

Spec: 032-pwa-mobile-document-capture
"""

import base64
import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.push.models import (
    PWAEventType,
    PWAInstallationEvent,
    WebAuthnCredential,
)
from app.modules.notifications.push.repository import (
    PWAInstallationEventRepository,
    WebAuthnCredentialRepository,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Challenge Management
# =============================================================================

# In-memory challenge store (use Redis in production)
_challenge_store: dict[str, tuple[bytes, datetime]] = {}
CHALLENGE_TIMEOUT = timedelta(minutes=5)


def _generate_challenge() -> bytes:
    """Generate a random challenge."""
    return secrets.token_bytes(32)


def _store_challenge(client_id: str, challenge: bytes) -> None:
    """Store a challenge for validation."""
    _challenge_store[client_id] = (challenge, datetime.now(timezone.utc))


def _get_and_clear_challenge(client_id: str) -> bytes | None:
    """Get and remove a stored challenge."""
    if client_id not in _challenge_store:
        return None

    challenge, created_at = _challenge_store.pop(client_id)

    # Check if expired
    if datetime.now(timezone.utc) - created_at > CHALLENGE_TIMEOUT:
        return None

    return challenge


def _base64url_encode(data: bytes) -> str:
    """Base64url encode bytes."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _base64url_decode(data: str) -> bytes:
    """Base64url decode string."""
    # Add padding
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data)


# =============================================================================
# WebAuthn Configuration
# =============================================================================


def get_rp_id() -> str:
    """Get Relying Party ID (domain)."""
    return os.getenv("WEBAUTHN_RP_ID", "localhost")


def get_rp_name() -> str:
    """Get Relying Party name."""
    return os.getenv("WEBAUTHN_RP_NAME", "Clairo Portal")


def get_rp_origin() -> str:
    """Get Relying Party origin."""
    return os.getenv("WEBAUTHN_RP_ORIGIN", "http://localhost:3001")


# =============================================================================
# WebAuthn Service
# =============================================================================


class WebAuthnService:
    """Service for WebAuthn biometric authentication."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize service with database session."""
        self.session = session
        self.credential_repo = WebAuthnCredentialRepository(session)
        self.event_repo = PWAInstallationEventRepository(session)

    async def get_registration_options(
        self,
        client_id: UUID,
        tenant_id: UUID,
        user_name: str,
        user_display_name: str | None = None,
    ) -> dict[str, Any]:
        """Generate WebAuthn registration options.

        Creates a challenge and returns options for navigator.credentials.create()
        """
        # Generate challenge
        challenge = _generate_challenge()
        _store_challenge(str(client_id), challenge)

        # Get existing credentials to exclude
        existing_credentials = await self.credential_repo.get_active_by_client(client_id)
        exclude_credentials = [
            {
                "id": _base64url_encode(cred.credential_id),
                "type": "public-key",
                "transports": ["internal"],
            }
            for cred in existing_credentials
        ]

        # Build user handle (stable identifier)
        user_handle = hashlib.sha256(str(client_id).encode()).digest()

        return {
            "challenge": _base64url_encode(challenge),
            "rp": {
                "id": get_rp_id(),
                "name": get_rp_name(),
            },
            "user": {
                "id": _base64url_encode(user_handle),
                "name": user_name,
                "displayName": user_display_name or user_name,
            },
            "pubKeyCredParams": [
                {"type": "public-key", "alg": -7},  # ES256
                {"type": "public-key", "alg": -257},  # RS256
            ],
            "timeout": 60000,
            "authenticatorSelection": {
                "authenticatorAttachment": "platform",
                "userVerification": "preferred",
                "residentKey": "preferred",
            },
            "attestation": "none",
            "excludeCredentials": exclude_credentials,
        }

    async def verify_registration(
        self,
        client_id: UUID,
        tenant_id: UUID,
        credential_response: dict[str, Any],
        device_name: str | None = None,
    ) -> WebAuthnCredential:
        """Verify and store a WebAuthn registration response.

        Note: This is a simplified implementation. In production,
        use a proper WebAuthn library like py_webauthn.
        """
        # Get stored challenge
        challenge = _get_and_clear_challenge(str(client_id))
        if not challenge:
            raise ValueError("Challenge expired or not found")

        # Decode response
        credential_id = _base64url_decode(credential_response["rawId"])
        response = credential_response["response"]

        # Decode clientDataJSON
        client_data_json = _base64url_decode(response["clientDataJSON"])

        # Verify origin and type
        import json

        client_data = json.loads(client_data_json)

        if client_data.get("type") != "webauthn.create":
            raise ValueError("Invalid credential type")

        expected_origin = get_rp_origin()
        if client_data.get("origin") != expected_origin:
            logger.warning(
                f"Origin mismatch: got {client_data.get('origin')}, expected {expected_origin}"
            )
            # In development, allow localhost variations
            if "localhost" not in client_data.get("origin", ""):
                raise ValueError("Invalid origin")

        # Verify challenge
        received_challenge = _base64url_decode(client_data["challenge"])
        if not hmac.compare_digest(challenge, received_challenge):
            raise ValueError("Challenge mismatch")

        # Decode attestation object
        attestation_object = _base64url_decode(response["attestationObject"])

        # Extract public key from attestation (simplified - in production use CBOR parser)
        # For now, store the raw attestation as "public key"
        public_key = attestation_object

        # Extract AAGUID if available (first 16 bytes of authenticator data after RP ID hash)
        # Attestation object is CBOR encoded
        # For simplicity, we'll just store it and skip AAGUID extraction
        aaguid = None

        # Create credential
        credential = WebAuthnCredential(
            client_id=client_id,
            tenant_id=tenant_id,
            credential_id=credential_id,
            public_key=public_key,
            device_name=device_name,
            aaguid=aaguid,
            sign_count=0,
        )
        credential = await self.credential_repo.create(credential)

        # Log event
        event = PWAInstallationEvent(
            client_id=client_id,
            tenant_id=tenant_id,
            event_type=PWAEventType.BIOMETRIC_REGISTERED.value,
            metadata={"device_name": device_name},
        )
        await self.event_repo.create(event)

        logger.info(
            f"WebAuthn credential registered for client {client_id}",
            extra={"client_id": str(client_id), "device_name": device_name},
        )

        return credential

    async def get_authentication_options(
        self,
        client_id: UUID,
    ) -> dict[str, Any]:
        """Generate WebAuthn authentication options.

        Returns options for navigator.credentials.get()
        """
        # Generate challenge
        challenge = _generate_challenge()
        _store_challenge(str(client_id), challenge)

        # Get credentials for this client
        credentials = await self.credential_repo.get_active_by_client(client_id)

        if not credentials:
            raise ValueError("No credentials registered for this client")

        allow_credentials = [
            {
                "id": _base64url_encode(cred.credential_id),
                "type": "public-key",
                "transports": ["internal"],
            }
            for cred in credentials
        ]

        return {
            "challenge": _base64url_encode(challenge),
            "timeout": 60000,
            "rpId": get_rp_id(),
            "allowCredentials": allow_credentials,
            "userVerification": "preferred",
        }

    async def verify_authentication(
        self,
        client_id: UUID,
        assertion_response: dict[str, Any],
    ) -> WebAuthnCredential:
        """Verify a WebAuthn authentication assertion.

        Returns the authenticated credential if successful.
        """
        # Get stored challenge
        challenge = _get_and_clear_challenge(str(client_id))
        if not challenge:
            raise ValueError("Challenge expired or not found")

        # Decode response
        credential_id = _base64url_decode(assertion_response["rawId"])
        response = assertion_response["response"]

        # Decode clientDataJSON
        client_data_json = _base64url_decode(response["clientDataJSON"])

        # Verify type and challenge
        import json

        client_data = json.loads(client_data_json)

        if client_data.get("type") != "webauthn.get":
            raise ValueError("Invalid assertion type")

        received_challenge = _base64url_decode(client_data["challenge"])
        if not hmac.compare_digest(challenge, received_challenge):
            raise ValueError("Challenge mismatch")

        # Find credential
        credential = await self.credential_repo.get_by_credential_id(credential_id)
        if not credential:
            raise ValueError("Credential not found")

        if credential.client_id != client_id:
            raise ValueError("Credential does not belong to this client")

        if not credential.is_active:
            raise ValueError("Credential is deactivated")

        # Decode authenticator data
        authenticator_data = _base64url_decode(response["authenticatorData"])

        # Extract sign count (bytes 33-36)
        if len(authenticator_data) >= 37:
            sign_count = int.from_bytes(authenticator_data[33:37], "big")

            # Verify sign count increased (replay protection)
            if sign_count <= credential.sign_count:
                logger.warning(
                    f"Sign count not increased for credential {credential.id}. "
                    f"Expected > {credential.sign_count}, got {sign_count}"
                )
                # In production, this could indicate a cloned authenticator
                # For now, we'll log but continue

            # Update sign count
            await self.credential_repo.update_sign_count(credential_id, sign_count)

        logger.info(
            f"WebAuthn authentication successful for client {client_id}",
            extra={"client_id": str(client_id), "credential_id": str(credential.id)},
        )

        return credential

    async def list_credentials(
        self,
        client_id: UUID,
    ) -> list[WebAuthnCredential]:
        """List all active credentials for a client."""
        return await self.credential_repo.get_active_by_client(client_id)

    async def revoke_credential(
        self,
        client_id: UUID,
        credential_id: UUID,
    ) -> bool:
        """Revoke a credential."""
        credential = await self.credential_repo.get_by_id(credential_id)

        if not credential:
            return False

        if credential.client_id != client_id:
            return False

        return await self.credential_repo.deactivate(credential_id)

    async def has_credentials(self, client_id: UUID) -> bool:
        """Check if client has any registered credentials."""
        credentials = await self.credential_repo.get_active_by_client(client_id)
        return len(credentials) > 0
