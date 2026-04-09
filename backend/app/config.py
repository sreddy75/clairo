"""Application configuration using Pydantic Settings.

This module provides type-safe configuration management with environment variable
loading and validation. All settings are cached for performance.

Usage:
    from app.config import get_settings
    settings = get_settings()
"""

import json
import os
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """PostgreSQL database configuration."""

    model_config = SettingsConfigDict(
        env_prefix="DATABASE_",
        env_file=(".env", ".env.local"),
        extra="ignore",
    )

    url: str = Field(
        default="postgresql+asyncpg://clairo:clairo_dev@localhost:5432/clairo",
        description="Full database URL for async SQLAlchemy connection",
    )
    pool_size: int = Field(default=3, ge=1, le=100, description="Connection pool size")
    max_overflow: int = Field(
        default=7, ge=0, le=100, description="Max connections above pool_size"
    )
    pool_timeout: int = Field(
        default=30, ge=1, le=300, description="Seconds to wait for connection"
    )
    pool_recycle: int = Field(
        default=1800, ge=60, le=7200, description="Seconds before connection recycle"
    )
    echo: bool = Field(default=False, description="Log all SQL statements")

    @field_validator("url", mode="after")
    @classmethod
    def ensure_asyncpg_driver(cls, v: str) -> str:
        """Ensure URL uses asyncpg driver for async SQLAlchemy.

        Railway provides postgresql:// URLs but we need postgresql+asyncpg://
        """
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v


class RedisSettings(BaseSettings):
    """Redis cache and broker configuration."""

    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        env_file=(".env", ".env.local"),
        extra="ignore",
    )

    url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    max_connections: int = Field(
        default=20, ge=1, le=100, description="Maximum connections in pool"
    )


class PineconeSettings(BaseSettings):
    """Pinecone vector database configuration."""

    model_config = SettingsConfigDict(
        env_prefix="PINECONE_",
        env_file=(".env", ".env.local"),
        extra="ignore",
    )

    api_key: SecretStr = Field(
        default=SecretStr(""),
        description="Pinecone API key",
    )
    environment: str = Field(
        default="",
        description="Pinecone environment (deprecated for serverless, kept for compatibility)",
    )
    index_host: str = Field(
        default="",
        description="Pinecone index host URL (for serverless indexes)",
    )


class VoyageSettings(BaseSettings):
    """Voyage AI embedding service configuration.

    Voyage AI provides high-quality text embeddings optimized for RAG retrieval.
    Uses voyage-3.5-lite model (512 dimensions) for best accuracy/cost ratio.
    """

    model_config = SettingsConfigDict(
        env_prefix="VOYAGE_",
        env_file=(".env", ".env.local"),
        extra="ignore",
    )

    api_key: SecretStr = Field(
        default=SecretStr(""),
        description="Voyage AI API key (get from voyageai.com)",
    )
    model: str = Field(
        default="voyage-3.5-lite",
        description="Embedding model to use",
    )
    dimensions: int = Field(
        default=1024,
        description="Vector dimensions for the chosen model",
    )
    batch_size: int = Field(
        default=128,
        ge=1,
        le=128,
        description="Max texts per embedding request (API limit is 128)",
    )
    timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="Request timeout in seconds",
    )


class MinioSettings(BaseSettings):
    """MinIO object storage configuration."""

    model_config = SettingsConfigDict(
        env_prefix="MINIO_",
        env_file=(".env", ".env.local"),
        extra="ignore",
    )

    endpoint: str = Field(default="localhost:9000", description="MinIO server endpoint (internal)")
    external_endpoint: str = Field(
        default="localhost:9000",
        description="MinIO endpoint for browser-accessible URLs (presigned URLs)",
    )
    access_key: str = Field(default="clairo", description="MinIO access key")
    secret_key: SecretStr = Field(default=SecretStr("clairo_dev"), description="MinIO secret key")
    bucket: str = Field(default="clairo-documents", description="Default bucket name")
    use_ssl: bool = Field(default=False, description="Use HTTPS for connection")


