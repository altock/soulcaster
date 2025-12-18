"""TDD tests for Datadog integration.

These tests are written BEFORE implementation following strict TDD principles.
"""
import hashlib
import hmac
import time
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from main import app
from store import (
    clear_feedback_items,
    get_all_feedback_items,
    get_feedback_by_external_id,
)

client = TestClient(app)


def setup_function():
    """Reset persistent test data by clearing all stored feedback items."""
    clear_feedback_items()


@pytest.fixture
def sample_datadog_event():
    """Sample Datadog webhook payload matching the spec."""
    return {
        "id": "1234567890",
        "title": "[Triggered] CPU > 90% on web-server-1",
        "body": "Monitor 'High CPU Usage' triggered at 2024-01-15 10:30:00 UTC",
        "alert_type": "error",
        "priority": "normal",
        "tags": ["env:production", "service:api", "host:web-server-1"],
        "date": 1705315800,  # 2024-01-15 10:30:00 UTC
        "org": {"id": "abc123", "name": "Acme Corp"},
        "snapshot": "https://p.datadoghq.com/snapshot/abc123",
    }


def test_datadog_webhook_creates_feedback_item(project_context, sample_datadog_event):
    """Webhook payload creates a new FeedbackItem with correct mapping."""
    pid = project_context["project_id"]

    response = client.post(
        f"/ingest/datadog/webhook?project_id={pid}",
        json=sample_datadog_event,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "id" in data

    # Verify FeedbackItem was created
    items = get_all_feedback_items(str(pid))
    assert len(items) == 1

    item = items[0]
    assert item.source == "datadog"
    assert item.title == "[Triggered] CPU > 90% on web-server-1"
    assert item.body == "Monitor 'High CPU Usage' triggered at 2024-01-15 10:30:00 UTC"

    # Verify external_id format includes hour bucket for deduplication
    expected_hour_bucket = 1705315800 // 3600  # 473698
    assert item.external_id == f"1234567890-{expected_hour_bucket}"

    # Verify timestamp mapping
    assert item.created_at == datetime.fromtimestamp(1705315800, tz=timezone.utc)


def test_datadog_webhook_deduplicates_by_hour(project_context, sample_datadog_event):
    """Same alert within an hour creates only one FeedbackItem."""
    pid = project_context["project_id"]

    # First event
    response1 = client.post(
        f"/ingest/datadog/webhook?project_id={pid}",
        json=sample_datadog_event,
    )
    assert response1.status_code == 200
    assert response1.json()["status"] == "ok"

    # Second event 5 minutes later (same hour bucket)
    # Original timestamp is 50 minutes into the hour, so +5 minutes = 55 minutes (still same hour)
    event_5min_later = sample_datadog_event.copy()
    event_5min_later["date"] = 1705315800 + 300  # +5 minutes, still in same hour

    response2 = client.post(
        f"/ingest/datadog/webhook?project_id={pid}",
        json=event_5min_later,
    )
    assert response2.status_code == 200
    assert response2.json()["status"] == "duplicate"

    # Should still have only one item
    items = get_all_feedback_items(str(pid))
    assert len(items) == 1

    # Third event in next hour (different hour bucket)
    # Original is 50 minutes into hour, so +15 minutes = 5 minutes into next hour
    event_next_hour = sample_datadog_event.copy()
    event_next_hour["date"] = 1705315800 + 900  # +15 minutes = next hour bucket

    response3 = client.post(
        f"/ingest/datadog/webhook?project_id={pid}",
        json=event_next_hour,
    )
    assert response3.status_code == 200
    assert response3.json()["status"] == "ok"

    # Now should have two items (different hour buckets)
    items = get_all_feedback_items(str(pid))
    assert len(items) == 2


def test_datadog_webhook_rejects_invalid_signature(project_context, sample_datadog_event, monkeypatch):
    """Invalid signature returns 401 when secret is configured."""
    pid = project_context["project_id"]

    # Mock that a webhook secret is configured
    def mock_get_secret(project_id: str):
        return "test-secret-key"

    monkeypatch.setattr("main.get_datadog_webhook_secret_for_project", mock_get_secret)

    # Make request with invalid signature
    response = client.post(
        f"/ingest/datadog/webhook?project_id={pid}",
        json=sample_datadog_event,
        headers={"X-Datadog-Signature": "invalid-signature"},
    )

    assert response.status_code == 401
    assert "signature" in response.json()["detail"].lower()

    # No item should be created
    items = get_all_feedback_items(str(pid))
    assert len(items) == 0


def test_datadog_webhook_accepts_valid_signature(project_context, sample_datadog_event, monkeypatch):
    """Valid signature passes when secret is configured."""
    import json

    pid = project_context["project_id"]
    secret = "test-secret-key"

    # Mock that a webhook secret is configured
    def mock_get_secret(project_id: str):
        return secret

    monkeypatch.setattr("main.get_datadog_webhook_secret_for_project", mock_get_secret)

    # Calculate valid signature using the exact JSON serialization TestClient will use
    # TestClient uses json.dumps with separators=(',', ':') and ensure_ascii=True
    payload_str = json.dumps(sample_datadog_event, separators=(',', ':'), sort_keys=False, ensure_ascii=True)
    payload_bytes = payload_str.encode('utf-8')
    signature = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()

    # Make request with valid signature
    response = client.post(
        f"/ingest/datadog/webhook?project_id={pid}",
        json=sample_datadog_event,
        headers={"X-Datadog-Signature": signature},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # Item should be created
    items = get_all_feedback_items(str(pid))
    assert len(items) == 1


def test_datadog_tags_stored_in_metadata(project_context, sample_datadog_event):
    """Tags from alert are preserved in metadata."""
    pid = project_context["project_id"]

    response = client.post(
        f"/ingest/datadog/webhook?project_id={pid}",
        json=sample_datadog_event,
    )

    assert response.status_code == 200

    items = get_all_feedback_items(str(pid))
    assert len(items) == 1

    item = items[0]
    assert "tags" in item.metadata
    assert item.metadata["tags"] == ["env:production", "service:api", "host:web-server-1"]

    # Verify other metadata fields
    assert item.metadata["alert_type"] == "error"
    assert item.metadata["priority"] == "normal"
    assert item.metadata["org_id"] == "abc123"
    assert item.metadata["snapshot_url"] == "https://p.datadoghq.com/snapshot/abc123"


def test_datadog_monitor_filter_applied(project_context, sample_datadog_event, monkeypatch):
    """Only configured monitors create feedback items."""
    pid = project_context["project_id"]

    # Mock that only specific monitors are configured
    def mock_get_monitors(project_id: str):
        return ["9999999999"]  # Different monitor ID

    monkeypatch.setattr("main.get_datadog_monitors_for_project", mock_get_monitors)

    # Event from unconfigured monitor should be rejected
    response = client.post(
        f"/ingest/datadog/webhook?project_id={pid}",
        json=sample_datadog_event,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "skipped"

    # No item should be created
    items = get_all_feedback_items(str(pid))
    assert len(items) == 0

    # Now test with matching monitor ID
    def mock_get_monitors_match(project_id: str):
        return ["1234567890"]  # Matching monitor ID

    monkeypatch.setattr("main.get_datadog_monitors_for_project", mock_get_monitors_match)

    response = client.post(
        f"/ingest/datadog/webhook?project_id={pid}",
        json=sample_datadog_event,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # Item should be created
    items = get_all_feedback_items(str(pid))
    assert len(items) == 1


def test_datadog_monitor_wildcard_accepts_all(project_context, sample_datadog_event, monkeypatch):
    """Wildcard '*' configuration accepts all monitors."""
    pid = project_context["project_id"]

    # Mock wildcard configuration
    def mock_get_monitors(project_id: str):
        return ["*"]

    monkeypatch.setattr("main.get_datadog_monitors_for_project", mock_get_monitors)

    response = client.post(
        f"/ingest/datadog/webhook?project_id={pid}",
        json=sample_datadog_event,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # Item should be created
    items = get_all_feedback_items(str(pid))
    assert len(items) == 1


def test_datadog_no_filter_accepts_all(project_context, sample_datadog_event, monkeypatch):
    """No monitor filter configured accepts all monitors."""
    pid = project_context["project_id"]

    # Mock no configuration (None)
    def mock_get_monitors(project_id: str):
        return None

    monkeypatch.setattr("main.get_datadog_monitors_for_project", mock_get_monitors)

    response = client.post(
        f"/ingest/datadog/webhook?project_id={pid}",
        json=sample_datadog_event,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # Item should be created
    items = get_all_feedback_items(str(pid))
    assert len(items) == 1


def test_datadog_handles_missing_optional_fields(project_context):
    """Webhook handles missing optional fields gracefully."""
    pid = project_context["project_id"]

    # Minimal payload
    minimal_event = {
        "id": "minimal123",
        "date": int(time.time()),
    }

    response = client.post(
        f"/ingest/datadog/webhook?project_id={pid}",
        json=minimal_event,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    items = get_all_feedback_items(str(pid))
    assert len(items) == 1

    item = items[0]
    assert item.source == "datadog"
    assert item.title == "Datadog Alert"  # Default title
    assert item.body == ""  # Empty body
    assert item.metadata["tags"] == []  # Empty tags
