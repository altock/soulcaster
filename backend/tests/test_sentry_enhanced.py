"""Tests for enhanced Sentry integration features.

Following TDD: These tests are written BEFORE implementation.
They should initially fail, then pass once the implementation is complete.
"""

import hashlib
import hmac
import json
import pytest
from fastapi.testclient import TestClient

from main import app
from store import (
    clear_feedback_items,
    clear_clusters,
    clear_config,
    get_all_feedback_items,
    get_feedback_by_external_id,
    set_sentry_config,
)

client = TestClient(app)


@pytest.fixture
def disable_auto_clustering(monkeypatch):
    """Prevent auto-clustering from running during tests."""
    monkeypatch.setattr("main._kickoff_clustering", lambda _project_id: None)


def setup_function():
    """Clear test data before each test."""
    clear_feedback_items()
    clear_clusters()
    clear_config()  # Clear Sentry config too


def _create_sentry_payload(issue_short_id="ISSUE-123", event_id="evt_456"):
    """Create a sample Sentry webhook payload."""
    return {
        "data": {
            "issue": {
                "short_id": issue_short_id,
                "id": "12345",
            },
            "event": {
                "event_id": event_id,
                "level": "error",
                "platform": "python",
                "environment": "production",
            },
        },
        "message": "TypeError: Cannot read property 'foo'",
        "level": "error",
        "platform": "python",
        "exception": {
            "values": [
                {
                    "type": "TypeError",
                    "value": "Cannot read property 'foo' of undefined",
                    "stacktrace": {
                        "frames": [
                            {
                                "filename": "/app/main.py",
                                "lineno": 42,
                                "function": "process_data",
                            },
                            {
                                "filename": "/app/utils.py",
                                "lineno": 15,
                                "function": "helper",
                            },
                            {
                                "filename": "/app/lib.py",
                                "lineno": 88,
                                "function": "core_logic",
                            },
                        ]
                    },
                }
            ]
        },
    }


def _sign_payload(payload_dict: dict, secret: str) -> str:
    """Generate HMAC-SHA256 signature for Sentry webhook."""
    body = json.dumps(payload_dict, separators=(',', ':')).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return signature


def test_sentry_signature_verification_valid(project_context, disable_auto_clustering):
    """Valid HMAC signature passes and creates FeedbackItem."""
    pid = project_context["project_id"]
    secret = "test-secret-key"

    # Configure the webhook secret for this project
    set_sentry_config(str(pid), "webhook_secret", secret)

    payload = _create_sentry_payload()
    signature = _sign_payload(payload, secret)

    response = client.post(
        f"/ingest/sentry?project_id={pid}",
        json=payload,
        headers={"sentry-hook-signature": signature}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    items = get_all_feedback_items(str(pid))
    assert len(items) == 1


def test_sentry_signature_verification_invalid(project_context, disable_auto_clustering):
    """Invalid signature returns 401 Unauthorized."""
    pid = project_context["project_id"]
    secret = "test-secret-key"

    # Configure the webhook secret for this project
    set_sentry_config(str(pid), "webhook_secret", secret)

    payload = _create_sentry_payload()
    bad_signature = "invalid_signature_hash"

    response = client.post(
        f"/ingest/sentry?project_id={pid}",
        json=payload,
        headers={"sentry-hook-signature": bad_signature}
    )

    assert response.status_code == 401
    assert "signature" in response.json()["detail"].lower()

    # No feedback item should be created
    items = get_all_feedback_items(str(pid))
    assert len(items) == 0


def test_sentry_uses_issue_short_id_for_dedup(project_context, disable_auto_clustering):
    """Multiple events for same issue create only one FeedbackItem."""
    pid = project_context["project_id"]

    # First event for issue ISSUE-ABC
    payload1 = _create_sentry_payload(issue_short_id="ISSUE-ABC", event_id="evt_001")
    response1 = client.post(f"/ingest/sentry?project_id={pid}", json=payload1)
    assert response1.status_code == 200

    # Second event for same issue, different event_id
    payload2 = _create_sentry_payload(issue_short_id="ISSUE-ABC", event_id="evt_002")
    response2 = client.post(f"/ingest/sentry?project_id={pid}", json=payload2)
    assert response2.status_code == 200

    # Only one feedback item should exist (deduped by issue short_id)
    items = get_all_feedback_items(str(pid))
    assert len(items) == 1
    assert items[0].external_id == "ISSUE-ABC"


def test_sentry_stack_trace_normalized(project_context, disable_auto_clustering):
    """Stack frames are extracted and formatted in the body."""
    pid = project_context["project_id"]

    payload = _create_sentry_payload()
    response = client.post(f"/ingest/sentry?project_id={pid}", json=payload)

    assert response.status_code == 200

    items = get_all_feedback_items(str(pid))
    assert len(items) == 1

    item = items[0]
    # Body should contain formatted stack trace
    assert "/app/main.py:42" in item.body
    assert "/app/utils.py:15" in item.body
    assert "/app/lib.py:88" in item.body
    assert "process_data" in item.body
    assert "helper" in item.body
    assert "core_logic" in item.body


def test_sentry_environment_filter(project_context, disable_auto_clustering):
    """Only configured environments are ingested."""
    pid = project_context["project_id"]

    # Configure to only accept production and staging
    set_sentry_config(str(pid), "environments", ["production", "staging"])

    # Event from production (should be accepted)
    payload_prod = _create_sentry_payload()
    payload_prod["data"]["event"]["environment"] = "production"
    response1 = client.post(f"/ingest/sentry?project_id={pid}", json=payload_prod)
    assert response1.status_code == 200

    # Event from development (should be rejected)
    payload_dev = _create_sentry_payload(issue_short_id="ISSUE-DEV")
    payload_dev["data"]["event"]["environment"] = "development"
    response2 = client.post(f"/ingest/sentry?project_id={pid}", json=payload_dev)
    # Should return 200 but not create an item (filtered out)
    assert response2.status_code == 200

    # Only the production event should be stored
    items = get_all_feedback_items(str(pid))
    assert len(items) == 1
    assert items[0].metadata.get("environment") == "production"


def test_sentry_level_filter(project_context, disable_auto_clustering):
    """Only configured levels (error/fatal) are ingested."""
    pid = project_context["project_id"]

    # Configure to only accept error and fatal
    set_sentry_config(str(pid), "levels", ["error", "fatal"])

    # Error level event (should be accepted)
    payload_error = _create_sentry_payload()
    payload_error["level"] = "error"
    payload_error["data"]["event"]["level"] = "error"
    response1 = client.post(f"/ingest/sentry?project_id={pid}", json=payload_error)
    assert response1.status_code == 200

    # Warning level event (should be rejected)
    payload_warning = _create_sentry_payload(issue_short_id="ISSUE-WARN")
    payload_warning["level"] = "warning"
    payload_warning["data"]["event"]["level"] = "warning"
    response2 = client.post(f"/ingest/sentry?project_id={pid}", json=payload_warning)
    # Should return 200 but not create an item (filtered out)
    assert response2.status_code == 200

    # Only the error event should be stored
    items = get_all_feedback_items(str(pid))
    assert len(items) == 1
    # Check that it's the error-level one
    assert items[0].metadata.get("level") == "error"
