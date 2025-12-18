"""Test suite for Splunk integration following TDD."""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from main import app
from store import (
    clear_feedback_items,
    clear_clusters,
    get_all_feedback_items,
    get_feedback_by_external_id,
    clear_config,
)
from splunk_client import set_splunk_webhook_token, set_splunk_allowed_searches

client = TestClient(app)


def setup_function():
    """Reset test data before each test."""
    clear_feedback_items()
    clear_clusters()
    clear_config()


def test_splunk_webhook_creates_feedback_item(project_context):
    """Alert payload creates FeedbackItem with log data."""
    pid = project_context["project_id"]

    # Set webhook token for auth
    set_splunk_webhook_token(str(pid), "test_token_123")

    payload = {
        "result": {
            "_raw": "2024-01-15 10:30:00 ERROR [api] Request failed: connection timeout",
            "_time": "1705315800",
            "host": "web-server-1",
            "source": "/var/log/api.log",
            "sourcetype": "api_logs"
        },
        "sid": "scheduler__admin__search__1705315800",
        "search_name": "API Error Rate > 5%",
        "app": "search",
        "owner": "admin",
        "results_link": "https://splunk.example.com/app/search?sid=scheduler__admin__search__1705315800"
    }

    response = client.post(
        f"/ingest/splunk/webhook?project_id={pid}&token=test_token_123",
        json=payload
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    items = get_all_feedback_items(str(pid))
    assert len(items) == 1
    assert items[0].source == "splunk"
    assert items[0].external_id == "scheduler__admin__search__1705315800"


def test_splunk_search_name_in_title(project_context):
    """Search name is prefixed to title."""
    pid = project_context["project_id"]

    set_splunk_webhook_token(str(pid), "test_token_123")

    payload = {
        "result": {
            "_raw": "Error in production",
            "_time": "1705315800",
        },
        "sid": "test_sid_001",
        "search_name": "Production Errors",
        "results_link": "https://splunk.example.com/search"
    }

    response = client.post(
        f"/ingest/splunk/webhook?project_id={pid}&token=test_token_123",
        json=payload
    )

    assert response.status_code == 200

    items = get_all_feedback_items(str(pid))
    assert len(items) == 1
    assert items[0].title == "[Splunk] Production Errors"


def test_splunk_raw_log_preserved(project_context):
    """Raw log line is preserved in body."""
    pid = project_context["project_id"]

    set_splunk_webhook_token(str(pid), "test_token_123")

    raw_log = "2024-01-15 ERROR Critical failure in payment processing"
    payload = {
        "result": {
            "_raw": raw_log,
            "_time": "1705315800",
        },
        "sid": "test_sid_002",
        "search_name": "Payment Errors",
    }

    response = client.post(
        f"/ingest/splunk/webhook?project_id={pid}&token=test_token_123",
        json=payload
    )

    assert response.status_code == 200

    items = get_all_feedback_items(str(pid))
    assert len(items) == 1
    assert items[0].body == raw_log


def test_splunk_results_link_in_metadata(project_context):
    """Splunk results link is preserved for drill-down."""
    pid = project_context["project_id"]

    set_splunk_webhook_token(str(pid), "test_token_123")

    results_link = "https://splunk.example.com/app/search?sid=test_sid"
    payload = {
        "result": {
            "_raw": "Error occurred",
            "_time": "1705315800",
            "host": "server-1",
            "source": "/var/log/app.log",
            "sourcetype": "app_logs"
        },
        "sid": "test_sid_003",
        "search_name": "App Errors",
        "results_link": results_link,
        "app": "search",
    }

    response = client.post(
        f"/ingest/splunk/webhook?project_id={pid}&token=test_token_123",
        json=payload
    )

    assert response.status_code == 200

    items = get_all_feedback_items(str(pid))
    assert len(items) == 1
    assert items[0].metadata["results_link"] == results_link
    assert items[0].metadata["search_name"] == "App Errors"
    assert items[0].metadata["host"] == "server-1"
    assert items[0].metadata["source"] == "/var/log/app.log"
    assert items[0].metadata["sourcetype"] == "app_logs"


def test_splunk_search_filter(project_context):
    """Only configured saved searches are ingested."""
    pid = project_context["project_id"]

    # Configure to only accept "Critical Errors" search
    set_splunk_webhook_token(str(pid), "test_token_123")
    set_splunk_allowed_searches(str(pid), ["Critical Errors"])

    # This should be accepted
    allowed_payload = {
        "result": {
            "_raw": "Critical error",
            "_time": "1705315800",
        },
        "sid": "test_sid_allowed",
        "search_name": "Critical Errors",
    }

    response = client.post(
        f"/ingest/splunk/webhook?project_id={pid}&token=test_token_123",
        json=allowed_payload
    )
    assert response.status_code == 200

    # This should be rejected
    blocked_payload = {
        "result": {
            "_raw": "Info message",
            "_time": "1705315801",
        },
        "sid": "test_sid_blocked",
        "search_name": "Info Messages",
    }

    response = client.post(
        f"/ingest/splunk/webhook?project_id={pid}&token=test_token_123",
        json=blocked_payload
    )
    # Should still return 200 but not create item
    assert response.status_code == 200

    items = get_all_feedback_items(str(pid))
    # Only the allowed search should create an item
    assert len(items) == 1
    assert items[0].metadata["search_name"] == "Critical Errors"


def test_splunk_token_auth_required(project_context):
    """Missing/invalid token returns 401."""
    pid = project_context["project_id"]

    set_splunk_webhook_token(str(pid), "correct_token")

    payload = {
        "result": {
            "_raw": "Error",
            "_time": "1705315800",
        },
        "sid": "test_sid",
        "search_name": "Errors",
    }

    # Test missing token
    response = client.post(
        f"/ingest/splunk/webhook?project_id={pid}",
        json=payload
    )
    assert response.status_code == 401

    # Test invalid token
    response = client.post(
        f"/ingest/splunk/webhook?project_id={pid}&token=wrong_token",
        json=payload
    )
    assert response.status_code == 401

    # Test valid token
    response = client.post(
        f"/ingest/splunk/webhook?project_id={pid}&token=correct_token",
        json=payload
    )
    assert response.status_code == 200


def test_splunk_token_auth_via_header(project_context):
    """Token can be provided via X-Splunk-Token header."""
    pid = project_context["project_id"]

    set_splunk_webhook_token(str(pid), "header_token")

    payload = {
        "result": {
            "_raw": "Error",
            "_time": "1705315800",
        },
        "sid": "test_sid_header",
        "search_name": "Errors",
    }

    response = client.post(
        f"/ingest/splunk/webhook?project_id={pid}",
        json=payload,
        headers={"X-Splunk-Token": "header_token"}
    )
    assert response.status_code == 200


def test_splunk_minimal_payload(project_context):
    """Handle minimal Splunk payload gracefully."""
    pid = project_context["project_id"]

    set_splunk_webhook_token(str(pid), "test_token")

    # Minimal payload with just the essentials
    payload = {
        "result": {
            "_raw": "Minimal log entry",
        },
    }

    response = client.post(
        f"/ingest/splunk/webhook?project_id={pid}&token=test_token",
        json=payload
    )

    assert response.status_code == 200

    items = get_all_feedback_items(str(pid))
    assert len(items) == 1
    assert items[0].body == "Minimal log entry"
    assert items[0].title == "[Splunk] Splunk Alert"  # Default title


def test_splunk_deduplication_by_sid(project_context):
    """Same SID should deduplicate."""
    pid = project_context["project_id"]

    set_splunk_webhook_token(str(pid), "test_token")

    payload = {
        "result": {
            "_raw": "Duplicate test",
            "_time": "1705315800",
        },
        "sid": "duplicate_sid",
        "search_name": "Test Search",
    }

    # First ingestion
    response1 = client.post(
        f"/ingest/splunk/webhook?project_id={pid}&token=test_token",
        json=payload
    )
    assert response1.status_code == 200
    assert response1.json()["status"] == "ok"

    # Second ingestion with same SID
    response2 = client.post(
        f"/ingest/splunk/webhook?project_id={pid}&token=test_token",
        json=payload
    )
    assert response2.status_code == 200
    assert response2.json()["status"] == "duplicate"

    # Should only have one item
    items = get_all_feedback_items(str(pid))
    assert len(items) == 1
