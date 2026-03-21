"""Xero OAuth 2.0 PKCE flow utilities.

Provides functions for:
- PKCE code verifier and challenge generation
- State token generation
- Authorization URL building
"""

import base64
import hashlib
import secrets
from urllib.parse import urlencode

from app.config import XeroSettings


def generate_code_verifier() -> str:
    """Generate a PKCE code verifier.

    Per RFC 7636, the code verifier must be 43-128 characters,
    using only [A-Z], [a-z], [0-9], -, ., _, ~.

    Returns:
        A 43-character URL-safe base64 token (32 bytes of entropy).
    """
    return secrets.token_urlsafe(32)


def generate_code_challenge(verifier: str) -> str:
    """Generate PKCE code challenge from verifier.

    Uses SHA256 hash with base64url encoding (S256 method).

    Args:
        verifier: The code verifier string.

    Returns:
        Base64url-encoded SHA256 hash of the verifier.
    """
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    # Base64url encode without padding
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def generate_state() -> str:
    """Generate a secure random OAuth state parameter.

    Uses secrets.token_urlsafe which is cryptographically secure.

    Returns:
        A 43-character URL-safe base64 token (32 bytes of entropy).
    """
    return secrets.token_urlsafe(32)


def build_authorization_url(
    settings: XeroSettings,
    state: str,
    code_challenge: str,
    redirect_uri: str,
) -> str:
    """Build Xero OAuth authorization URL with PKCE.

    Args:
        settings: Xero configuration settings.
        state: CSRF protection state token.
        code_challenge: PKCE code challenge (S256).
        redirect_uri: Where Xero should redirect after authorization.

    Returns:
        Full authorization URL to redirect user to.
    """
    params = {
        "response_type": "code",
        "client_id": settings.client_id,
        "redirect_uri": redirect_uri,
        "scope": settings.scopes,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{settings.authorization_url}?{urlencode(params)}"
