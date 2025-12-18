"""Datadog integration client for webhook handling.

This module provides functions to:
- Convert Datadog webhook events to FeedbackItem objects
- Verify webhook signatures for security
"""
import hashlib
import hmac
import time
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from models import FeedbackItem


def datadog_event_to_feedback_item(event: dict, project_id: str) -> FeedbackItem:
    """
    Convert a Datadog webhook event to a FeedbackItem.

    Implements deduplication by creating external_id with hour buckets:
    {alert_id}-{timestamp // 3600}. This means multiple alerts from the
    same monitor within the same hour will be deduplicated.

    Parameters:
        event (dict): Datadog webhook payload
        project_id (str): Project UUID to associate the feedback with

    Returns:
        FeedbackItem: Normalized feedback item ready for storage
    """
    # Extract required fields with defaults
    alert_id = event.get("id", str(uuid4()))
    timestamp = event.get("date", int(time.time()))

    # Create external_id with hour bucket for deduplication
    hour_bucket = timestamp // 3600
    external_id = f"{alert_id}-{hour_bucket}"

    # Extract optional fields
    title = event.get("title", "Datadog Alert")
    body = event.get("body", "")

    # Build metadata
    metadata = {
        "alert_type": event.get("alert_type"),
        "priority": event.get("priority"),
        "tags": event.get("tags", []),
        "org_id": event.get("org", {}).get("id"),
        "snapshot_url": event.get("snapshot"),
    }

    # Create FeedbackItem
    return FeedbackItem(
        id=uuid4(),
        project_id=project_id,
        source="datadog",
        external_id=external_id,
        title=title,
        body=body,
        raw_text=f"{title} {body}",
        metadata=metadata,
        created_at=datetime.fromtimestamp(timestamp, tz=timezone.utc),
    )


def verify_signature(payload_bytes: bytes, signature: str, secret: str) -> bool:
    """
    Verify Datadog webhook signature using HMAC-SHA256.

    Parameters:
        payload_bytes (bytes): Raw request body bytes
        signature (str): Signature from X-Datadog-Signature header
        secret (str): Configured webhook secret for this project

    Returns:
        bool: True if signature is valid, False otherwise
    """
    expected = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)
