"""PostHog integration client for normalizing events to FeedbackItems."""

import json
from datetime import datetime, timezone
from typing import Optional, List
from uuid import uuid4

from models import FeedbackItem
from store import _STORE


def posthog_event_to_feedback_item(event: dict, project_id: str) -> FeedbackItem:
    """
    Convert a PostHog event (from webhook or API) to a FeedbackItem.

    Extracts exception details, stack traces, session IDs, and other metadata
    from PostHog event properties.

    Parameters:
        event (dict): PostHog event data (from webhook data.data or API response)
        project_id (str): Project ID to associate the feedback with

    Returns:
        FeedbackItem: Normalized feedback item ready for storage
    """
    props = event.get("properties", {})
    exception_msg = props.get("$exception_message", "")
    stack_trace = props.get("$exception_stack_trace_raw", "")

    # Construct external_id from uuid and timestamp for deduplication
    event_uuid = event.get("uuid", event.get("distinct_id", ""))
    timestamp = event.get("timestamp", "")
    external_id = f"{event_uuid}-{timestamp}"

    # Build title from exception message or event type
    title = exception_msg[:200] if exception_msg else f"PostHog: {event.get('event', 'Unknown')}"

    # Body includes exception message and stack trace
    body_parts = []
    if exception_msg:
        body_parts.append(exception_msg)
    if stack_trace:
        body_parts.append(stack_trace)
    body = "\n\n".join(body_parts) if body_parts else "No details available"

    # Parse timestamp
    try:
        created_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        created_at = datetime.now(timezone.utc)

    return FeedbackItem(
        id=uuid4(),
        project_id=project_id,
        source="posthog",
        external_id=external_id,
        title=title,
        body=body,
        raw_text=f"{exception_msg} {stack_trace}",
        metadata={
            "event_type": event.get("event"),
            "distinct_id": event.get("distinct_id"),
            "session_id": props.get("$session_id"),
            "current_url": props.get("$current_url"),
            "browser": props.get("$browser"),
            "os": props.get("$os"),
        },
        created_at=created_at,
    )


def fetch_posthog_events(
    _api_key: str,
    _posthog_project_id: str,
    _event_types: list[str],
    _since: Optional[str] = None,
) -> list[dict]:
    """
    Fetch events from PostHog API.

    This function would make HTTP requests to PostHog's API to fetch events
    since the last sync timestamp. For the initial implementation, this is
    a stub that returns an empty list.

    Parameters:
        api_key (str): PostHog personal API key
        posthog_project_id (str): PostHog project ID
        event_types (list[str]): Event types to fetch (e.g., ["$exception"])
        since (Optional[str]): ISO timestamp to fetch events since

    Returns:
        list[dict]: List of PostHog events
    """
    # TODO: Implement actual API calls to PostHog
    # For now, return empty list (will be enhanced in future iterations)
    return []


def get_posthog_event_types(project_id: str) -> Optional[List[str]]:
    """
    Retrieve the list of PostHog event types to track for a project.

    Args:
        project_id: Project identifier.

    Returns:
        List[str] or None: List of event types, or None if not configured.
    """
    key = f"config:posthog:{project_id}:event_types"
    value = _STORE.get(key)
    if value is None:
        return None
    # Store as JSON array string
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def set_posthog_event_types(project_id: str, event_types: List[str]) -> None:
    """
    Set the list of PostHog event types to track for a project.

    Args:
        project_id: Project identifier.
        event_types: List of event types to track (e.g., ["$exception", "$error"]).
    """
    key = f"config:posthog:{project_id}:event_types"
    _STORE.set(key, json.dumps(event_types))
