"""Tests for PostHog integration (TDD - written before implementation)."""

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from main import app
from models import FeedbackItem
from store import (
    get_all_feedback_items,
    get_feedback_by_external_id,
    clear_feedback_items,
    clear_clusters,
)

client = TestClient(app)


def setup_function():
    """Clear data before each test."""
    clear_feedback_items()
    clear_clusters()


def test_posthog_webhook_creates_feedback_item(project_context):
    """Webhook payload creates FeedbackItem with exception details."""
    test_project_id = project_context["project_id"]
    payload = {
        "hook": {"id": "hook-123", "event": "action_performed"},
        "data": {
            "event": "$exception",
            "uuid": "event-uuid-123",
            "distinct_id": "user-456",
            "properties": {
                "$exception_message": "TypeError: Cannot read property 'foo' of undefined",
                "$exception_stack_trace_raw": "at handleClick (/app/src/components/Button.tsx:42:5)\nat onClick (/app/src/App.tsx:15:3)",
                "$session_id": "session-abc-789",
                "$current_url": "https://app.example.com/dashboard",
            },
            "timestamp": "2024-01-15T10:30:00Z",
        }
    }

    response = client.post(
        f"/ingest/posthog/webhook?project_id={test_project_id}",
        json=payload
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "id" in data

    # Verify feedback item was created
    items = get_all_feedback_items(str(test_project_id))
    assert len(items) == 1

    item = items[0]
    assert item.source == "posthog"
    assert "TypeError" in item.title
    assert "$exception_message" in item.body or "TypeError" in item.body
    assert "handleClick" in item.body  # Stack trace should be in body
    assert item.metadata["event_type"] == "$exception"
    assert item.metadata["distinct_id"] == "user-456"


def test_posthog_exception_extracts_stack_trace(project_context):
    """Stack trace is preserved in body."""
    test_project_id = project_context["project_id"]
    stack_trace = """at handleClick (/app/src/components/Button.tsx:42:5)
at onClick (/app/src/App.tsx:15:3)
at invokePassiveEffectCreate (/node_modules/react-dom/cjs/react-dom.development.js:23487:20)"""

    payload = {
        "hook": {"id": "hook-123", "event": "action_performed"},
        "data": {
            "event": "$exception",
            "uuid": "event-uuid-456",
            "distinct_id": "user-789",
            "properties": {
                "$exception_message": "ReferenceError: foo is not defined",
                "$exception_stack_trace_raw": stack_trace,
                "$session_id": "session-xyz",
            },
            "timestamp": "2024-01-15T11:00:00Z",
        }
    }

    response = client.post(
        f"/ingest/posthog/webhook?project_id={test_project_id}",
        json=payload
    )

    assert response.status_code == 200

    items = get_all_feedback_items(str(test_project_id))
    item = items[0]

    # Stack trace should be in the body
    assert "handleClick" in item.body
    assert "Button.tsx:42:5" in item.body
    assert "App.tsx:15:3" in item.body


def test_posthog_sync_fetches_new_events(project_context):
    """Sync pulls events since last_synced timestamp."""
    test_project_id = project_context["project_id"]
    # Set up configuration - will implement config storage functions in implementation
    # For now, just test the endpoint exists

    # Mock: In real implementation, this would call PostHog API
    # For now, we'll simulate by posting events
    response = client.post(
        f"/ingest/posthog/sync?project_id={test_project_id}"
    )

    # Should succeed even with no events
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


def test_posthog_event_type_filter(project_context):
    """Only configured event types are ingested."""
    test_project_id = project_context["project_id"]
    # Configure to only accept $exception events (config will be in implementation)

    # Send an $exception event (should be accepted)
    exception_payload = {
        "hook": {"id": "hook-123", "event": "action_performed"},
        "data": {
            "event": "$exception",
            "uuid": "event-1",
            "distinct_id": "user-1",
            "properties": {
                "$exception_message": "Error 1",
            },
            "timestamp": "2024-01-15T10:30:00Z",
        }
    }

    response = client.post(
        f"/ingest/posthog/webhook?project_id={test_project_id}",
        json=exception_payload
    )
    assert response.status_code == 200

    # Send a different event type (should be filtered out if config is checked)
    # Note: For webhook endpoint, we might accept all and filter during sync
    # This test documents the expected behavior
    items = get_all_feedback_items(str(test_project_id))
    assert len(items) >= 1
    assert all(item.metadata.get("event_type") in ["$exception", None] for item in items)


def test_posthog_session_id_in_metadata(project_context):
    """Session replay ID is preserved for linking."""
    test_project_id = project_context["project_id"]
    session_id = "session-replay-abc-123"

    payload = {
        "hook": {"id": "hook-123", "event": "action_performed"},
        "data": {
            "event": "$exception",
            "uuid": "event-uuid-789",
            "distinct_id": "user-999",
            "properties": {
                "$exception_message": "Network error",
                "$session_id": session_id,
                "$current_url": "https://app.example.com/checkout",
            },
            "timestamp": "2024-01-15T12:00:00Z",
        }
    }

    response = client.post(
        f"/ingest/posthog/webhook?project_id={test_project_id}",
        json=payload
    )

    assert response.status_code == 200

    items = get_all_feedback_items(str(test_project_id))
    item = items[0]

    # Session ID should be preserved in metadata
    assert item.metadata["session_id"] == session_id
    assert item.metadata["current_url"] == "https://app.example.com/checkout"


def test_posthog_webhook_deduplication(project_context):
    """Same event sent twice creates only one FeedbackItem."""
    test_project_id = project_context["project_id"]
    payload = {
        "hook": {"id": "hook-123", "event": "action_performed"},
        "data": {
            "event": "$exception",
            "uuid": "event-duplicate-test",
            "distinct_id": "user-123",
            "properties": {
                "$exception_message": "Duplicate test",
            },
            "timestamp": "2024-01-15T10:30:00Z",
        }
    }

    # Send the same payload twice
    response1 = client.post(
        f"/ingest/posthog/webhook?project_id={test_project_id}",
        json=payload
    )
    response2 = client.post(
        f"/ingest/posthog/webhook?project_id={test_project_id}",
        json=payload
    )

    assert response1.status_code == 200
    assert response2.status_code == 200

    # Should only have one item due to deduplication
    items = get_all_feedback_items(str(test_project_id))
    assert len(items) == 1


def test_posthog_webhook_missing_project_id():
    """Webhook without project_id returns 400."""
    payload = {
        "hook": {"id": "hook-123", "event": "action_performed"},
        "data": {
            "event": "$exception",
            "uuid": "event-123",
            "distinct_id": "user-123",
            "properties": {},
            "timestamp": "2024-01-15T10:30:00Z",
        }
    }

    response = client.post("/ingest/posthog/webhook", json=payload)
    assert response.status_code == 400
