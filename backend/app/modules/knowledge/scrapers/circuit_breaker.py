"""DB-backed circuit breaker for knowledge base scrapers.

Prevents hammering external sites (ATO, legislation.gov.au) when they are
down or returning errors. State is persisted in the ``scraper_circuit_breakers``
table so it survives process restarts.

Circuit states:
- **closed**: healthy -- all requests allowed.
- **open**: tripped after ``failure_threshold`` consecutive failures.
  Requests are blocked until ``recovery_timeout`` elapses.
- **half_open**: recovery window -- a limited number of test requests
  (``half_open_max_requests``) are allowed. If they succeed the circuit
  closes; if they fail it re-opens.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.repository import CircuitBreakerRepository

logger = logging.getLogger(__name__)


class CircuitOpenError(Exception):
    """Raised when a request is blocked by an open circuit breaker.

    Attributes:
        source_host: The host whose circuit is open.
        retry_after: The earliest time a request may be retried.
    """

    def __init__(self, source_host: str, retry_after: datetime) -> None:
        self.source_host = source_host
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker open for {source_host}. Retry after {retry_after.isoformat()}"
        )


class ScraperCircuitBreaker:
    """DB-backed circuit breaker for scraper HTTP requests.

    All state mutations go through :class:`CircuitBreakerRepository` so
    state is shared across workers and survives restarts. The caller is
    responsible for committing the database session.

    Args:
        session: Async SQLAlchemy session (caller manages commit).
        failure_threshold: Number of consecutive failures before the
            circuit opens.
        recovery_timeout: Seconds to wait in the *open* state before
            transitioning to *half_open*.
        half_open_max_requests: Number of test requests allowed while
            the circuit is *half_open*.
    """

    def __init__(
        self,
        session: AsyncSession,
        failure_threshold: int = 5,
        recovery_timeout: int = 3600,
        half_open_max_requests: int = 2,
    ) -> None:
        self._repo = CircuitBreakerRepository(session)
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_requests = half_open_max_requests

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def check(self, source_host: str) -> bool:
        """Check whether a request to *source_host* is allowed.

        Returns ``True`` when the request may proceed. Raises
        :class:`CircuitOpenError` when the circuit is open and the
        recovery timeout has not elapsed.

        State transitions that happen here:
        * **open -> half_open** when the recovery timeout expires.
        """
        state = await self._repo.get_by_host(source_host)

        # No record yet or circuit is closed -- allow the request.
        if state is None or state.state == "closed":
            return True

        if state.state == "open":
            # Check whether the recovery timeout has elapsed.
            if state.opened_at is not None:
                recovery_deadline = state.opened_at + timedelta(
                    seconds=state.recovery_timeout_seconds
                )
                now = datetime.now(tz=UTC)

                if now >= recovery_deadline:
                    # Transition to half_open and allow a test request.
                    # Reset failure_count to 0 so it can be used to track
                    # the number of half-open test requests admitted.
                    logger.info(
                        "Circuit breaker for %s transitioning open -> half_open",
                        source_host,
                    )
                    await self._repo.upsert(
                        source_host,
                        state="half_open",
                        failure_count=0,
                    )
                    return True

                # Still within the recovery window -- block.
                raise CircuitOpenError(
                    source_host=source_host,
                    retry_after=recovery_deadline,
                )

            # opened_at is unexpectedly None -- treat as closed.
            logger.warning(
                "Circuit breaker for %s is open but opened_at is None; allowing request",
                source_host,
            )
            return True

        if state.state == "half_open":
            # Allow up to ``half_open_max_requests`` test requests.
            # We use the ``failure_count`` field as a counter for the
            # number of half-open requests that have been admitted so far.
            if state.failure_count < self.half_open_max_requests:
                return True

            # Limit reached -- block until a success resets the circuit.
            retry_after = datetime.now(tz=UTC) + timedelta(seconds=self.recovery_timeout)
            raise CircuitOpenError(
                source_host=source_host,
                retry_after=retry_after,
            )

        # Unknown state -- default to allowing the request.
        logger.warning(
            "Circuit breaker for %s has unknown state '%s'; allowing request",
            source_host,
            state.state,
        )
        return True

    async def record_success(self, source_host: str) -> None:
        """Record a successful request for *source_host*.

        Resets the failure count and closes the circuit.
        """
        logger.debug("Circuit breaker recording success for %s", source_host)
        await self._repo.upsert(
            source_host,
            state="closed",
            failure_count=0,
            last_success_at=datetime.now(tz=UTC),
        )

    async def record_failure(self, source_host: str) -> None:
        """Record a failed request for *source_host*.

        Increments the failure count. If the count reaches the
        ``failure_threshold`` the circuit transitions to *open*.
        """
        now = datetime.now(tz=UTC)
        state = await self._repo.get_by_host(source_host)

        current_failures = (state.failure_count if state else 0) + 1

        if current_failures >= self.failure_threshold:
            logger.warning(
                "Circuit breaker for %s tripped after %d consecutive failures",
                source_host,
                current_failures,
            )
            await self._repo.upsert(
                source_host,
                state="open",
                failure_count=current_failures,
                last_failure_at=now,
                opened_at=now,
                recovery_timeout_seconds=self.recovery_timeout,
            )
        else:
            logger.info(
                "Circuit breaker recording failure %d/%d for %s",
                current_failures,
                self.failure_threshold,
                source_host,
            )
            await self._repo.upsert(
                source_host,
                failure_count=current_failures,
                last_failure_at=now,
            )
