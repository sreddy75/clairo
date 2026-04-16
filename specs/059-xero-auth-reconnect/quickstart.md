# Developer Quickstart: 059-xero-auth-reconnect

**What this feature does**: Fixes a token refresh race condition that causes erroneous Xero re-auth prompts. Adds a global reconnection notification for genuine re-auth needs.

**Estimated scope**: ~400 lines backend, ~150 lines frontend. No new services, no new tables (one column).

---

## Local Setup

No new infrastructure required. Uses existing PostgreSQL, Redis, and Xero dev credentials.

```bash
# Start services
docker-compose up -d

# Run migrations after implementing the Alembic file
cd backend && uv run alembic upgrade head

# Verify migration
cd backend && uv run alembic current
```

---

## Implementation Order

Follow this order — each step has a clear test gate before moving on.

### Step 1: Database Migration

Add `oauth_grant_id` to `xero_connections`:

```bash
cd backend && uv run alembic revision --autogenerate -m "xero_add_oauth_grant_id"
# Then edit the generated file to add the back-fill logic (see data-model.md)
cd backend && uv run alembic upgrade head
```

Verify back-fill worked:
```sql
SELECT COUNT(*) FROM xero_connections WHERE oauth_grant_id IS NULL;
-- Should be 0
```

### Step 2: Update `XeroConnection` Model

In `modules/integrations/xero/models.py`:
```python
oauth_grant_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    nullable=False,
    default=uuid.uuid4,
    index=True,
)
```

### Step 3: Update `oauth_service.py` — Set Grant ID at Callback

When creating connections in `handle_callback`, generate one `oauth_grant_id` and assign it to all connections created in that callback:

```python
oauth_grant_id = uuid.uuid4()
for org in organizations:
    connection = XeroConnection(
        oauth_grant_id=oauth_grant_id,  # same value for all
        ...
    )
```

### Step 4: Rewrite `connection_service.py` — Grant-Scoped Lock

Key changes in `_refresh_with_lock`:
1. Lock key: `xero_token_refresh:grant:{connection.oauth_grant_id}`
2. After refresh: query all connections with same `oauth_grant_id` + `tenant_id`, update all
3. On `invalid_grant`: re-read DB before marking `needs_reauth`
4. Redis fallback: catch `RedisError`, log warning, refresh without lock

**Test gate**: Run concurrent refresh test before proceeding (see Testing section).

### Step 5: Consolidate Token Paths

Replace direct `refresh_tokens()` calls and raw `encryption.decrypt()` calls in:
- `data_service._get_connection_with_token` → `await connection_service.ensure_valid_token(connection_id)`
- `report_service._get_connection_and_token` → same
- `payroll_service` → same
- `xpm_service` → same
- `bas/router get_org_tax_rates` → same (and handle `XeroAuthRequiredError` instead of returning `{}`)
- `xero_writeback` task → same (remove the inline refresh loop)

**Test gate**: All existing xero integration tests still pass.

### Step 6: Add `GET /status` Endpoint

In `modules/integrations/xero/router.py`:

```python
@router.get("/status", response_model=XeroAuthStatusResponse)
async def get_xero_auth_status(
    current_user: PracticeUser = Depends(get_current_practice_user),
    connection_repo: XeroConnectionRepository = Depends(get_connection_repo),
) -> XeroAuthStatusResponse:
    connections = await connection_repo.list_by_tenant(current_user.tenant_id)
    needs_reauth = [
        XeroConnectionSummary(connection_id=c.id, org_name=c.organization_name)
        for c in connections
        if c.status == XeroConnectionStatus.NEEDS_REAUTH
    ]
    active = sum(1 for c in connections if c.status == XeroConnectionStatus.ACTIVE)
    return XeroAuthStatusResponse(
        needs_reauth=needs_reauth,
        total_connections=len(connections),
        active_connections=active,
    )
```

### Step 7: Frontend — XeroAuthProvider + Banner

New files:
- `frontend/src/lib/xero-auth-context.tsx` — React context, polls `/status`
- `frontend/src/components/xero/XeroReauthBanner.tsx` — notification banner

Wrap authenticated layout in `XeroAuthProvider`. Banner renders inside provider.

Extend `app/settings/integrations/xero/callback/page.tsx` to read `sessionStorage.getItem('xero_reauth_return_to')` for all pages (it currently only handles Tax Planning return).

---

## Testing

