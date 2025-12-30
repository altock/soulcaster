"""Tests for integration configuration endpoints.

This module tests the configuration API endpoints for:
- Splunk (webhook token, allowed searches)
- Datadog (webhook secret, allowed monitors)
- PostHog (event types)
- Sentry (webhook secret, environments, levels)
"""

import os
import pytest
from fastapi.testclient import TestClient

from main import app
from store import clear_config

client = TestClient(app)


def setup_function():
    """Clear config before each test."""
    clear_config()


# ============================================================
# SPLUNK CONFIG TESTS
# ============================================================

def test_get_splunk_config_empty_by_default(project_context):
    """GET /config/splunk should return empty config by default."""
    pid = project_context["project_id"]

    response = client.get(f"/config/splunk?project_id={pid}")

    assert response.status_code == 200
    data = response.json()
    assert data["webhook_token"] is None
    assert data["allowed_searches"] is None
    assert data["project_id"] == str(pid)


def test_get_splunk_config_requires_project_id():
    """GET /config/splunk should return 400 if project_id is missing."""
    response = client.get("/config/splunk")

    assert response.status_code == 400


def test_set_splunk_webhook_token(project_context):
    """POST /config/splunk/token should set and return the token."""
    pid = project_context["project_id"]

    response = client.post(
        f"/config/splunk/token?project_id={pid}",
        json={"token": "secret-token-123"}
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Verify it was stored
    get_response = client.get(f"/config/splunk?project_id={pid}")
    assert get_response.json()["webhook_token"] == "secret-token-123"


def test_set_splunk_webhook_token_requires_project_id():
    """POST /config/splunk/token should return 400 if project_id is missing."""
    response = client.post(
        "/config/splunk/token",
        json={"token": "secret-token-123"}
    )

    assert response.status_code == 400


def test_set_splunk_allowed_searches(project_context):
    """POST /config/splunk/searches should set and return the search list."""
    pid = project_context["project_id"]

    response = client.post(
        f"/config/splunk/searches?project_id={pid}",
        json={"searches": ["Search1", "Search2"]}
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Verify it was stored
    get_response = client.get(f"/config/splunk?project_id={pid}")
    assert get_response.json()["allowed_searches"] == ["Search1", "Search2"]


def test_set_splunk_allowed_searches_requires_project_id():
    """POST /config/splunk/searches should return 400 if project_id is missing."""
    response = client.post(
        "/config/splunk/searches",
        json={"searches": ["Search1"]}
    )

    assert response.status_code == 400


# ============================================================
# DATADOG CONFIG TESTS
# ============================================================

def test_get_datadog_config_empty_by_default(project_context):
    """GET /config/datadog should return empty config by default."""
    pid = project_context["project_id"]

    response = client.get(f"/config/datadog?project_id={pid}")

    assert response.status_code == 200
    data = response.json()
    assert data["webhook_secret"] is None
    assert data["allowed_monitors"] is None
    assert data["project_id"] == str(pid)


def test_get_datadog_config_requires_project_id():
    """GET /config/datadog should return 400 if project_id is missing."""
    response = client.get("/config/datadog")

    assert response.status_code == 400


def test_set_datadog_webhook_secret(project_context):
    """POST /config/datadog/secret should set and return the secret."""
    pid = project_context["project_id"]

    response = client.post(
        f"/config/datadog/secret?project_id={pid}",
        json={"secret": "dd-webhook-secret"}
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Verify it was stored
    get_response = client.get(f"/config/datadog?project_id={pid}")
    assert get_response.json()["webhook_secret"] == "dd-webhook-secret"


def test_set_datadog_webhook_secret_requires_project_id():
    """POST /config/datadog/secret should return 400 if project_id is missing."""
    response = client.post(
        "/config/datadog/secret",
        json={"secret": "dd-webhook-secret"}
    )

    assert response.status_code == 400


def test_set_datadog_allowed_monitors(project_context):
    """POST /config/datadog/monitors should set and return the monitor list."""
    pid = project_context["project_id"]

    response = client.post(
        f"/config/datadog/monitors?project_id={pid}",
        json={"monitors": ["123", "456"]}
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Verify it was stored
    get_response = client.get(f"/config/datadog?project_id={pid}")
    assert get_response.json()["allowed_monitors"] == ["123", "456"]


def test_set_datadog_allowed_monitors_wildcard(project_context):
    """POST /config/datadog/monitors should accept wildcard."""
    pid = project_context["project_id"]

    response = client.post(
        f"/config/datadog/monitors?project_id={pid}",
        json={"monitors": ["*"]}
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Verify it was stored
    get_response = client.get(f"/config/datadog?project_id={pid}")
    assert get_response.json()["allowed_monitors"] == ["*"]


def test_set_datadog_allowed_monitors_requires_project_id():
    """POST /config/datadog/monitors should return 400 if project_id is missing."""
    response = client.post(
        "/config/datadog/monitors",
        json={"monitors": ["123"]}
    )

    assert response.status_code == 400


# ============================================================
# POSTHOG CONFIG TESTS
# ============================================================

def test_get_posthog_config_empty_by_default(project_context):
    """GET /config/posthog should return empty config by default."""
    pid = project_context["project_id"]

    response = client.get(f"/config/posthog?project_id={pid}")

    assert response.status_code == 200
    data = response.json()
    assert data["event_types"] is None
    assert data["project_id"] == str(pid)


def test_get_posthog_config_requires_project_id():
    """GET /config/posthog should return 400 if project_id is missing."""
    response = client.get("/config/posthog")

    assert response.status_code == 400


def test_set_posthog_event_types(project_context):
    """POST /config/posthog/events should set and return the event types."""
    pid = project_context["project_id"]

    response = client.post(
        f"/config/posthog/events?project_id={pid}",
        json={"event_types": ["$exception", "$error"]}
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Verify it was stored
    get_response = client.get(f"/config/posthog?project_id={pid}")
    assert get_response.json()["event_types"] == ["$exception", "$error"]


def test_set_posthog_event_types_requires_project_id():
    """POST /config/posthog/events should return 400 if project_id is missing."""
    response = client.post(
        "/config/posthog/events",
        json={"event_types": ["$exception"]}
    )

    assert response.status_code == 400


# ============================================================
# SENTRY CONFIG TESTS
# ============================================================

def test_get_sentry_config_empty_by_default(project_context):
    """GET /config/sentry should return empty config by default."""
    pid = project_context["project_id"]

    response = client.get(f"/config/sentry?project_id={pid}")

    assert response.status_code == 200
    data = response.json()
    assert data["webhook_secret"] is None
    assert data["allowed_environments"] is None
    assert data["allowed_levels"] is None
    assert data["project_id"] == str(pid)


def test_get_sentry_config_requires_project_id():
    """GET /config/sentry should return 400 if project_id is missing."""
    response = client.get("/config/sentry")

    assert response.status_code == 400


def test_set_sentry_webhook_secret(project_context):
    """POST /config/sentry/secret should set and return the secret."""
    pid = project_context["project_id"]

    response = client.post(
        f"/config/sentry/secret?project_id={pid}",
        json={"secret": "sentry-webhook-secret"}
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Verify it was stored
    get_response = client.get(f"/config/sentry?project_id={pid}")
    assert get_response.json()["webhook_secret"] == "sentry-webhook-secret"


def test_set_sentry_webhook_secret_requires_project_id():
    """POST /config/sentry/secret should return 400 if project_id is missing."""
    response = client.post(
        "/config/sentry/secret",
        json={"secret": "sentry-webhook-secret"}
    )

    assert response.status_code == 400


def test_set_sentry_allowed_environments(project_context):
    """POST /config/sentry/environments should set and return the environment list."""
    pid = project_context["project_id"]

    response = client.post(
        f"/config/sentry/environments?project_id={pid}",
        json={"environments": ["production", "staging"]}
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Verify it was stored
    get_response = client.get(f"/config/sentry?project_id={pid}")
    assert get_response.json()["allowed_environments"] == ["production", "staging"]


def test_set_sentry_allowed_environments_requires_project_id():
    """POST /config/sentry/environments should return 400 if project_id is missing."""
    response = client.post(
        "/config/sentry/environments",
        json={"environments": ["production"]}
    )

    assert response.status_code == 400


def test_set_sentry_allowed_levels(project_context):
    """POST /config/sentry/levels should set and return the level list."""
    pid = project_context["project_id"]

    response = client.post(
        f"/config/sentry/levels?project_id={pid}",
        json={"levels": ["error", "fatal"]}
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Verify it was stored
    get_response = client.get(f"/config/sentry?project_id={pid}")
    assert get_response.json()["allowed_levels"] == ["error", "fatal"]


def test_set_sentry_allowed_levels_requires_project_id():
    """POST /config/sentry/levels should return 400 if project_id is missing."""
    response = client.post(
        "/config/sentry/levels",
        json={"levels": ["error"]}
    )

    assert response.status_code == 400


# ============================================================
# INTEGRATION ENABLED STATE TESTS
# ============================================================

def test_get_splunk_config_includes_enabled_default_true(project_context):
    """GET /config/splunk should include enabled=True by default."""
    pid = project_context["project_id"]

    response = client.get(f"/config/splunk?project_id={pid}")

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True


def test_set_splunk_enabled_state(project_context):
    """POST /config/splunk/enabled should set the enabled state."""
    pid = project_context["project_id"]

    # Disable Splunk
    response = client.post(
        f"/config/splunk/enabled?project_id={pid}",
        json={"enabled": False}
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Verify it was stored
    get_response = client.get(f"/config/splunk?project_id={pid}")
    assert get_response.json()["enabled"] is False

    # Enable Splunk
    response = client.post(
        f"/config/splunk/enabled?project_id={pid}",
        json={"enabled": True}
    )

    assert response.status_code == 200
    get_response = client.get(f"/config/splunk?project_id={pid}")
    assert get_response.json()["enabled"] is True


def test_set_splunk_enabled_requires_project_id():
    """POST /config/splunk/enabled should return 400 if project_id is missing."""
    response = client.post(
        "/config/splunk/enabled",
        json={"enabled": False}
    )

    assert response.status_code == 400


def test_get_datadog_config_includes_enabled_default_true(project_context):
    """GET /config/datadog should include enabled=True by default."""
    pid = project_context["project_id"]

    response = client.get(f"/config/datadog?project_id={pid}")

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True


def test_set_datadog_enabled_state(project_context):
    """POST /config/datadog/enabled should set the enabled state."""
    pid = project_context["project_id"]

    # Disable Datadog
    response = client.post(
        f"/config/datadog/enabled?project_id={pid}",
        json={"enabled": False}
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Verify it was stored
    get_response = client.get(f"/config/datadog?project_id={pid}")
    assert get_response.json()["enabled"] is False


def test_set_datadog_enabled_requires_project_id():
    """POST /config/datadog/enabled should return 400 if project_id is missing."""
    response = client.post(
        "/config/datadog/enabled",
        json={"enabled": False}
    )

    assert response.status_code == 400


def test_get_posthog_config_includes_enabled_default_true(project_context):
    """GET /config/posthog should include enabled=True by default."""
    pid = project_context["project_id"]

    response = client.get(f"/config/posthog?project_id={pid}")

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True


def test_set_posthog_enabled_state(project_context):
    """POST /config/posthog/enabled should set the enabled state."""
    pid = project_context["project_id"]

    # Disable PostHog
    response = client.post(
        f"/config/posthog/enabled?project_id={pid}",
        json={"enabled": False}
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Verify it was stored
    get_response = client.get(f"/config/posthog?project_id={pid}")
    assert get_response.json()["enabled"] is False


def test_set_posthog_enabled_requires_project_id():
    """POST /config/posthog/enabled should return 400 if project_id is missing."""
    response = client.post(
        "/config/posthog/enabled",
        json={"enabled": False}
    )

    assert response.status_code == 400


def test_get_sentry_config_includes_enabled_default_true(project_context):
    """GET /config/sentry should include enabled=True by default."""
    pid = project_context["project_id"]

    response = client.get(f"/config/sentry?project_id={pid}")

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True


def test_set_sentry_enabled_state(project_context):
    """POST /config/sentry/enabled should set the enabled state."""
    pid = project_context["project_id"]

    # Disable Sentry
    response = client.post(
        f"/config/sentry/enabled?project_id={pid}",
        json={"enabled": False}
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Verify it was stored
    get_response = client.get(f"/config/sentry?project_id={pid}")
    assert get_response.json()["enabled"] is False


def test_set_sentry_enabled_requires_project_id():
    """POST /config/sentry/enabled should return 400 if project_id is missing."""
    response = client.post(
        "/config/sentry/enabled",
        json={"enabled": False}
    )

    assert response.status_code == 400


# ============================================================
# GENERIC GET ENABLED ENDPOINT TESTS
# ============================================================

def test_get_integration_enabled_sentry_default_true(project_context):
    """GET /config/sentry/enabled should return enabled=True by default."""
    pid = project_context["project_id"]

    response = client.get(f"/config/sentry/enabled?project_id={pid}")

    assert response.status_code == 200
    assert response.json() == {"enabled": True}


def test_get_integration_enabled_after_set(project_context):
    """GET /config/sentry/enabled should reflect the value after POST."""
    pid = project_context["project_id"]

    # Disable Sentry
    client.post(
        f"/config/sentry/enabled?project_id={pid}",
        json={"enabled": False}
    )

    # Verify via GET /config/sentry/enabled
    response = client.get(f"/config/sentry/enabled?project_id={pid}")

    assert response.status_code == 200
    assert response.json() == {"enabled": False}


def test_get_integration_enabled_invalid_integration(project_context):
    """GET /config/invalid/enabled should return 400."""
    pid = project_context["project_id"]

    response = client.get(f"/config/invalid/enabled?project_id={pid}")

    assert response.status_code == 400
    assert "Invalid integration" in response.json()["detail"]


def test_get_integration_enabled_requires_project_id():
    """GET /config/sentry/enabled should return 400 if project_id is missing."""
    response = client.get("/config/sentry/enabled")

    assert response.status_code == 400
