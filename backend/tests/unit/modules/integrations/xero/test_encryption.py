"""Unit tests for token encryption.

Tests:
- Encrypt/decrypt round-trip
- Different input lengths
- Invalid key handling
- Tampered ciphertext detection
"""

import pytest

from app.modules.integrations.xero.encryption import TokenEncryption, TokenEncryptionError


class TestTokenEncryption:
    """Tests for TokenEncryption class."""

    @pytest.fixture
    def valid_key(self) -> str:
        """Generate a valid encryption key for testing."""
        return TokenEncryption.generate_key()

    @pytest.fixture
    def encryption(self, valid_key: str) -> TokenEncryption:
        """Create a TokenEncryption instance for testing."""
        return TokenEncryption(valid_key)

    def test_encrypt_decrypt_roundtrip(self, encryption: TokenEncryption) -> None:
        """Encrypted data should decrypt to original."""
        plaintext = "this_is_a_secret_access_token_12345"
        encrypted = encryption.encrypt(plaintext)
        decrypted = encryption.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_different_inputs(self, encryption: TokenEncryption) -> None:
        """Should handle various input types."""
        test_cases = [
            "short",
            "a" * 1000,  # long string
            "special!@#$%^&*()chars",
            "unicode_émojis_🔐",
            "newlines\n\tand\ttabs",
        ]
        for plaintext in test_cases:
            encrypted = encryption.encrypt(plaintext)
            decrypted = encryption.decrypt(encrypted)
            assert decrypted == plaintext, f"Failed for: {plaintext[:20]}..."

    def test_encrypt_produces_different_output(self, encryption: TokenEncryption) -> None:
        """Same input should produce different ciphertext (due to random nonce)."""
        plaintext = "same_token"
        encrypted1 = encryption.encrypt(plaintext)
        encrypted2 = encryption.encrypt(plaintext)
        # Different ciphertext
        assert encrypted1 != encrypted2
        # But both decrypt to same value
        assert encryption.decrypt(encrypted1) == plaintext
        assert encryption.decrypt(encrypted2) == plaintext

    def test_invalid_key_empty(self) -> None:
        """Should reject empty key."""
        with pytest.raises(TokenEncryptionError, match="cannot be empty"):
            TokenEncryption("")

    def test_invalid_key_wrong_length(self) -> None:
        """Should reject keys that aren't 32 bytes."""
        import base64

        # 16 bytes instead of 32
        short_key = base64.b64encode(b"x" * 16).decode()
        with pytest.raises(TokenEncryptionError, match="must be 32 bytes"):
            TokenEncryption(short_key)

        # 64 bytes instead of 32
        long_key = base64.b64encode(b"x" * 64).decode()
        with pytest.raises(TokenEncryptionError, match="must be 32 bytes"):
            TokenEncryption(long_key)

    def test_invalid_key_bad_base64(self) -> None:
        """Should reject invalid base64 encoding."""
        with pytest.raises(TokenEncryptionError, match="Invalid base64"):
            TokenEncryption("not-valid-base64!!!")

    def test_tampered_ciphertext_detection(self, encryption: TokenEncryption) -> None:
        """Should detect and reject tampered ciphertext."""
        plaintext = "secret_token"
        encrypted = encryption.encrypt(plaintext)

        # Tamper with the ciphertext (flip a bit in the middle)
        import base64

        raw = bytearray(base64.b64decode(encrypted))
        raw[len(raw) // 2] ^= 0xFF  # Flip all bits in one byte
        tampered = base64.b64encode(raw).decode()

        with pytest.raises(TokenEncryptionError, match="Decryption failed"):
            encryption.decrypt(tampered)

    def test_decrypt_empty_string(self, encryption: TokenEncryption) -> None:
        """Should reject empty encrypted string."""
        with pytest.raises(TokenEncryptionError, match="Cannot decrypt empty"):
            encryption.decrypt("")

    def test_encrypt_empty_string(self, encryption: TokenEncryption) -> None:
        """Should reject empty plaintext."""
        with pytest.raises(TokenEncryptionError, match="Cannot encrypt empty"):
            encryption.encrypt("")

    def test_decrypt_invalid_base64(self, encryption: TokenEncryption) -> None:
        """Should handle invalid base64 in encrypted data."""
        with pytest.raises(TokenEncryptionError, match="Decryption failed"):
            encryption.decrypt("not-valid-base64!!!")

    def test_decrypt_truncated_data(self, encryption: TokenEncryption) -> None:
        """Should reject truncated encrypted data."""
        import base64

        # Too short to contain nonce + tag
        short_data = base64.b64encode(b"x" * 10).decode()
        with pytest.raises(TokenEncryptionError, match="too short"):
            encryption.decrypt(short_data)

    def test_different_keys_cannot_decrypt(self, valid_key: str) -> None:
        """Data encrypted with one key cannot be decrypted with another."""
        encryption1 = TokenEncryption(valid_key)
        encryption2 = TokenEncryption(TokenEncryption.generate_key())

        plaintext = "secret"
        encrypted = encryption1.encrypt(plaintext)

        with pytest.raises(TokenEncryptionError, match="Decryption failed"):
            encryption2.decrypt(encrypted)

    def test_generate_key_produces_valid_keys(self) -> None:
        """Generated keys should be valid for encryption."""
        key = TokenEncryption.generate_key()
        encryption = TokenEncryption(key)
        plaintext = "test_token"
        encrypted = encryption.encrypt(plaintext)
        decrypted = encryption.decrypt(encrypted)
        assert decrypted == plaintext

    def test_generate_key_produces_unique_keys(self) -> None:
        """Each generated key should be unique."""
        keys = {TokenEncryption.generate_key() for _ in range(100)}
        assert len(keys) == 100  # All unique
