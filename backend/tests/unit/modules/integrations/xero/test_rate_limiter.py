"""Unit tests for Xero rate limiter.

Tests:
- Header parsing
- Request allowance checking
- Wait time calculation
- Exponential backoff
"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.modules.integrations.xero.rate_limiter import RateLimitState, XeroRateLimiter


class TestRateLimitState:
    """Tests for RateLimitState dataclass."""

    def test_default_values(self) -> None:
        """Should have sensible defaults."""
        state = RateLimitState()
        assert state.daily_remaining == 5000
        assert state.minute_remaining == 60
        assert state.app_minute_remaining is None
        assert state.retry_after is None
        assert state.is_rate_limited is False

    def test_is_rate_limited_when_not_limited(self) -> None:
        """Should return False when not rate limited."""
        state = RateLimitState()
        assert state.is_rate_limited is False

    def test_is_rate_limited_when_limited(self) -> None:
        """Should return True when rate limited."""
        state = RateLimitState(rate_limited_until=datetime.now(UTC) + timedelta(seconds=60))
        assert state.is_rate_limited is True

    def test_is_rate_limited_when_expired(self) -> None:
        """Should return False when rate limit expired."""
        state = RateLimitState(rate_limited_until=datetime.now(UTC) - timedelta(seconds=1))
        assert state.is_rate_limited is False

    def test_seconds_until_reset_when_not_limited(self) -> None:
        """Should return 0 when not rate limited."""
        state = RateLimitState()
        assert state.seconds_until_reset == 0

    def test_seconds_until_reset_when_limited(self) -> None:
        """Should return remaining seconds when rate limited."""
        state = RateLimitState(rate_limited_until=datetime.now(UTC) + timedelta(seconds=30))
        # Allow some margin for test execution time
        assert 28 <= state.seconds_until_reset <= 30


class TestXeroRateLimiter:
    """Tests for XeroRateLimiter class."""

    @pytest.fixture
    def limiter(self) -> XeroRateLimiter:
        """Create a rate limiter instance."""
        return XeroRateLimiter()

    @pytest.fixture
    def fresh_state(self) -> RateLimitState:
        """Create a fresh rate limit state."""
        return RateLimitState()

    def test_update_from_headers_daily(self, limiter: XeroRateLimiter) -> None:
        """Should parse X-DayLimit-Remaining header."""
        state = RateLimitState()
        headers = httpx.Headers({"X-DayLimit-Remaining": "4500"})

        state = limiter.update_from_headers(state, headers)

        assert state.daily_remaining == 4500

    def test_update_from_headers_minute(self, limiter: XeroRateLimiter) -> None:
        """Should parse X-MinLimit-Remaining header."""
        state = RateLimitState()
        headers = httpx.Headers({"X-MinLimit-Remaining": "45"})

        state = limiter.update_from_headers(state, headers)

        assert state.minute_remaining == 45

    def test_update_from_headers_app_minute(self, limiter: XeroRateLimiter) -> None:
        """Should parse X-AppMinLimit-Remaining header."""
        state = RateLimitState()
        headers = httpx.Headers({"X-AppMinLimit-Remaining": "9500"})

        state = limiter.update_from_headers(state, headers)

        assert state.app_minute_remaining == 9500

    def test_update_from_headers_retry_after(self, limiter: XeroRateLimiter) -> None:
        """Should parse Retry-After header and set rate_limited_until."""
        state = RateLimitState()
        headers = httpx.Headers({"Retry-After": "60"})

        state = limiter.update_from_headers(state, headers)

        assert state.retry_after == 60
        assert state.is_rate_limited is True
        assert 58 <= state.seconds_until_reset <= 60

    def test_update_from_headers_all(self, limiter: XeroRateLimiter) -> None:
        """Should parse all headers together."""
        state = RateLimitState()
        headers = httpx.Headers(
            {
                "X-DayLimit-Remaining": "4000",
                "X-MinLimit-Remaining": "50",
                "X-AppMinLimit-Remaining": "9000",
            }
        )

        state = limiter.update_from_headers(state, headers)

        assert state.daily_remaining == 4000
        assert state.minute_remaining == 50
        assert state.app_minute_remaining == 9000
        assert state.last_updated is not None

    def test_record_rate_limit_hit(self, limiter: XeroRateLimiter) -> None:
        """Should record rate limit hit with retry_after."""
        state = RateLimitState()

        state = limiter.record_rate_limit_hit(state, 120)

        assert state.retry_after == 120
        assert state.is_rate_limited is True
        assert 118 <= state.seconds_until_reset <= 120

    def test_can_make_request_when_allowed(
        self, limiter: XeroRateLimiter, fresh_state: RateLimitState
    ) -> None:
        """Should allow requests when limits not reached."""
        assert limiter.can_make_request(fresh_state) is True

    def test_can_make_request_when_rate_limited(self, limiter: XeroRateLimiter) -> None:
        """Should deny requests when rate limited."""
        state = RateLimitState(rate_limited_until=datetime.now(UTC) + timedelta(seconds=60))
        assert limiter.can_make_request(state) is False

    def test_can_make_request_when_daily_limit_low(self, limiter: XeroRateLimiter) -> None:
        """Should deny requests when daily limit is low."""
        state = RateLimitState(daily_remaining=50)  # Below safety margin of 100
        assert limiter.can_make_request(state) is False

    def test_can_make_request_when_minute_limit_low(self, limiter: XeroRateLimiter) -> None:
        """Should deny requests when minute limit is low."""
        state = RateLimitState(minute_remaining=3)  # Below safety margin of 5
        assert limiter.can_make_request(state) is False

    def test_can_make_request_when_app_minute_limit_low(self, limiter: XeroRateLimiter) -> None:
        """Should deny requests when app minute limit is low."""
        state = RateLimitState(app_minute_remaining=3)  # Below safety margin
        assert limiter.can_make_request(state) is False

    def test_get_wait_time_when_no_wait_needed(
        self, limiter: XeroRateLimiter, fresh_state: RateLimitState
    ) -> None:
        """Should return 0 when no wait needed."""
        assert limiter.get_wait_time(fresh_state) == 0

    def test_get_wait_time_when_rate_limited(self, limiter: XeroRateLimiter) -> None:
        """Should return seconds until reset when rate limited."""
        state = RateLimitState(rate_limited_until=datetime.now(UTC) + timedelta(seconds=45))
        wait = limiter.get_wait_time(state)
        assert 43 <= wait <= 45

    def test_get_wait_time_when_minute_limit_low(self, limiter: XeroRateLimiter) -> None:
        """Should return 60 seconds when minute limit low."""
        state = RateLimitState(minute_remaining=3)
        assert limiter.get_wait_time(state) == 60

    def test_get_wait_time_when_daily_limit_low(self, limiter: XeroRateLimiter) -> None:
        """Should return seconds until midnight when daily limit low."""
        state = RateLimitState(daily_remaining=50)
        wait = limiter.get_wait_time(state)
        # Should be less than 24 hours
        assert 0 < wait <= 86400

    def test_calculate_backoff_first_attempt(self, limiter: XeroRateLimiter) -> None:
        """Should return 1 second for first attempt."""
        assert limiter.calculate_backoff(0) == 1

    def test_calculate_backoff_second_attempt(self, limiter: XeroRateLimiter) -> None:
        """Should return 2 seconds for second attempt."""
        assert limiter.calculate_backoff(1) == 2

    def test_calculate_backoff_third_attempt(self, limiter: XeroRateLimiter) -> None:
        """Should return 4 seconds for third attempt."""
        assert limiter.calculate_backoff(2) == 4

    def test_calculate_backoff_max_limit(self, limiter: XeroRateLimiter) -> None:
        """Should cap at MAX_BACKOFF_SECONDS."""
        # 2^10 = 1024, should be capped at 300
        assert limiter.calculate_backoff(10) == 300

    def test_should_retry_on_429(self, limiter: XeroRateLimiter) -> None:
        """Should retry on 429 rate limit."""
        assert limiter.should_retry(429, 0) is True
        assert limiter.should_retry(429, 1) is True
        assert limiter.should_retry(429, 2) is True
        assert limiter.should_retry(429, 3) is False  # Max attempts

    def test_should_retry_on_500(self, limiter: XeroRateLimiter) -> None:
        """Should retry on 500 server error."""
        assert limiter.should_retry(500, 0) is True
        assert limiter.should_retry(503, 0) is True

    def test_should_not_retry_on_400(self, limiter: XeroRateLimiter) -> None:
        """Should not retry on 400 client error."""
        assert limiter.should_retry(400, 0) is False
        assert limiter.should_retry(401, 0) is False
        assert limiter.should_retry(403, 0) is False
        assert limiter.should_retry(404, 0) is False

    def test_should_not_retry_after_max_attempts(self, limiter: XeroRateLimiter) -> None:
        """Should not retry after max attempts."""
        assert limiter.should_retry(429, 3) is False
        assert limiter.should_retry(500, 3) is False