class CelerySettings(BaseSettings):
    """Celery background task configuration.

    On Railway, REDIS_URL is provided automatically. If CELERY_BROKER_URL
    is not explicitly set, broker_url and result_backend are derived from
    REDIS_URL with different database numbers (/1 and /2).
    """

    model_config = SettingsConfigDict(
        env_prefix="CELERY_",
        env_file=(".env", ".env.local"),
        extra="ignore",
    )

    broker_url: str = Field(default="", description="Celery broker URL")
    result_backend: str = Field(default="", description="Celery result backend URL")
    task_default_queue: str = Field(default="clairo-default", description="Default task queue name")
    task_time_limit: int = Field(
        default=3600, ge=1, description="Hard time limit for tasks (seconds)"
    )
    task_soft_time_limit: int = Field(
        default=3300, ge=1, description="Soft time limit for tasks (seconds)"
    )

    @staticmethod
    def _redis_url_with_db(base_url: str, db: int) -> str:
        """Append /db to a Redis URL, stripping any existing db number."""
        # Remove trailing slash and any existing /N db selector
        url = base_url.rstrip("/")
        # If URL ends with /digits, strip it
        parts = url.rsplit("/", 1)
        if len(parts) == 2 and parts[1].isdigit():
            url = parts[0]
        return f"{url}/{db}"

    @model_validator(mode="after")
    def derive_urls_from_redis(self) -> "CelerySettings":
        """Fall back to REDIS_URL when CELERY_BROKER_URL is not set."""
        redis_url = os.environ.get("REDIS_URL", "")

        if not self.broker_url:
            if redis_url:
                self.broker_url = self._redis_url_with_db(redis_url, 1)
            else:
                self.broker_url = "redis://localhost:6379/1"

        if not self.result_backend:
            if redis_url:
                self.result_backend = self._redis_url_with_db(redis_url, 2)
            else:
                self.result_backend = "redis://localhost:6379/2"

        return self


class SecuritySettings(BaseSettings):
    """Security and authentication configuration."""

    model_config = SettingsConfigDict(
        env_prefix="JWT_",
        env_file=(".env", ".env.local"),
        extra="ignore",
    )

    secret_key: SecretStr = Field(
        default=SecretStr("change-me-in-production-use-openssl-rand-hex-32"),
        description="JWT signing secret key",
    )
    algorithm: str = Field(default="HS256", description="JWT signing algorithm")
    access_token_expire_minutes: int = Field(
        default=30, ge=1, description="Access token expiration in minutes"
    )
    refresh_token_expire_days: int = Field(
        default=7, ge=1, description="Refresh token expiration in days"
    )


class ClerkSettings(BaseSettings):
    """Clerk authentication provider configuration.

    Clerk provides authentication infrastructure including JWT-based auth,
    MFA, and user management. This configuration enables integration with
    Clerk's API and JWKS validation.
    """

    model_config = SettingsConfigDict(
        env_prefix="CLERK_",
        env_file=(".env", ".env.local"),
        extra="ignore",
    )

    publishable_key: str = Field(
        default="pk_test_placeholder",
        description="Clerk publishable key (starts with pk_)",
    )
    secret_key: SecretStr = Field(
        default=SecretStr("sk_test_placeholder"),
        description="Clerk secret key (starts with sk_)",
    )
    jwks_url: str = Field(
        default="https://clerk.accounts.dev/.well-known/jwks.json",
        description="JWKS endpoint URL for token validation",
    )
    webhook_secret: SecretStr = Field(
        default=SecretStr("whsec_placeholder"),
        description="Webhook signing secret for Clerk events",
    )
    jwt_clock_skew_seconds: int = Field(
        default=60,
        ge=0,
        le=300,
        description="Clock skew tolerance for JWT validation (seconds)",
    )
    jwks_cache_ttl_seconds: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="JWKS cache time-to-live (seconds)",
    )


class ResendSettings(BaseSettings):
    """Resend email service configuration.

    Resend provides transactional email delivery with high deliverability.
    Used for welcome emails, invitations, and notifications.
    """

    model_config = SettingsConfigDict(
        env_prefix="RESEND_",
        env_file=(".env", ".env.local"),
        extra="ignore",
    )

    api_key: SecretStr = Field(
        default=SecretStr("re_placeholder"),
        description="Resend API key (starts with re_)",
    )
    from_email: str = Field(
        default="Clairo <noreply@clairo.com.au>",
        description="Default sender email address",
    )
    from_name: str = Field(
        default="Clairo",
        description="Default sender display name",
    )
    reply_to: str | None = Field(
        default=None,
        description="Reply-to email address",
    )
    enabled: bool = Field(
        default=True,
        description="Enable email sending (disable for testing)",
    )


