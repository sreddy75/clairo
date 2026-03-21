"""Token encryption for secure OAuth token storage.

Uses AES-256-GCM for authenticated encryption with:
- 256-bit key (32 bytes)
- 96-bit nonce (12 bytes) - unique per encryption
- 128-bit authentication tag for integrity

Storage format: base64(nonce + ciphertext + tag)
"""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class TokenEncryptionError(Exception):
    """Raised when token encryption/decryption fails."""

    pass


class TokenEncryption:
    """Encrypt/decrypt OAuth tokens using AES-256-GCM.

    Thread-safe: AESGCM is stateless after initialization.

    Example:
        encryption = TokenEncryption(key="base64_encoded_32_byte_key")
        encrypted = encryption.encrypt("secret_token")
        decrypted = encryption.decrypt(encrypted)
        assert decrypted == "secret_token"
    """

    NONCE_SIZE = 12  # 96 bits, recommended for GCM
    KEY_SIZE = 32  # 256 bits

    def __init__(self, key: str) -> None:
        """Initialize encryption with base64-encoded key.

        Args:
            key: Base64-encoded 32-byte (256-bit) encryption key.

        Raises:
            TokenEncryptionError: If key is invalid or wrong length.
        """
        if not key:
            raise TokenEncryptionError("Encryption key cannot be empty")

        try:
            self._key = base64.b64decode(key)
        except Exception as e:
            raise TokenEncryptionError(f"Invalid base64 encoding for key: {e}") from e

        if len(self._key) != self.KEY_SIZE:
            raise TokenEncryptionError(
                f"Encryption key must be {self.KEY_SIZE} bytes, got {len(self._key)}"
            )

        self._aesgcm = AESGCM(self._key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a token string.

        Uses a unique random nonce for each encryption, providing
        semantic security (same plaintext produces different ciphertext).

        Args:
            plaintext: The token to encrypt.

        Returns:
            Base64-encoded string containing nonce + ciphertext + tag.

        Raises:
            TokenEncryptionError: If encryption fails.
        """
        if not plaintext:
            raise TokenEncryptionError("Cannot encrypt empty string")

        try:
            # Generate unique nonce for this encryption
            nonce = os.urandom(self.NONCE_SIZE)

            # Encrypt (ciphertext includes authentication tag)
            ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

            # Combine nonce + ciphertext for storage
            combined = nonce + ciphertext

            # Base64 encode for safe string storage
            return base64.b64encode(combined).decode("utf-8")

        except Exception as e:
            raise TokenEncryptionError(f"Encryption failed: {e}") from e

    def decrypt(self, encrypted: str) -> str:
        """Decrypt an encrypted token string.

        Validates the authentication tag to detect tampering.

        Args:
            encrypted: Base64-encoded string from encrypt().

        Returns:
            The original plaintext token.

        Raises:
            TokenEncryptionError: If decryption fails or data is tampered.
        """
        if not encrypted:
            raise TokenEncryptionError("Cannot decrypt empty string")

        try:
            # Decode from base64
            combined = base64.b64decode(encrypted)

            if len(combined) < self.NONCE_SIZE + 16:  # 16 = min tag size
                raise TokenEncryptionError("Encrypted data too short")

            # Extract nonce and ciphertext
            nonce = combined[: self.NONCE_SIZE]
            ciphertext = combined[self.NONCE_SIZE :]

            # Decrypt and verify (raises InvalidTag if tampered)
            plaintext = self._aesgcm.decrypt(nonce, ciphertext, None)

            return plaintext.decode("utf-8")

        except TokenEncryptionError:
            raise
        except Exception as e:
            raise TokenEncryptionError(f"Decryption failed: {e}") from e

    @staticmethod
    def generate_key() -> str:
        """Generate a new random encryption key.

        Useful for initial setup and key rotation.

        Returns:
            Base64-encoded 32-byte key suitable for AES-256.
        """
        key = os.urandom(TokenEncryption.KEY_SIZE)
        return base64.b64encode(key).decode("utf-8")