### P1: Concurrent Refresh Test (Critical)

```python
# tests/unit/modules/integrations/xero/test_connection_service.py

async def test_concurrent_refresh_no_invalid_grant(
    db_session, mock_xero_client, redis_client
):
    """
    Two sibling connections both hit the refresh window simultaneously.
    Only one Xero token refresh call should occur.
    Both connections should have fresh tokens after.
    Zero needs_reauth transitions.
    """
    # Setup: two connections, same oauth_grant_id, near-expired tokens
    grant_id = uuid.uuid4()
    conn_a = await create_connection(db_session, oauth_grant_id=grant_id, nearly_expired=True)
    conn_b = await create_connection(db_session, oauth_grant_id=grant_id, nearly_expired=True)

    mock_xero_client.refresh_token.return_value = (new_tokens, expires_at)

    # Run concurrent ensure_valid_token for both connections
    results = await asyncio.gather(
        connection_service.ensure_valid_token(conn_a.id),
        connection_service.ensure_valid_token(conn_b.id),
    )

    # Assert: exactly one Xero API call
    assert mock_xero_client.refresh_token.call_count == 1

    # Assert: both connections have the new token
    refreshed_a = await connection_repo.get_by_id(conn_a.id)
    refreshed_b = await connection_repo.get_by_id(conn_b.id)
    assert refreshed_a.status == XeroConnectionStatus.ACTIVE
    assert refreshed_b.status == XeroConnectionStatus.ACTIVE

    # Assert: no needs_reauth transitions
    assert refreshed_a.status != XeroConnectionStatus.NEEDS_REAUTH
    assert refreshed_b.status != XeroConnectionStatus.NEEDS_REAUTH
```

### P1: Redis Fallback Test

```python
async def test_redis_unavailable_refresh_succeeds(db_session, mock_xero_client):
    """If Redis is down, refresh proceeds without lock (best-effort)."""
    conn = await create_connection(db_session, nearly_expired=True)

    with patch("aioredis.from_url", side_effect=ConnectionError("Redis down")):
        token = await connection_service.ensure_valid_token(conn.id)

    assert token is not None  # refresh succeeded without lock
    # Warning was logged (check log capture)
```

### P1: Retry-Before-Reauth Test

```python
async def test_invalid_grant_retry_uses_sibling_tokens(db_session, mock_xero_client):
    """
    If invalid_grant received but sibling already refreshed,
    re-reads DB and uses fresh tokens instead of marking needs_reauth.
    """
    grant_id = uuid.uuid4()
    conn_a = await create_connection(db_session, oauth_grant_id=grant_id, nearly_expired=True)
    conn_b = await create_connection(db_session, oauth_grant_id=grant_id, nearly_expired=True)

    # Simulate: conn_b tries to refresh but gets invalid_grant
    # Meanwhile conn_a already refreshed and propagated fresh tokens
    # (conn_b's DB record should now have valid tokens from propagation)
    await update_connection_tokens(db_session, conn_b.id, fresh_tokens, future_expiry)

    mock_xero_client.refresh_token.side_effect = XeroAuthError("invalid_grant", 400)

    token = await connection_service.ensure_valid_token(conn_b.id)

    # Should not raise, should not mark needs_reauth
    assert token is not None
    refreshed = await connection_repo.get_by_id(conn_b.id)
    assert refreshed.status == XeroConnectionStatus.ACTIVE
```

### P2: Status Endpoint Test

```python
# tests/integration/api/test_xero_status.py

async def test_get_xero_status_returns_needs_reauth_connections(client, db_session, auth_headers):
    await set_connection_status(db_session, conn_id, "needs_reauth")
    response = await client.get("/api/v1/integrations/xero/status", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["needs_reauth"]) == 1
    assert data["needs_reauth"][0]["org_name"] == "Smith & Co"
```

---

## Common Pitfalls

- **Do not** back-fill `oauth_grant_id` using `refresh_token` values — tokens rotate and blobs will differ for connections that share a grant but have already had one refresh
- **Do not** use `asyncio.sleep` in the retry logic — re-read DB once and proceed or fail fast
- **Always** pass `tenant_id` in the grant group query — missing it breaks multi-tenancy isolation
- **Always** flush token updates for all siblings in a single `db.flush()` call or in a tight loop before releasing the lock
- The `XeroAuthRequiredError` should be a domain exception (not `HTTPException`) — convert to HTTP 401/403 at the router layer only