class StripeSettings(BaseSettings):
    """Stripe payment processing configuration.

    Stripe provides payment infrastructure for subscriptions and billing.
    This configuration enables checkout, customer portal, and webhooks.
    """

    model_config = SettingsConfigDict(
        env_prefix="STRIPE_",
        env_file=(".env", ".env.local"),
        extra="ignore",
    )

    secret_key: SecretStr = Field(
        default=SecretStr("sk_test_placeholder"),
        description="Stripe secret key (starts with sk_)",
    )
    publishable_key: str = Field(
        default="pk_test_placeholder",
        description="Stripe publishable key (starts with pk_)",
    )
    webhook_secret: SecretStr = Field(
        default=SecretStr("whsec_placeholder"),
        description="Stripe webhook signing secret",
    )
    price_starter: str = Field(
        default="price_starter",
        description="Stripe price ID for Starter tier",
    )
    price_professional: str = Field(
        default="price_professional",
        description="Stripe price ID for Professional tier",
    )
    price_growth: str = Field(
        default="price_growth",
        description="Stripe price ID for Growth tier",
    )


class XeroSettings(BaseSettings):
    """Xero OAuth 2.0 integration configuration.

    Xero provides accounting software integration. This configuration enables
    OAuth 2.0 PKCE flow for secure authorization and API access.
    """

    model_config = SettingsConfigDict(
        env_prefix="XERO_",
        env_file=(".env", ".env.local"),
        extra="ignore",
    )

    client_id: str = Field(
        default="",
        description="Xero OAuth client ID",
    )
    client_secret: SecretStr | None = Field(
        default=None,
        description="Xero OAuth client secret (optional for PKCE)",
    )
    redirect_uri: str = Field(
        default="http://localhost:3000/settings/integrations/xero/callback",
        description="OAuth callback redirect URI",
    )
    scopes: str = Field(
        default="offline_access openid profile email accounting.settings accounting.transactions accounting.contacts accounting.journals.read accounting.reports.read payroll.employees payroll.payruns payroll.settings assets assets.read",
        description="OAuth scopes to request (includes payroll for PAYG, journals for audit trail, assets for fixed assets)",
    )
    authorization_url: str = Field(
        default="https://login.xero.com/identity/connect/authorize",
        description="Xero authorization endpoint",
    )
    token_url: str = Field(
        default="https://identity.xero.com/connect/token",
        description="Xero token exchange endpoint",
    )
    connections_url: str = Field(
        default="https://api.xero.com/connections",
        description="Xero connections endpoint",
    )
    revocation_url: str = Field(
        default="https://identity.xero.com/connect/revocation",
        description="Xero token revocation endpoint",
    )
    api_url: str = Field(
        default="https://api.xero.com/api.xro/2.0",
        description="Xero API base URL",
    )
    payroll_url: str = Field(
        default="https://api.xero.com/payroll.xro/2.0",
        description="Xero Payroll API base URL (AU)",
    )
    assets_url: str = Field(
        default="https://api.xero.com/assets.xro/1.0",
        description="Xero Assets API base URL",
    )
    max_concurrent_entity_syncs: int = Field(
        default=5,
        description=(
            "Maximum concurrent Xero entity sync tasks. Each entity sync may "
            "make multiple API calls (paginated), so this limits parallel load "
            "to stay within Xero's 60 calls/minute rate limit."
        ),
    )
    entity_sync_rate_limit: str = Field(
        default="10/m",
        description=(
            "Celery rate limit for the sync_entity task. Controls how many "
            "entity syncs a single worker processes per minute. Format: '10/m' "
            "means 10 per minute. Each entity sync may make multiple Xero API "
            "calls (paginated), so this should be conservative relative to "
            "Xero's 60 calls/minute limit."
        ),
    )
    webhook_key: str = Field(
        default="",
        description=(
            "Xero webhook signing key for HMAC-SHA256 signature verification. "
            "Obtained from the Xero Developer Portal when registering a webhook. "
            "Required for webhook endpoint to accept events."
        ),
    )
    phase_timeout_seconds: int = Field(
        default=1800,
        ge=60,
        le=7200,
        description=(
            "Timeout in seconds for each phase of the progressive sync. "
            "Default 1800 (30 min) matches Xero token lifetime. Increase for "
            "very large datasets."
        ),
    )

    @property
    def scopes_list(self) -> list[str]:
        """Get scopes as a list."""
        return self.scopes.split()

    @property
    def has_payroll_scopes(self) -> bool:
        """Check if payroll scopes are included."""
        payroll_scopes = ["payroll.employees", "payroll.payruns"]
        return all(scope in self.scopes_list for scope in payroll_scopes)

    @property
    def has_assets_scopes(self) -> bool:
        """Check if assets scopes are included."""
        return "assets" in self.scopes_list or "assets.read" in self.scopes_list


