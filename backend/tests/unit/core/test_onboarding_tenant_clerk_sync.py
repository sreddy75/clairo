"""Regression tests for onboarding ↔ Clerk tenant sync.

`get_or_create_onboarding_tenant` used to create a tenant + PracticeUser in the
DB but never write that tenant into Clerk's ``public_metadata.tenant_id``. The
JWT therefore stayed unset/stale and could diverge from the user's real tenant —
and `get_current_tenant_id` (which trusts the JWT claim first) would then scope
the user to the wrong/empty tenant. These tests pin the fix: the dependency now
syncs Clerk whenever it resolves a tenant the JWT didn't already carry.

The dependency only touches ``session`` and the Clerk client, so we use a fake
session and a mocked Clerk client — no DB, no network.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.dependencies import get_or_create_onboarding_tenant
from app.modules.auth.clerk import ClerkTokenPayload
from app.modules.auth.models import UserRole


class _Result:
    def __init__(self, row: object) -> None:
        self._row = row

    def one_or_none(self) -> object:
        return self._row


class _FakeSession:
    """Minimal AsyncSession stand-in for the onboarding dependency."""

    def __init__(self, lookup_row: object = None) -> None:
        self._lookup_row = lookup_row
        self.added: list[object] = []
        self.committed = False

    async def execute(self, _stmt: object) -> _Result:
        return _Result(self._lookup_row)

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        # Mimic the DB assigning primary keys on flush.
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    async def commit(self) -> None:
        self.committed = True


def _request(tenant_id: uuid.UUID | None = None, email: str = "new.user@example.com") -> object:
    payload = ClerkTokenPayload(
        sub="user_clerk123",
        email=email,
        tenant_id=tenant_id,
        exp=9_999_999_999,
        iat=0,
    )
    return SimpleNamespace(state=SimpleNamespace(user=payload))


@pytest.fixture
def clerk_mock(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = MagicMock()
    mock.update_user_metadata = AsyncMock()
    monkeypatch.setattr(
        "app.modules.auth.clerk.get_clerk_client", lambda *a, **k: mock
    )
    return mock


class TestOnboardingClerkSync:
    async def test_new_user_creates_tenant_and_syncs_clerk(self, clerk_mock: MagicMock) -> None:
        """A brand-new user: tenant is created AND written into Clerk metadata."""
        session = _FakeSession(lookup_row=None)

        tenant_id = await get_or_create_onboarding_tenant(_request(), session)

        assert isinstance(tenant_id, uuid.UUID)
        assert session.committed is True
        clerk_mock.update_user_metadata.assert_awaited_once()
        kwargs = clerk_mock.update_user_metadata.await_args.kwargs
        assert kwargs["clerk_id"] == "user_clerk123"
        assert kwargs["public_metadata"] == {"tenant_id": str(tenant_id), "role": "admin"}

    async def test_existing_db_user_resyncs_clerk_with_real_role(
        self, clerk_mock: MagicMock
    ) -> None:
        """DB has a tenant but the JWT didn't carry it → re-sync Clerk (no new tenant)."""
        existing = uuid.uuid4()
        session = _FakeSession(lookup_row=(existing, UserRole.ACCOUNTANT))

        tenant_id = await get_or_create_onboarding_tenant(_request(), session)

        assert tenant_id == existing
        assert session.committed is False  # nothing created
        clerk_mock.update_user_metadata.assert_awaited_once()
        kwargs = clerk_mock.update_user_metadata.await_args.kwargs
        assert kwargs["public_metadata"] == {
            "tenant_id": str(existing),
            "role": "accountant",
        }

    async def test_jwt_tenant_present_is_trusted_no_clerk_write(
        self, clerk_mock: MagicMock
    ) -> None:
        """If the JWT already carries a tenant, return it and don't touch Clerk."""
        existing = uuid.uuid4()
        session = _FakeSession(lookup_row=None)

        tenant_id = await get_or_create_onboarding_tenant(_request(tenant_id=existing), session)

        assert tenant_id == existing
        clerk_mock.update_user_metadata.assert_not_awaited()

    async def test_clerk_failure_does_not_block_onboarding(self, clerk_mock: MagicMock) -> None:
        """A Clerk outage must not break onboarding — the tenant still resolves."""
        clerk_mock.update_user_metadata.side_effect = RuntimeError("clerk down")
        session = _FakeSession(lookup_row=None)

        tenant_id = await get_or_create_onboarding_tenant(_request(), session)

        assert isinstance(tenant_id, uuid.UUID)
        assert session.committed is True
