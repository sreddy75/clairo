"""Xero webhook handler with HMAC-SHA256 signature verification.

This module provides:
- Signature verification for incoming Xero webhook requests
- Intent-to-receive validation for webhook registration
- Event deduplication by webhook_key
- Batching logic to group events by connection and entity type

Xero webhook payload format:
{
  "events": [
    {
      "resourceUrl": "https://api.xero.com/api.xro/2.0/Invoices/...",
      "resourceId": "<uuid>",
      "eventDateUtc": "2026-02-15T10:30:00.000Z",
      "eventType": "Update",
      "eventCategory": "INVOICE",
      "tenantId": "<xero-org-uuid>"
    }
  ],
  "firstEventSequence": 1,
  "lastEventSequence": 3,
  "entropy": "RANDOM_STRING"
}

Xero sends an X-Xero-Signature header containing a base64-encoded
HMAC-SHA256 hash of the raw request body, using the webhook signing key.

See: https://developer.xero.com/documentation/guides/webhooks/overview
"""

import base64
import hashlib
import hmac
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.xero.models import XeroWebhookEventStatus
from app.modules.integrations.xero.repository import (
    XeroConnectionRepository,
    XeroWebhookEventRepository,
)

logger = logging.getLogger(__name__)

# Batching window: events within this period for the same connection
# and entity type are grouped into a single targeted sync.
BATCH_WINDOW_SECONDS = 30

# Map Xero webhook event categories to our internal entity type names
# used by the sync_entity task and ENTITY_SYNC_MAP.
EVENT_CATEGORY_TO_ENTITY_TYPE: dict[str, str] = {
    "INVOICE": "invoices",
    "CONTACT": "contacts",
    "BANKTRANSACTION": "bank_transactions",
    "CREDITNOTE": "credit_notes",
    "PAYMENT": "payments",
    "OVERPAYMENT": "overpayments",
    "PREPAYMENT": "prepayments",
    "MANUALJOURNAL": "manual_journals",
    "ACCOUNT": "accounts",
    "PURCHASEORDER": "purchase_orders",
    "QUOTE": "quotes",
}


def verify_webhook_signature(
    payload: bytes,
    signature_header: str,
    webhook_key: str,
) -> bool:
    """Verify the HMAC-SHA256 signature of a Xero webhook payload.

    Xero computes a base64-encoded HMAC-SHA256 of the raw request body
    using the webhook signing key, and sends it in the X-Xero-Signature
    header. This function recomputes the HMAC and compares using a
    constant-time comparison to prevent timing attacks.

    Args:
        payload: Raw request body bytes.
        signature_header: Value of the X-Xero-Signature header.
        webhook_key: The webhook signing key from Xero Developer Portal.

    Returns:
        True if the signature is valid, False otherwise.
    """
    if not webhook_key:
        logger.error("Webhook key is not configured; cannot verify signature")
        return False

    # Compute HMAC-SHA256 of the payload using the webhook key
    computed_hash = hmac.new(
        key=webhook_key.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).digest()

    # Base64 encode the computed hash
    computed_signature = base64.b64encode(computed_hash).decode("utf-8")

    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(computed_signature, signature_header)


def is_intent_to_receive(payload_data: dict[str, Any]) -> bool:
    """Check if the webhook payload is an intent-to-receive validation request.

    When registering a webhook in the Xero Developer Portal, Xero sends
    a validation request with an empty events array. The application must
    respond with HTTP 200 to confirm it can receive webhooks.

    Args:
        payload_data: Parsed JSON payload from the webhook request.

    Returns:
        True if this is an intent-to-receive validation (empty events).
    """
    events = payload_data.get("events", [])
    return len(events) == 0


