"""Xero API rate limiter.

Handles Xero's rate limiting:
- 60 requests per minute per tenant
- 5000 requests per day per tenant
- App-level minute limits

Provides utilities for:
- Parsing rate limit headers from responses
- Checking if requests are allowed
- Calculating wait times
- Exponential backoff for retries
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx


@dataclass
class RateLimitState:
    """Current rate limit state for a connection."""

    daily_remaining: int = 5000
    minute_remaining: int = 60
    app_minute_remaining: int | None = None
    retry_after: int | None = None
    last_updated: datetime | None = None
    rate_limited_until: datetime | None = None
    last_request_at: datetime | None = None

    @property
    def is_rate_limited(self) -> bool:
        """Check if currently rate limited."""
        if self.rate_limited_until is None:
            return False
        return datetime.now(UTC) < self.rate_limited_until

    @property
    def seconds_until_reset(self) -> int:
        """Get seconds until rate limit resets."""
        if self.rate_limited_until is None:
            return 0
        delta = self.rate_limited_until - datetime.now(UTC)
        return max(0, int(delta.total_seconds()))


class XeroRateLimiter:
    """Rate limiter for Xero API requests.

    Tracks rate limit state and determines when requests are allowed.

    Example:
        limiter = XeroRateLimiter()
        if limiter.can_make_request(state):
            response = await client.get(...)
            state = limiter.update_from_headers(state, response.headers)
        else:
            wait_time = limiter.get_wait_time(state)
            await asyncio.sleep(wait_time)
    """

    # Xero rate limit thresholds
    DAILY_LIMIT = 5000
    MINUTE_LIMIT = 60

    # Safety margins (stop before hitting absolute limit)
    DAILY_SAFETY_MARGIN = 100  # Stop 100 requests before daily limit
    MINUTE_SAFETY_MARGIN = 5  # Stop 5 requests before minute limit

    # Backoff settings
    MIN_BACKOFF_SECONDS = 1
    MAX_BACKOFF_SECONDS = 300  # 5 minutes max
    BACKOFF_BASE = 2

    def update_from_headers(
        self,
        state: RateLimitState,
        headers: httpx.Headers,
    ) -> RateLimitState:
        """Update rate limit state from response headers.

        Xero provides these headers:
        - X-DayLimit-Remaining: requests left today
        - X-MinLimit-Remaining: requests left this minute
        - X-AppMinLimit-Remaining: app-level minute limit
        - Retry-After: seconds to wait (on 429)

        Args:
            state: Current rate limit state.
            headers: Response headers from Xero.

        Returns:
            Updated rate limit state.
        """
        # Parse rate limit headers
        daily = headers.get("X-DayLimit-Remaining")
        minute = headers.get("X-MinLimit-Remaining")
        app_minute = headers.get("X-AppMinLimit-Remaining")
        retry_after = headers.get("Retry-After")

        # Update state
        if daily is not None:
            state.daily_remaining = int(daily)
        if minute is not None:
            state.minute_remaining = int(minute)
        if app_minute is not None:
            state.app_minute_remaining = int(app_minute)
        if retry_after is not None:
            state.retry_after = int(retry_after)
            state.rate_limited_until = datetime.now(UTC) + timedelta(seconds=int(retry_after))

        state.last_updated = datetime.now(UTC)
        return state

    def record_rate_limit_hit(
        self,
        state: RateLimitState,
        retry_after: int,
    ) -> RateLimitState:
        """Record a 429 rate limit response.

        Args:
            state: Current rate limit state.
            retry_after: Seconds from Retry-After header.

        Returns:
            Updated rate limit state.
        """
        state.retry_after = retry_after
        state.rate_limited_until = datetime.now(UTC) + timedelta(seconds=retry_after)
        state.last_updated = datetime.now(UTC)
        return state

    def can_make_request(self, state: RateLimitState) -> bool:
        """Check if a request can be made based on rate limits.

        Args:
            state: Current rate limit state.

        Returns:
            True if request is allowed, False if should wait.
        """
        # Check if currently in rate-limited state
        if state.is_rate_limited:
            return False

        # Check daily limit with safety margin
        if state.daily_remaining <= self.DAILY_SAFETY_MARGIN:
            return False

        # Check minute limit with safety margin
        if state.minute_remaining <= self.MINUTE_SAFETY_MARGIN:
            return False

        # Check app-level minute limit if available
        if state.app_minute_remaining is not None:
            if state.app_minute_remaining <= self.MINUTE_SAFETY_MARGIN:
                return False

        return True

    def get_wait_time(self, state: RateLimitState) -> int:
        """Get seconds to wait before next request.

        Args:
            state: Current rate limit state.

        Returns:
            Seconds to wait (0 if no wait needed).
        """
        # If rate limited, return time until reset
        if state.is_rate_limited:
            return state.seconds_until_reset

        # If minute limit approaching, wait until next minute
        if state.minute_remaining <= self.MINUTE_SAFETY_MARGIN:
            # Wait up to 60 seconds for minute limit reset
            return 60

        # If daily limit approaching, wait until midnight UTC
        if state.daily_remaining <= self.DAILY_SAFETY_MARGIN:
            now = datetime.now(UTC)
            midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
            midnight += timedelta(days=1)
            return int((midnight - now).total_seconds())

        return 0

    def calculate_backoff(self, attempt: int) -> int:
        """Calculate exponential backoff delay.

        Args:
            attempt: Attempt number (0-indexed).

        Returns:
            Seconds to wait before retry.
        """
        # Exponential backoff with jitter
        delay = self.MIN_BACKOFF_SECONDS * (self.BACKOFF_BASE**attempt)
        delay = min(delay, self.MAX_BACKOFF_SECONDS)
        return int(delay)

    def should_retry(self, status_code: int, attempt: int, max_attempts: int = 3) -> bool:
        """Determine if a request should be retried.

        Args:
            status_code: HTTP status code from response.
            attempt: Current attempt number (0-indexed).
            max_attempts: Maximum number of attempts.

        Returns:
            True if should retry, False otherwise.
        """
        if attempt >= max_attempts:
            return False

        # Retry on rate limits
        if status_code == 429:
            return True

        # Retry on server errors
        if 500 <= status_code < 600:
            return True

        # Don't retry on client errors (except 429)
        return False