class TokenEncryptionSettings(BaseSettings):
    """Token encryption configuration for secure storage of OAuth tokens.

    Uses AES-256-GCM for encryption. The key must be a 32-byte value,
    base64 encoded for storage in environment variables.
    """

    model_config = SettingsConfigDict(
        env_prefix="TOKEN_ENCRYPTION_",
        env_file=(".env", ".env.local"),
        extra="ignore",
    )

    key: SecretStr = Field(
        default=SecretStr(""),  # Must be set in production
        description="Base64-encoded 32-byte encryption key",
    )

    @field_validator("key", mode="after")
    @classmethod
    def validate_key_if_set(cls, v: SecretStr) -> SecretStr:
        """Validate key length if set (skip validation for empty default)."""
        import base64

        key_value = v.get_secret_value()
        if key_value:
            try:
                decoded = base64.b64decode(key_value)
                if len(decoded) != 32:
                    raise ValueError("Token encryption key must be exactly 32 bytes when decoded")
            except Exception as e:
                if "32 bytes" not in str(e):
                    raise ValueError(f"Invalid base64 encoding for token encryption key: {e}")
                raise
        return v


class OpenAISettings(BaseSettings):
    """OpenAI configuration for Whisper transcription API."""

    model_config = SettingsConfigDict(
        env_prefix="OPENAI_",
        env_file=(".env", ".env.local"),
        extra="ignore",
    )

    api_key: SecretStr = Field(
        default=SecretStr(""),
        description="OpenAI API key for Whisper transcription",
    )


class AnthropicSettings(BaseSettings):
    """Anthropic Claude AI configuration for chatbot responses."""

    model_config = SettingsConfigDict(
        env_prefix="ANTHROPIC_",
        env_file=(".env", ".env.local"),
        extra="ignore",
    )

    api_key: SecretStr = Field(
        default=SecretStr(""),
        description="Anthropic API key (starts with sk-ant-)",
    )
    model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Claude model to use for chat responses",
    )
    max_tokens: int = Field(
        default=2048,
        ge=256,
        le=8192,
        description="Maximum tokens in response",
    )
    temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Response temperature (lower = more focused)",
    )


class SentrySettings(BaseSettings):
    """Sentry error tracking configuration.

    Sentry provides real-time error tracking and performance monitoring.
    """

    model_config = SettingsConfigDict(
        env_prefix="SENTRY_",
        env_file=(".env", ".env.local"),
        extra="ignore",
    )

    dsn: str = Field(
        default="",
        description="Sentry DSN for error tracking (leave empty to disable)",
    )
    traces_sample_rate: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Percentage of transactions to trace (0.1 = 10%)",
    )
    profiles_sample_rate: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Percentage of transactions to profile",
    )
    environment: str = Field(
        default="development",
        description="Sentry environment tag",
    )
    enabled: bool = Field(
        default=True,
        description="Enable Sentry (set to false for local dev)",
    )

    @property
    def is_configured(self) -> bool:
        """Check if Sentry is configured with a valid DSN."""
        return bool(self.dsn) and self.enabled


class PostHogSettings(BaseSettings):
    """PostHog product analytics configuration.

    PostHog provides product analytics, feature flags, and session recordings.
    """

    model_config = SettingsConfigDict(
        env_prefix="POSTHOG_",
        env_file=(".env", ".env.local"),
        extra="ignore",
    )

    api_key: str = Field(
        default="",
        description="PostHog project API key (phc_...)",
    )
    host: str = Field(
        default="https://app.posthog.com",
        description="PostHog host (use https://eu.posthog.com for EU)",
    )
    enabled: bool = Field(
        default=True,
        description="Enable PostHog analytics",
    )

    @property
    def is_configured(self) -> bool:
        """Check if PostHog is configured with a valid API key."""
        return bool(self.api_key) and self.enabled


class ATOSettings(BaseSettings):
    """ATO (Australian Taxation Office) configuration.

    Settings for tax-related features including instant asset write-off detection.
    Based on ATO small business instant asset write-off rules.
    """

    model_config = SettingsConfigDict(
        env_prefix="ATO_",
        env_file=(".env", ".env.local"),
        extra="ignore",
    )

    # Instant Asset Write-Off Thresholds (GST-exclusive)
    # Current threshold effective from 1 July 2023
    instant_write_off_threshold: int = Field(
        default=20000,
        ge=0,
        le=1000000,
        description="Instant asset write-off threshold in AUD (GST-exclusive)",
    )

    # Turnover threshold for small business eligibility
    small_business_turnover_threshold: int = Field(
        default=10000000,
        ge=0,
        description="Maximum turnover for small business instant write-off eligibility (AUD)",
    )

    # Financial year start month (1 = January, 7 = July for Australia)
    financial_year_start_month: int = Field(
        default=7,
        ge=1,
        le=12,
        description="Financial year start month (1-12, default 7 for Australia)",
    )

    # GST rate for threshold adjustment
    gst_rate: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description="GST rate for threshold adjustment (0.10 = 10%)",
    )