async def store_webhook_events(
    session: AsyncSession,
    payload_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Parse and store webhook events, deduplicating by webhook_key.

    Extracts events from the Xero webhook payload, resolves the Xero
    tenant ID to our internal connection, and stores each event as
    an XeroWebhookEvent record. Events with duplicate webhook_keys
    (already seen) are skipped.

    Args:
        session: Database session (should NOT have RLS context set,
            since we need to query across tenants).
        payload_data: Parsed JSON payload from the webhook request.

    Returns:
        List of dicts describing stored events, each with:
        - event_id: UUID of the stored event
        - connection_id: UUID of the matched connection
        - tenant_id: UUID of the owning tenant
        - event_category: Entity category (e.g., "INVOICE")
        - event_type: Event type (e.g., "Update")
        - resource_id: Xero entity ID
    """
    events = payload_data.get("events", [])
    if not events:
        return []

    conn_repo = XeroConnectionRepository(session)
    webhook_repo = XeroWebhookEventRepository(session)

    # Cache connection lookups by xero_tenant_id to avoid repeated queries
    connection_cache: dict[str, list[Any]] = {}
    stored_events: list[dict[str, Any]] = []

    for event in events:
        xero_tenant_id = event.get("tenantId", "")
        resource_id = event.get("resourceId", "")
        event_type = event.get("eventType", "")
        event_category = event.get("eventCategory", "")
        event_date_str = event.get("eventDateUtc", "")

        # Generate a deduplication key from the event data.
        # Xero does not provide a unique eventKey in the payload, so we
        # construct one from the combination of fields that uniquely
        # identify an event.
        webhook_key = (
            f"{xero_tenant_id}:{event_category}:{resource_id}:{event_type}:{event_date_str}"
        )

        # Check for duplicate (idempotency)
        existing = await webhook_repo.get_by_webhook_key(webhook_key)
        if existing:
            logger.debug(
                "Duplicate webhook event skipped",
                extra={"webhook_key": webhook_key},
            )
            continue

        # Resolve xero_tenant_id to our connection(s)
        if xero_tenant_id not in connection_cache:
            connections = await conn_repo.find_by_xero_tenant_id(xero_tenant_id)
            connection_cache[xero_tenant_id] = connections

        connections = connection_cache[xero_tenant_id]
        if not connections:
            logger.warning(
                "No active connection found for Xero tenant ID in webhook",
                extra={"xero_tenant_id": xero_tenant_id},
            )
            continue

        # Store an event for each matching connection (typically one,
        # but could be multiple if the same Xero org is connected
        # to multiple Clairo tenants).
        for connection in connections:
            try:
                stored = await webhook_repo.create(
                    tenant_id=connection.tenant_id,
                    connection_id=connection.id,
                    webhook_key=webhook_key,
                    event_type=event_type,
                    event_category=event_category,
                    resource_id=resource_id,
                    status=XeroWebhookEventStatus.PENDING,
                    raw_payload=event,
                )
                stored_events.append(
                    {
                        "event_id": stored.id,
                        "connection_id": connection.id,
                        "tenant_id": connection.tenant_id,
                        "event_category": event_category,
                        "event_type": event_type,
                        "resource_id": resource_id,
                    }
                )
                logger.info(
                    "Stored webhook event",
                    extra={
                        "webhook_key": webhook_key,
                        "connection_id": str(connection.id),
                        "event_category": event_category,
                    },
                )
            except Exception:
                # If a unique constraint violation occurs (race condition),
                # log and skip rather than failing the entire batch.
                logger.warning(
                    "Failed to store webhook event (possible duplicate)",
                    extra={"webhook_key": webhook_key},
                    exc_info=True,
                )
                continue

    return stored_events


def batch_events_by_connection_and_entity(
    events: list[Any],
) -> dict[tuple[uuid.UUID, str], list[Any]]:
    """Group webhook events by (connection_id, entity_type) for batched processing.

    Events within the BATCH_WINDOW_SECONDS for the same connection and
    entity type are grouped together, allowing a single targeted sync
    per entity type per connection rather than one sync per event.

    Args:
        events: List of XeroWebhookEvent model instances (pending events).

    Returns:
        Dict mapping (connection_id, entity_type) to list of events in that batch.
        Only events whose event_category maps to a known entity type are included.
    """
    batches: dict[tuple[uuid.UUID, str], list[Any]] = defaultdict(list)

    for event in events:
        # Map the Xero event category to our internal entity type
        entity_type = EVENT_CATEGORY_TO_ENTITY_TYPE.get(event.event_category)
        if not entity_type:
            logger.warning(
                "Unknown webhook event category, skipping",
                extra={"event_category": event.event_category},
            )
            continue

        batch_key = (event.connection_id, entity_type)
        batches[batch_key].append(event)

    return dict(batches)


def get_earliest_event_timestamp(events: list[Any]) -> datetime | None:
    """Get the earliest created_at timestamp from a list of events.

    Used to determine the modified_since parameter for targeted
    incremental sync — we need to fetch all records modified since
    the earliest event in the batch.

    Args:
        events: List of XeroWebhookEvent model instances.

    Returns:
        The earliest created_at datetime, or None if the list is empty.
    """
    if not events:
        return None

    # Use created_at as the reference timestamp. Subtract a small buffer
    # to account for clock skew between Xero and our system.
    earliest = min(event.created_at for event in events)
    return earliest - timedelta(seconds=BATCH_WINDOW_SECONDS)
