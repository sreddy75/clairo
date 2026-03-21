"""Xero API HTTP client.

Provides async HTTP client for Xero API:
- Token exchange (authorization code -> tokens)
- Token refresh
- Connections listing (authorized organizations)
- Token revocation
- Data sync endpoints (contacts, invoices, transactions, accounts)
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.config import XeroSettings
from app.modules.integrations.xero.rate_limiter import RateLimitState
from app.modules.integrations.xero.schemas import TokenResponse, XeroOrganization


class XeroClientError(Exception):
    """Base exception for Xero API errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class XeroAuthError(XeroClientError):
    """Authentication/authorization error (invalid credentials, expired tokens)."""

    pass


class XeroRateLimitError(XeroClientError):
    """Rate limit exceeded error."""

    def __init__(self, message: str, retry_after: int) -> None:
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class XeroClient:
    """Async HTTP client for Xero OAuth and API operations.

    Example:
        async with XeroClient(settings) as client:
            tokens = await client.exchange_code(code, verifier, redirect_uri)
            orgs = await client.get_connections(tokens.access_token)
    """

    DEFAULT_TIMEOUT = 30.0

    def __init__(self, settings: XeroSettings) -> None:
        """Initialize Xero client with settings.

        Args:
            settings: Xero configuration including client_id and URLs.
        """
        self.settings = settings
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "XeroClient":
        """Create HTTP client on context entry."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.DEFAULT_TIMEOUT),
            headers={"User-Agent": "Clairo/1.0"},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[no-untyped-def]
        """Close HTTP client on context exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get the HTTP client, raising if not in context."""
        if self._client is None:
            raise RuntimeError("XeroClient must be used as async context manager")
        return self._client

    async def exchange_code(
        self,
        code: str,
        code_verifier: str,
        redirect_uri: str,
    ) -> tuple[TokenResponse, datetime]:
        """Exchange authorization code for tokens.

        Args:
            code: Authorization code from Xero callback.
            code_verifier: PKCE code verifier used when generating auth URL.
            redirect_uri: Same redirect URI used in authorization request.

        Returns:
            Tuple of (TokenResponse, token_expires_at datetime).

        Raises:
            XeroAuthError: If code exchange fails.
            XeroClientError: For other API errors.
        """
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
            "client_id": self.settings.client_id,
        }

        # Add client_secret if configured (not needed for PKCE but some apps use it)
        if self.settings.client_secret:
            data["client_secret"] = self.settings.client_secret.get_secret_value()

        response = await self.client.post(
            self.settings.token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if response.status_code != 200:
            error_data = response.json() if response.content else {}
            error_msg = error_data.get(
                "error_description", error_data.get("error", "Unknown error")
            )
            raise XeroAuthError(f"Token exchange failed: {error_msg}", response.status_code)

        token_data = response.json()
        token_response = TokenResponse(**token_data)

        # Calculate expiry time
        expires_at = datetime.now(UTC) + timedelta(seconds=token_response.expires_in)

        return token_response, expires_at

    async def refresh_token(self, refresh_token: str) -> tuple[TokenResponse, datetime]:
        """Refresh access token using refresh token.

        Note: Xero uses rotating refresh tokens - each refresh returns a new
        refresh token and the old one is invalidated.

        Args:
            refresh_token: Current refresh token.

        Returns:
            Tuple of (TokenResponse with new tokens, token_expires_at datetime).

        Raises:
            XeroAuthError: If refresh fails (token expired/revoked).
            XeroClientError: For other API errors.
        """
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.settings.client_id,
        }

        if self.settings.client_secret:
            data["client_secret"] = self.settings.client_secret.get_secret_value()

        response = await self.client.post(
            self.settings.token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if response.status_code != 200:
            error_data = response.json() if response.content else {}
            error_msg = error_data.get(
                "error_description", error_data.get("error", "Unknown error")
            )

            # Check for invalid_grant which means token is expired/revoked
            if error_data.get("error") == "invalid_grant":
                raise XeroAuthError(
                    "Refresh token expired or revoked - re-authorization required",
                    response.status_code,
                )

            raise XeroAuthError(f"Token refresh failed: {error_msg}", response.status_code)

        token_data = response.json()
        token_response = TokenResponse(**token_data)
        expires_at = datetime.now(UTC) + timedelta(seconds=token_response.expires_in)

        return token_response, expires_at

    async def get_connections(self, access_token: str) -> list[XeroOrganization]:
        """Get list of authorized Xero organizations.

        After OAuth, a user may have authorized access to multiple Xero
        organizations. This endpoint lists all of them.

        Args:
            access_token: Valid Xero access token.

        Returns:
            List of XeroOrganization objects.

        Raises:
            XeroAuthError: If token is invalid.
            XeroRateLimitError: If rate limit exceeded.
            XeroClientError: For other API errors.
        """
        response = await self.client.get(
            self.settings.connections_url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
        )

        self._check_response(response)

        connections_data = response.json()
        return [XeroOrganization(**conn) for conn in connections_data]

    async def revoke_token(self, token: str) -> None:
        """Revoke a token (access or refresh).

        Args:
            token: The token to revoke.

        Raises:
            XeroClientError: If revocation fails.
        """
        data = {
            "token": token,
            "client_id": self.settings.client_id,
        }

        if self.settings.client_secret:
            data["client_secret"] = self.settings.client_secret.get_secret_value()

        response = await self.client.post(
            self.settings.revocation_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        # Revocation returns 200 on success, but we don't fail on errors
        # since we want to disconnect even if Xero-side revocation fails
        if response.status_code not in (200, 400):
            # Log but don't raise - we still want to remove local connection
            pass

    def _check_response(self, response: httpx.Response) -> None:
        """Check response for errors and raise appropriate exceptions.

        Args:
            response: HTTP response to check.

        Raises:
            XeroAuthError: For 401 responses.
            XeroRateLimitError: For 429 responses.
            XeroClientError: For other error responses.
        """
        if response.status_code == 200:
            return

        if response.status_code == 401:
            raise XeroAuthError("Invalid or expired access token", 401)

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "60"))
            raise XeroRateLimitError(
                f"Rate limit exceeded, retry after {retry_after} seconds",
                retry_after,
            )

        error_msg = f"Xero API error: {response.status_code}"
        if response.content:
            try:
                error_data = response.json()
                error_msg = error_data.get("Detail", error_data.get("Message", error_msg))
            except Exception:
                pass

        raise XeroClientError(error_msg, response.status_code)

    def parse_rate_limit_headers(
        self, headers: httpx.Headers
    ) -> tuple[int | None, int | None, int | None]:
        """Parse rate limit headers from Xero response.

        Args:
            headers: Response headers.

        Returns:
            Tuple of (daily_remaining, minute_remaining, app_minute_remaining).
            None values indicate header was not present.
        """
        daily = headers.get("X-DayLimit-Remaining")
        minute = headers.get("X-MinLimit-Remaining")
        app_minute = headers.get("X-AppMinLimit-Remaining")

        return (
            int(daily) if daily else None,
            int(minute) if minute else None,
            int(app_minute) if app_minute else None,
        )

    def _extract_rate_limit_state(self, headers: httpx.Headers) -> RateLimitState:
        """Extract rate limit state from response headers.

        Args:
            headers: Response headers.

        Returns:
            RateLimitState with parsed values.
        """
        daily, minute, _ = self.parse_rate_limit_headers(headers)
        return RateLimitState(
            daily_remaining=daily or 5000,
            minute_remaining=minute or 60,
            last_request_at=datetime.now(UTC),
        )

    # =========================================================================
    # Organisation API Methods
    # =========================================================================

    async def get_organisation(
        self,
        access_token: str,
        tenant_id: str,
    ) -> tuple[dict[str, Any] | None, RateLimitState]:
        """Fetch organisation details from Xero API.

        Gets detailed information about the Xero organisation including
        entity type, ABN/tax number, and GST settings.

        Args:
            access_token: Valid Xero access token.
            tenant_id: Xero tenant ID to fetch from.

        Returns:
            Tuple of (organisation dict or None, rate_limit_state).

        Raises:
            XeroAuthError: If token is invalid.
            XeroRateLimitError: If rate limit exceeded.
            XeroClientError: For other API errors.
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        response = await self.client.get(
            f"{self.settings.api_url}/Organisation",
            headers=headers,
        )

        self._check_response(response)

        rate_limit_state = self._extract_rate_limit_state(response.headers)
        data = response.json()

        # Organisation endpoint returns {"Organisations": [...]}
        organisations = data.get("Organisations", [])
        if organisations:
            return organisations[0], rate_limit_state

        return None, rate_limit_state

    # =========================================================================
    # Data Sync API Methods
    # =========================================================================

    async def get_contacts(
        self,
        access_token: str,
        tenant_id: str,
        page: int = 1,
        modified_since: datetime | None = None,
    ) -> tuple[list[dict[str, Any]], bool, RateLimitState]:
        """Fetch contacts from Xero API.

        Args:
            access_token: Valid Xero access token.
            tenant_id: Xero tenant ID to fetch from.
            page: Page number (1-based).
            modified_since: Only return contacts modified after this time.

        Returns:
            Tuple of (contacts list, has_more_pages, rate_limit_state).

        Raises:
            XeroAuthError: If token is invalid.
            XeroRateLimitError: If rate limit exceeded.
            XeroClientError: For other API errors.
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        if modified_since:
            headers["If-Modified-Since"] = modified_since.strftime("%a, %d %b %Y %H:%M:%S GMT")

        params = {"page": page}

        response = await self.client.get(
            f"{self.settings.api_url}/Contacts",
            headers=headers,
            params=params,
        )

        self._check_response(response)

        data = response.json()
        contacts = data.get("Contacts", [])

        # Xero returns up to 100 contacts per page
        has_more = len(contacts) >= 100

        rate_limit = self._extract_rate_limit_state(response.headers)

        return contacts, has_more, rate_limit

    async def get_invoices(
        self,
        access_token: str,
        tenant_id: str,
        page: int = 1,
        modified_since: datetime | None = None,
    ) -> tuple[list[dict[str, Any]], bool, RateLimitState]:
        """Fetch invoices from Xero API.

        Args:
            access_token: Valid Xero access token.
            tenant_id: Xero tenant ID to fetch from.
            page: Page number (1-based).
            modified_since: Only return invoices modified after this time.

        Returns:
            Tuple of (invoices list, has_more_pages, rate_limit_state).

        Raises:
            XeroAuthError: If token is invalid.
            XeroRateLimitError: If rate limit exceeded.
            XeroClientError: For other API errors.
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        if modified_since:
            headers["If-Modified-Since"] = modified_since.strftime("%a, %d %b %Y %H:%M:%S GMT")

        params = {"page": page}

        response = await self.client.get(
            f"{self.settings.api_url}/Invoices",
            headers=headers,
            params=params,
        )

        self._check_response(response)

        data = response.json()
        invoices = data.get("Invoices", [])

        # Xero returns up to 100 invoices per page
        has_more = len(invoices) >= 100

        rate_limit = self._extract_rate_limit_state(response.headers)

        return invoices, has_more, rate_limit

    async def get_bank_transactions(
        self,
        access_token: str,
        tenant_id: str,
        page: int = 1,
        modified_since: datetime | None = None,
    ) -> tuple[list[dict[str, Any]], bool, RateLimitState]:
        """Fetch bank transactions from Xero API.

        Args:
            access_token: Valid Xero access token.
            tenant_id: Xero tenant ID to fetch from.
            page: Page number (1-based).
            modified_since: Only return transactions modified after this time.

        Returns:
            Tuple of (transactions list, has_more_pages, rate_limit_state).

        Raises:
            XeroAuthError: If token is invalid.
            XeroRateLimitError: If rate limit exceeded.
            XeroClientError: For other API errors.
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        if modified_since:
            headers["If-Modified-Since"] = modified_since.strftime("%a, %d %b %Y %H:%M:%S GMT")

        params = {"page": page}

        response = await self.client.get(
            f"{self.settings.api_url}/BankTransactions",
            headers=headers,
            params=params,
        )

        self._check_response(response)

        data = response.json()
        transactions = data.get("BankTransactions", [])

        # Xero returns up to 100 transactions per page
        has_more = len(transactions) >= 100

        rate_limit = self._extract_rate_limit_state(response.headers)

        return transactions, has_more, rate_limit

    async def get_accounts(
        self,
        access_token: str,
        tenant_id: str,
    ) -> tuple[list[dict[str, Any]], RateLimitState]:
        """Fetch chart of accounts from Xero API.

        Note: Accounts endpoint does not require pagination as organizations
        typically have < 100 accounts.

        Args:
            access_token: Valid Xero access token.
            tenant_id: Xero tenant ID to fetch from.

        Returns:
            Tuple of (accounts list, rate_limit_state).

        Raises:
            XeroAuthError: If token is invalid.
            XeroRateLimitError: If rate limit exceeded.
            XeroClientError: For other API errors.
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        response = await self.client.get(
            f"{self.settings.api_url}/Accounts",
            headers=headers,
        )

        self._check_response(response)

        data = response.json()
        accounts = data.get("Accounts", [])

        rate_limit = self._extract_rate_limit_state(response.headers)

        return accounts, rate_limit

    # =========================================================================
    # Payroll API Methods (Australian Payroll)
    # =========================================================================

    async def get_employees(
        self,
        access_token: str,
        tenant_id: str,
        page: int = 1,
        modified_since: datetime | None = None,
    ) -> tuple[list[dict[str, Any]], bool, RateLimitState]:
        """Fetch employees from Xero Payroll API (AU).

        Args:
            access_token: Valid Xero access token with payroll scopes.
            tenant_id: Xero tenant ID to fetch from.
            page: Page number (1-based).
            modified_since: Only return employees modified after this time.

        Returns:
            Tuple of (employees list, has_more_pages, rate_limit_state).

        Raises:
            XeroAuthError: If token is invalid or lacks payroll scope.
            XeroRateLimitError: If rate limit exceeded.
            XeroClientError: For other API errors.
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        if modified_since:
            headers["If-Modified-Since"] = modified_since.strftime("%a, %d %b %Y %H:%M:%S GMT")

        params = {"page": page}

        response = await self.client.get(
            f"{self.settings.payroll_url}/Employees",
            headers=headers,
            params=params,
        )

        self._check_response(response)

        data = response.json()
        # Xero Payroll AU API returns lowercase 'employees' (not 'Employees')
        employees = data.get("employees", [])

        # Xero Payroll returns up to 100 employees per page
        has_more = len(employees) >= 100

        rate_limit = self._extract_rate_limit_state(response.headers)

        return employees, has_more, rate_limit

    async def get_pay_runs(
        self,
        access_token: str,
        tenant_id: str,
        page: int = 1,
        status: str | None = None,
    ) -> tuple[list[dict[str, Any]], bool, RateLimitState]:
        """Fetch pay runs from Xero Payroll API (AU).

        Args:
            access_token: Valid Xero access token with payroll scopes.
            tenant_id: Xero tenant ID to fetch from.
            page: Page number (1-based).
            status: Filter by status ('DRAFT' or 'POSTED').

        Returns:
            Tuple of (pay_runs list, has_more_pages, rate_limit_state).

        Raises:
            XeroAuthError: If token is invalid or lacks payroll scope.
            XeroRateLimitError: If rate limit exceeded.
            XeroClientError: For other API errors.
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        params: dict[str, Any] = {"page": page}

        # Filter by status if specified
        if status:
            params["where"] = f'PayRunStatus=="{status}"'

        response = await self.client.get(
            f"{self.settings.payroll_url}/PayRuns",
            headers=headers,
            params=params,
        )

        self._check_response(response)

        data = response.json()
        pay_runs = data.get("PayRuns", [])

        # Xero Payroll returns up to 100 pay runs per page
        has_more = len(pay_runs) >= 100

        rate_limit = self._extract_rate_limit_state(response.headers)

        return pay_runs, has_more, rate_limit

    async def get_pay_run_details(
        self,
        access_token: str,
        tenant_id: str,
        pay_run_id: str,
    ) -> tuple[dict[str, Any], RateLimitState]:
        """Fetch detailed pay run including payslips from Xero Payroll API (AU).

        Args:
            access_token: Valid Xero access token with payroll scopes.
            tenant_id: Xero tenant ID to fetch from.
            pay_run_id: The Xero PayRun ID.

        Returns:
            Tuple of (pay_run dict, rate_limit_state).

        Raises:
            XeroAuthError: If token is invalid or lacks payroll scope.
            XeroRateLimitError: If rate limit exceeded.
            XeroClientError: For other API errors.
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        response = await self.client.get(
            f"{self.settings.payroll_url}/PayRuns/{pay_run_id}",
            headers=headers,
        )

        self._check_response(response)

        data = response.json()
        pay_runs = data.get("PayRuns", [])

        rate_limit = self._extract_rate_limit_state(response.headers)

        # Return the single pay run (API returns a list with one item)
        pay_run = pay_runs[0] if pay_runs else {}

        return pay_run, rate_limit

    # =========================================================================
    # Reports API Methods (Spec 023)
    # =========================================================================

    async def get_profit_and_loss(
        self,
        access_token: str,
        tenant_id: str,
        from_date: str | None = None,
        to_date: str | None = None,
        periods: int = 1,
        timeframe: str = "MONTH",
        standard_layout: bool = True,
        payments_only: bool = False,
    ) -> tuple[dict[str, Any], RateLimitState]:
        """Fetch Profit & Loss report from Xero Reports API.

        Args:
            access_token: Valid Xero access token.
            tenant_id: Xero tenant ID.
            from_date: Start date (YYYY-MM-DD). Defaults to start of current month.
            to_date: End date (YYYY-MM-DD). Defaults to today.
            periods: Number of comparison periods (1-11).
            timeframe: Comparison timeframe (MONTH, QUARTER, YEAR).
            standard_layout: Use standard chart of accounts layout.
            payments_only: Cash basis (True) vs accrual (False).

        Returns:
            Tuple of (report dict, rate_limit_state).

        Raises:
            XeroAuthError: If token is invalid.
            XeroRateLimitError: If rate limit exceeded.
            XeroClientError: For other API errors.
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        # Build params - CRITICAL: `date` param is undocumented but required
        # for per-period amounts (not cumulative)
        params: dict[str, Any] = {
            "periods": periods,
            "timeframe": timeframe,
            "standardLayout": str(standard_layout).lower(),
            "paymentsOnly": str(payments_only).lower(),
        }

        if from_date:
            params["fromDate"] = from_date
            params["date"] = from_date  # Undocumented but critical
        if to_date:
            params["toDate"] = to_date

        response = await self.client.get(
            f"{self.settings.api_url}/Reports/ProfitAndLoss",
            headers=headers,
            params=params,
        )

        self._check_response(response)

        data = response.json()
        rate_limit = self._extract_rate_limit_state(response.headers)

        return data, rate_limit

    async def get_balance_sheet(
        self,
        access_token: str,
        tenant_id: str,
        as_of_date: str | None = None,
        periods: int = 1,
        timeframe: str = "MONTH",
        standard_layout: bool = True,
        payments_only: bool = False,
    ) -> tuple[dict[str, Any], RateLimitState]:
        """Fetch Balance Sheet report from Xero Reports API.

        Args:
            access_token: Valid Xero access token.
            tenant_id: Xero tenant ID.
            as_of_date: Report date (YYYY-MM-DD). Defaults to today.
            periods: Number of comparison periods (1-11).
            timeframe: Comparison timeframe (MONTH, QUARTER, YEAR).
            standard_layout: Use standard chart of accounts layout.
            payments_only: Cash basis (True) vs accrual (False).

        Returns:
            Tuple of (report dict, rate_limit_state).
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        params: dict[str, Any] = {
            "periods": periods,
            "timeframe": timeframe,
            "standardLayout": str(standard_layout).lower(),
            "paymentsOnly": str(payments_only).lower(),
        }

        if as_of_date:
            params["date"] = as_of_date

        response = await self.client.get(
            f"{self.settings.api_url}/Reports/BalanceSheet",
            headers=headers,
            params=params,
        )

        self._check_response(response)

        data = response.json()
        rate_limit = self._extract_rate_limit_state(response.headers)

        return data, rate_limit

    async def get_aged_receivables(
        self,
        access_token: str,
        tenant_id: str,
        as_of_date: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> tuple[dict[str, Any], RateLimitState]:
        """Fetch Aged Receivables by Contact report from Xero Reports API.

        Args:
            access_token: Valid Xero access token.
            tenant_id: Xero tenant ID.
            as_of_date: Aged as-of date (YYYY-MM-DD). Defaults to today.
            from_date: Filter invoices from this date.
            to_date: Filter invoices to this date.

        Returns:
            Tuple of (report dict, rate_limit_state).
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        params: dict[str, Any] = {}

        if as_of_date:
            params["date"] = as_of_date
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date

        response = await self.client.get(
            f"{self.settings.api_url}/Reports/AgedReceivablesByContact",
            headers=headers,
            params=params,
        )

        self._check_response(response)

        data = response.json()
        rate_limit = self._extract_rate_limit_state(response.headers)

        return data, rate_limit

    async def get_aged_payables(
        self,
        access_token: str,
        tenant_id: str,
        as_of_date: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> tuple[dict[str, Any], RateLimitState]:
        """Fetch Aged Payables by Contact report from Xero Reports API.

        Args:
            access_token: Valid Xero access token.
            tenant_id: Xero tenant ID.
            as_of_date: Aged as-of date (YYYY-MM-DD). Defaults to today.
            from_date: Filter bills from this date.
            to_date: Filter bills to this date.

        Returns:
            Tuple of (report dict, rate_limit_state).
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        params: dict[str, Any] = {}

        if as_of_date:
            params["date"] = as_of_date
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date

        response = await self.client.get(
            f"{self.settings.api_url}/Reports/AgedPayablesByContact",
            headers=headers,
            params=params,
        )

        self._check_response(response)

        data = response.json()
        rate_limit = self._extract_rate_limit_state(response.headers)

        return data, rate_limit

    async def get_trial_balance(
        self,
        access_token: str,
        tenant_id: str,
        as_of_date: str | None = None,
        payments_only: bool = False,
    ) -> tuple[dict[str, Any], RateLimitState]:
        """Fetch Trial Balance report from Xero Reports API.

        Args:
            access_token: Valid Xero access token.
            tenant_id: Xero tenant ID.
            as_of_date: Report date (YYYY-MM-DD). Defaults to end of current month.
            payments_only: Cash basis (True) vs accrual (False).

        Returns:
            Tuple of (report dict, rate_limit_state).
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        params: dict[str, Any] = {
            "paymentsOnly": str(payments_only).lower(),
        }

        if as_of_date:
            params["date"] = as_of_date

        response = await self.client.get(
            f"{self.settings.api_url}/Reports/TrialBalance",
            headers=headers,
            params=params,
        )

        self._check_response(response)

        data = response.json()
        rate_limit = self._extract_rate_limit_state(response.headers)

        return data, rate_limit

    async def get_bank_summary(
        self,
        access_token: str,
        tenant_id: str,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> tuple[dict[str, Any], RateLimitState]:
        """Fetch Bank Summary report from Xero Reports API.

        Args:
            access_token: Valid Xero access token.
            tenant_id: Xero tenant ID.
            from_date: Period start (YYYY-MM-DD). Defaults to start of current month.
            to_date: Period end (YYYY-MM-DD). Defaults to today.

        Returns:
            Tuple of (report dict, rate_limit_state).
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        params: dict[str, Any] = {}

        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date

        response = await self.client.get(
            f"{self.settings.api_url}/Reports/BankSummary",
            headers=headers,
            params=params,
        )

        self._check_response(response)

        data = response.json()
        rate_limit = self._extract_rate_limit_state(response.headers)

        return data, rate_limit

    async def get_budget_summary(
        self,
        access_token: str,
        tenant_id: str,
        as_of_date: str | None = None,
        periods: int = 12,
        timeframe: int = 1,
    ) -> tuple[dict[str, Any], RateLimitState]:
        """Fetch Budget Summary report from Xero Reports API.

        Args:
            access_token: Valid Xero access token.
            tenant_id: Xero tenant ID.
            as_of_date: Budget as-of date (YYYY-MM-DD). Defaults to today.
            periods: Number of periods (1-12).
            timeframe: 1=months, 2=quarters.

        Returns:
            Tuple of (report dict, rate_limit_state).
            Note: Returns empty if no budget configured in Xero.
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        params: dict[str, Any] = {
            "periods": periods,
            "timeframe": timeframe,
        }

        if as_of_date:
            params["date"] = as_of_date

        response = await self.client.get(
            f"{self.settings.api_url}/Reports/BudgetSummary",
            headers=headers,
            params=params,
        )

        self._check_response(response)

        data = response.json()
        rate_limit = self._extract_rate_limit_state(response.headers)

        return data, rate_limit

    # =========================================================================
    # Credit Notes, Payments, Journals API Methods (Spec 024)
    # =========================================================================

    async def get_credit_notes(
        self,
        access_token: str,
        tenant_id: str,
        modified_since: datetime | None = None,
        page: int = 1,
    ) -> tuple[list[dict[str, Any]], RateLimitState]:
        """Fetch credit notes from Xero.

        Args:
            access_token: Valid Xero access token.
            tenant_id: Xero tenant ID.
            modified_since: Only return credit notes modified after this datetime.
            page: Page number for pagination (100 per page).

        Returns:
            Tuple of (list of credit note dicts, rate_limit_state).
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        if modified_since:
            headers["If-Modified-Since"] = modified_since.strftime("%a, %d %b %Y %H:%M:%S GMT")

        params: dict[str, Any] = {"page": page}

        response = await self.client.get(
            f"{self.settings.api_url}/CreditNotes",
            headers=headers,
            params=params,
        )

        self._check_response(response)

        data = response.json()
        credit_notes = data.get("CreditNotes", [])
        rate_limit = self._extract_rate_limit_state(response.headers)

        return credit_notes, rate_limit

    async def get_payments(
        self,
        access_token: str,
        tenant_id: str,
        modified_since: datetime | None = None,
        page: int = 1,
    ) -> tuple[list[dict[str, Any]], RateLimitState]:
        """Fetch payments from Xero.

        Args:
            access_token: Valid Xero access token.
            tenant_id: Xero tenant ID.
            modified_since: Only return payments modified after this datetime.
            page: Page number for pagination (100 per page).

        Returns:
            Tuple of (list of payment dicts, rate_limit_state).
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        if modified_since:
            headers["If-Modified-Since"] = modified_since.strftime("%a, %d %b %Y %H:%M:%S GMT")

        params: dict[str, Any] = {"page": page}

        response = await self.client.get(
            f"{self.settings.api_url}/Payments",
            headers=headers,
            params=params,
        )

        self._check_response(response)

        data = response.json()
        payments = data.get("Payments", [])
        rate_limit = self._extract_rate_limit_state(response.headers)

        return payments, rate_limit

    async def get_overpayments(
        self,
        access_token: str,
        tenant_id: str,
        modified_since: datetime | None = None,
        page: int = 1,
    ) -> tuple[list[dict[str, Any]], RateLimitState]:
        """Fetch overpayments from Xero.

        Args:
            access_token: Valid Xero access token.
            tenant_id: Xero tenant ID.
            modified_since: Only return overpayments modified after this datetime.
            page: Page number for pagination (100 per page).

        Returns:
            Tuple of (list of overpayment dicts, rate_limit_state).
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        if modified_since:
            headers["If-Modified-Since"] = modified_since.strftime("%a, %d %b %Y %H:%M:%S GMT")

        params: dict[str, Any] = {"page": page}

        response = await self.client.get(
            f"{self.settings.api_url}/Overpayments",
            headers=headers,
            params=params,
        )

        self._check_response(response)

        data = response.json()
        overpayments = data.get("Overpayments", [])
        rate_limit = self._extract_rate_limit_state(response.headers)

        return overpayments, rate_limit

    async def get_prepayments(
        self,
        access_token: str,
        tenant_id: str,
        modified_since: datetime | None = None,
        page: int = 1,
    ) -> tuple[list[dict[str, Any]], RateLimitState]:
        """Fetch prepayments from Xero.

        Args:
            access_token: Valid Xero access token.
            tenant_id: Xero tenant ID.
            modified_since: Only return prepayments modified after this datetime.
            page: Page number for pagination (100 per page).

        Returns:
            Tuple of (list of prepayment dicts, rate_limit_state).
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        if modified_since:
            headers["If-Modified-Since"] = modified_since.strftime("%a, %d %b %Y %H:%M:%S GMT")

        params: dict[str, Any] = {"page": page}

        response = await self.client.get(
            f"{self.settings.api_url}/Prepayments",
            headers=headers,
            params=params,
        )

        self._check_response(response)

        data = response.json()
        prepayments = data.get("Prepayments", [])
        rate_limit = self._extract_rate_limit_state(response.headers)

        return prepayments, rate_limit

    async def get_journals(
        self,
        access_token: str,
        tenant_id: str,
        modified_since: datetime | None = None,
        offset: int = 0,
        payments_only: bool = False,
    ) -> tuple[list[dict[str, Any]], RateLimitState]:
        """Fetch journals from Xero.

        Note: Journals use offset pagination, not page numbers.
        Each call returns up to 100 journals starting from the offset.

        Args:
            access_token: Valid Xero access token.
            tenant_id: Xero tenant ID.
            modified_since: Only return journals modified after this datetime.
            offset: Journal number to start from (for pagination).
            payments_only: If True, only return journals for payments.

        Returns:
            Tuple of (list of journal dicts, rate_limit_state).
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        if modified_since:
            headers["If-Modified-Since"] = modified_since.strftime("%a, %d %b %Y %H:%M:%S GMT")

        params: dict[str, Any] = {
            "offset": offset,
            "paymentsOnly": str(payments_only).lower(),
        }

        response = await self.client.get(
            f"{self.settings.api_url}/Journals",
            headers=headers,
            params=params,
        )

        self._check_response(response)

        data = response.json()
        journals = data.get("Journals", [])
        rate_limit = self._extract_rate_limit_state(response.headers)

        return journals, rate_limit

    async def get_manual_journals(
        self,
        access_token: str,
        tenant_id: str,
        modified_since: datetime | None = None,
        page: int = 1,
    ) -> tuple[list[dict[str, Any]], RateLimitState]:
        """Fetch manual journals from Xero.

        Args:
            access_token: Valid Xero access token.
            tenant_id: Xero tenant ID.
            modified_since: Only return manual journals modified after this datetime.
            page: Page number for pagination (100 per page).

        Returns:
            Tuple of (list of manual journal dicts, rate_limit_state).
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        if modified_since:
            headers["If-Modified-Since"] = modified_since.strftime("%a, %d %b %Y %H:%M:%S GMT")

        params: dict[str, Any] = {"page": page}

        response = await self.client.get(
            f"{self.settings.api_url}/ManualJournals",
            headers=headers,
            params=params,
        )

        self._check_response(response)

        data = response.json()
        manual_journals = data.get("ManualJournals", [])
        rate_limit = self._extract_rate_limit_state(response.headers)

        return manual_journals, rate_limit

    # ===== Assets API Methods (requires 'assets' scope) =====

    async def get_asset_types(
        self,
        access_token: str,
        tenant_id: str,
    ) -> tuple[list[dict[str, Any]], RateLimitState]:
        """Fetch asset types from Xero Assets API.

        Asset types define depreciation categories (e.g., Motor Vehicles,
        Computer Equipment) with their depreciation methods and rates.

        Args:
            access_token: Valid Xero access token with 'assets' scope.
            tenant_id: Xero tenant ID.

        Returns:
            Tuple of (list of asset type dicts, rate_limit_state).
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        response = await self.client.get(
            f"{self.settings.assets_url}/AssetTypes",
            headers=headers,
        )

        self._check_response(response)

        data = response.json()
        rate_limit = self._extract_rate_limit_state(response.headers)

        # Handle different response formats from Xero
        if isinstance(data, list):
            # API returned a list directly
            asset_types = data
        elif isinstance(data, dict):
            asset_types = data.get("assetTypes", [])
        else:
            logger.warning(f"Unexpected asset types response format: {type(data)}")
            asset_types = []

        return asset_types, rate_limit

    async def get_assets(
        self,
        access_token: str,
        tenant_id: str,
        status: str | None = None,
        page: int = 1,
        page_size: int = 100,
        order_by: str = "AssetName",
        sort_direction: str = "ASC",
    ) -> tuple[list[dict[str, Any]], dict[str, Any], RateLimitState]:
        """Fetch fixed assets from Xero Assets API.

        Args:
            access_token: Valid Xero access token with 'assets' scope.
            tenant_id: Xero tenant ID.
            status: Filter by status (Draft, Registered, Disposed).
            page: Page number for pagination.
            page_size: Number of assets per page (max 100).
            order_by: Field to order by (AssetName, AssetNumber, PurchaseDate).
            sort_direction: Sort direction (ASC or DESC).

        Returns:
            Tuple of (list of asset dicts, pagination info, rate_limit_state).
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        params: dict[str, Any] = {
            "page": page,
            "pageSize": page_size,
            "orderBy": order_by,
            "sortDirection": sort_direction,
        }

        if status:
            params["status"] = status

        response = await self.client.get(
            f"{self.settings.assets_url}/Assets",
            headers=headers,
            params=params,
        )

        self._check_response(response)

        data = response.json()
        assets = data.get("items", [])
        pagination = data.get("pagination", {})
        rate_limit = self._extract_rate_limit_state(response.headers)

        return assets, pagination, rate_limit

    async def get_asset_settings(
        self,
        access_token: str,
        tenant_id: str,
    ) -> tuple[dict[str, Any], RateLimitState]:
        """Fetch asset settings from Xero Assets API.

        Settings include the organization's default depreciation methods,
        start month, and fixed asset accounts.

        Args:
            access_token: Valid Xero access token with 'assets' scope.
            tenant_id: Xero tenant ID.

        Returns:
            Tuple of (settings dict, rate_limit_state).
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        response = await self.client.get(
            f"{self.settings.assets_url}/Settings",
            headers=headers,
        )

        self._check_response(response)

        settings = response.json()
        rate_limit = self._extract_rate_limit_state(response.headers)

        return settings, rate_limit

    # =========================================================================
    # Spec 025: Purchase Orders
    # =========================================================================

    async def get_purchase_orders(
        self,
        access_token: str,
        tenant_id: str,
        status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> tuple[list[dict[str, Any]], RateLimitState]:
        """Fetch purchase orders from Xero Accounting API.

        Args:
            access_token: Valid Xero access token.
            tenant_id: Xero tenant ID.
            status: Filter by status (DRAFT, SUBMITTED, AUTHORISED, BILLED, DELETED).
            date_from: Filter by date from (YYYY-MM-DD).
            date_to: Filter by date to (YYYY-MM-DD).
            page: Page number for pagination.
            page_size: Number of items per page.

        Returns:
            Tuple of (list of purchase order dicts, rate_limit_state).
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        # Build where clause for filtering
        where_clauses = []
        if status:
            where_clauses.append(f'Status=="{status}"')
        if date_from:
            where_clauses.append(f"Date>=DateTime({date_from.replace('-', ',')})")
        if date_to:
            where_clauses.append(f"Date<=DateTime({date_to.replace('-', ',')})")

        params: dict[str, Any] = {
            "page": page,
            "pageSize": min(page_size, 100),
        }
        if where_clauses:
            params["where"] = " && ".join(where_clauses)

        response = await self.client.get(
            f"{self.settings.api_url}/PurchaseOrders",
            headers=headers,
            params=params,
        )

        self._check_response(response)

        data = response.json()
        purchase_orders = data.get("PurchaseOrders", [])
        rate_limit = self._extract_rate_limit_state(response.headers)

        return purchase_orders, rate_limit

    async def get_repeating_invoices(
        self,
        access_token: str,
        tenant_id: str,
        status: str | None = None,
    ) -> tuple[list[dict[str, Any]], RateLimitState]:
        """Fetch repeating invoices from Xero Accounting API.

        Args:
            access_token: Valid Xero access token.
            tenant_id: Xero tenant ID.
            status: Filter by status (DRAFT, AUTHORISED).

        Returns:
            Tuple of (list of repeating invoice dicts, rate_limit_state).
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        params: dict[str, Any] = {}
        if status:
            params["where"] = f'Status=="{status}"'

        response = await self.client.get(
            f"{self.settings.api_url}/RepeatingInvoices",
            headers=headers,
            params=params,
        )

        self._check_response(response)

        data = response.json()
        invoices = data.get("RepeatingInvoices", [])
        rate_limit = self._extract_rate_limit_state(response.headers)

        return invoices, rate_limit

    async def get_tracking_categories(
        self,
        access_token: str,
        tenant_id: str,
        include_archived: bool = False,
    ) -> tuple[list[dict[str, Any]], RateLimitState]:
        """Fetch tracking categories from Xero Accounting API.

        Args:
            access_token: Valid Xero access token.
            tenant_id: Xero tenant ID.
            include_archived: Include archived tracking categories.

        Returns:
            Tuple of (list of tracking category dicts, rate_limit_state).
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        params: dict[str, Any] = {}
        if include_archived:
            params["includeArchived"] = "true"

        response = await self.client.get(
            f"{self.settings.api_url}/TrackingCategories",
            headers=headers,
            params=params,
        )

        self._check_response(response)

        data = response.json()
        categories = data.get("TrackingCategories", [])
        rate_limit = self._extract_rate_limit_state(response.headers)

        return categories, rate_limit

    async def get_quotes(
        self,
        access_token: str,
        tenant_id: str,
        status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> tuple[list[dict[str, Any]], RateLimitState]:
        """Fetch quotes from Xero Accounting API.

        Args:
            access_token: Valid Xero access token.
            tenant_id: Xero tenant ID.
            status: Filter by status (DRAFT, SENT, DECLINED, ACCEPTED, INVOICED, DELETED).
            date_from: Filter by date from (YYYY-MM-DD).
            date_to: Filter by date to (YYYY-MM-DD).
            page: Page number for pagination.
            page_size: Number of items per page.

        Returns:
            Tuple of (list of quote dicts, rate_limit_state).
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        }

        # Build where clause for filtering
        where_clauses = []
        if status:
            where_clauses.append(f'Status=="{status}"')
        if date_from:
            where_clauses.append(f"Date>=DateTime({date_from.replace('-', ',')})")
        if date_to:
            where_clauses.append(f"Date<=DateTime({date_to.replace('-', ',')})")

        params: dict[str, Any] = {
            "page": page,
            "pageSize": min(page_size, 100),
        }
        if where_clauses:
            params["where"] = " && ".join(where_clauses)

        response = await self.client.get(
            f"{self.settings.api_url}/Quotes",
            headers=headers,
            params=params,
        )

        self._check_response(response)

        data = response.json()
        quotes = data.get("Quotes", [])
        rate_limit = self._extract_rate_limit_state(response.headers)

        return quotes, rate_limit