class CorsSettings(BaseSettings):
    """CORS (Cross-Origin Resource Sharing) configuration."""

    model_config = SettingsConfigDict(env_prefix="CORS_")

    # Store as string to avoid pydantic-settings parsing issues
    # Use validation_alias for env var mapping (CORS_ORIGINS -> origins_raw)
    origins_raw: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        validation_alias="CORS_ORIGINS",
        description="Comma-separated list of allowed origins",
    )
    allow_credentials: bool = Field(default=True, description="Allow credentials")
    allow_methods_raw: str = Field(
        default="*",
        validation_alias="CORS_ALLOW_METHODS",
    )
    allow_headers_raw: str = Field(
        default="*",
        validation_alias="CORS_ALLOW_HEADERS",
    )

    @property
    def origins(self) -> list[str]:
        """Parse origins from comma-separated or JSON string."""
        if self.origins_raw.startswith("["):
            try:
                return json.loads(self.origins_raw)
            except json.JSONDecodeError:
                pass
        return [o.strip() for o in self.origins_raw.split(",") if o.strip()]

    @property
    def allow_methods(self) -> list[str]:
        """Parse allow_methods from comma-separated string."""
        if self.allow_methods_raw == "*":
            return ["*"]
        return [m.strip() for m in self.allow_methods_raw.split(",") if m.strip()]

    @property
    def allow_headers(self) -> list[str]:
        """Parse allow_headers from comma-separated string."""
        if self.allow_headers_raw == "*":
            return ["*"]
        return [h.strip() for h in self.allow_headers_raw.split(",") if h.strip()]


class Settings(BaseSettings):
    """Main application settings.

    Settings are loaded from environment variables with optional .env file support.
    Nested settings classes handle specific configuration domains.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_name: str = Field(default="Clairo", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    environment: Literal["development", "staging", "production", "test"] = Field(
        default="development", description="Deployment environment"
    )
    debug: bool = Field(default=True, description="Enable debug mode")

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level"
    )
    log_format: Literal["json", "console"] = Field(
        default="console", description="Log output format"
    )

    # Nested settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    pinecone: PineconeSettings = Field(default_factory=PineconeSettings)
    voyage: VoyageSettings = Field(default_factory=VoyageSettings)
    minio: MinioSettings = Field(default_factory=MinioSettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    clerk: ClerkSettings = Field(default_factory=ClerkSettings)
    resend: ResendSettings = Field(default_factory=ResendSettings)
    stripe: StripeSettings = Field(default_factory=StripeSettings)
    xero: XeroSettings = Field(default_factory=XeroSettings)
    token_encryption: TokenEncryptionSettings = Field(default_factory=TokenEncryptionSettings)
    cors: CorsSettings = Field(default_factory=CorsSettings)
    anthropic: AnthropicSettings = Field(default_factory=AnthropicSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    sentry: SentrySettings = Field(default_factory=SentrySettings)
    posthog: PostHogSettings = Field(default_factory=PostHogSettings)
    ato: ATOSettings = Field(default_factory=ATOSettings)

    # Frontend URL for redirects
    frontend_url: str = Field(
        default="http://localhost:3000",
        description="Frontend URL for OAuth redirects and billing",
    )

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def stripe_webhook_secret(self) -> str:
        """Get Stripe webhook secret for signature verification."""
        return self.stripe.webhook_secret.get_secret_value()

    @property
    def stripe_price_starter(self) -> str:
        """Get Stripe price ID for Starter tier."""
        return self.stripe.price_starter

    @property
    def stripe_price_professional(self) -> str:
        """Get Stripe price ID for Professional tier."""
        return self.stripe.price_professional

    @property
    def stripe_price_growth(self) -> str:
        """Get Stripe price ID for Growth tier."""
        return self.stripe.price_growth


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Uses lru_cache to ensure settings are only loaded once and reused
    across the application.

    Returns:
        Settings: The application settings instance.
    """
    return Settings()
