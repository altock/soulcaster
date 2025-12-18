"""Splunk webhook integration client.

This module provides utilities for processing Splunk alert webhooks and
converting them into FeedbackItems for clustering and analysis.
"""

import json
import hmac
from datetime import datetime, timezone
from typing import Optional, List
from uuid import uuid4

from models import FeedbackItem
from store import get_splunk_config, set_splunk_config


def splunk_alert_to_feedback_item(alert: dict, project_id: str) -> FeedbackItem:
    """
    Convert a Splunk alert webhook payload into a FeedbackItem.

    Args:
        alert: Splunk alert payload containing result, sid, search_name, etc.
        project_id: Project identifier to associate the feedback with.

    Returns:
        FeedbackItem: Normalized feedback item ready for storage and clustering.

    Example payload:
        {
          "result": {
            "_raw": "2024-01-15 10:30:00 ERROR [api] Request failed",
            "_time": "1705315800",
            "host": "web-server-1",
            "source": "/var/log/api.log",
            "sourcetype": "api_logs"
          },
          "sid": "scheduler__admin__search__1705315800",
          "search_name": "API Error Rate > 5%",
          "app": "search",
          "owner": "admin",
          "results_link": "https://splunk.example.com/..."
        }
    """
    result = alert.get("result", {})
    search_name = alert.get("search_name", "Splunk Alert")
    raw_log = result.get("_raw", "")

    # Extract timestamp from _time field (Unix timestamp)
    time_value = result.get("_time")
    if time_value:
        try:
            created_at = datetime.fromtimestamp(int(time_value), tz=timezone.utc)
        except (ValueError, TypeError):
            created_at = datetime.now(timezone.utc)
    else:
        created_at = datetime.now(timezone.utc)

    return FeedbackItem(
        id=uuid4(),
        project_id=project_id,
        source="splunk",
        external_id=alert.get("sid", str(uuid4())),
        title=f"[Splunk] {search_name}",
        body=raw_log,
        raw_text=f"{search_name} {raw_log}",
        metadata={
            "search_name": search_name,
            "sid": alert.get("sid"),
            "host": result.get("host"),
            "source": result.get("source"),
            "sourcetype": result.get("sourcetype"),
            "results_link": alert.get("results_link"),
            "app": alert.get("app"),
            "owner": alert.get("owner"),
        },
        created_at=created_at,
    )


def verify_token(provided_token: Optional[str], project_id: str) -> bool:
    """
    Verify that the provided webhook token matches the configured token for the project.

    Args:
        provided_token: Token from query parameter or header.
        project_id: Project identifier to look up the configured token.

    Returns:
        bool: True if token matches, False otherwise.
    """
    if not provided_token:
        return False

    configured_token = get_splunk_webhook_token(project_id)
    if not configured_token:
        # If no token is configured, reject all requests for security
        return False

    return hmac.compare_digest(provided_token, configured_token)


def get_splunk_webhook_token(project_id: str) -> Optional[str]:
    """
    Retrieve the configured webhook token for a project.

    Args:
        project_id: Project identifier.

    Returns:
        str or None: The configured token, or None if not set.
    """
    return get_splunk_config(project_id, "webhook_token")


def set_splunk_webhook_token(project_id: str, token: str) -> None:
    """
    Set the webhook token for a project.

    Args:
        project_id: Project identifier.
        token: Webhook token to store.
    """
    set_splunk_config(project_id, "webhook_token", token)


def get_splunk_allowed_searches(project_id: str) -> Optional[List[str]]:
    """
    Retrieve the list of allowed saved search names for a project.

    Args:
        project_id: Project identifier.

    Returns:
        List[str] or None: List of allowed search names, or None if not configured (allow all).
    """
    value = get_splunk_config(project_id, "searches")
    if value is None:
        return None
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    return None


def set_splunk_allowed_searches(project_id: str, searches: List[str]) -> None:
    """
    Set the list of allowed saved search names for a project.

    Args:
        project_id: Project identifier.
        searches: List of saved search names to allow.
    """
    set_splunk_config(project_id, "searches", searches)


def is_search_allowed(search_name: str, project_id: str) -> bool:
    """
    Check if a saved search is allowed for ingestion.

    Args:
        search_name: Name of the Splunk saved search.
        project_id: Project identifier.

    Returns:
        bool: True if the search is allowed, False otherwise.
              If no filter is configured, returns True (allow all).
    """
    allowed_searches = get_splunk_allowed_searches(project_id)
    if allowed_searches is None:
        # No filter configured, allow all
        return True
    return search_name in allowed_searches
