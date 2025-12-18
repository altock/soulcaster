"""Sentry webhook integration helpers.

This module provides utilities for processing Sentry webhook payloads:
- Signature verification (HMAC-SHA256)
- Stack trace extraction and normalization
- Payload parsing
"""

import hashlib
import hmac
import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def verify_sentry_signature(body: bytes, signature: str, secret: str) -> bool:
    """
    Verify Sentry webhook signature using HMAC-SHA256.

    Sentry signs webhook payloads with a client secret and sends the signature
    in the 'sentry-hook-signature' header. This function verifies that signature.

    Parameters:
        body (bytes): Raw request body bytes (before JSON parsing).
        signature (str): Signature from the 'sentry-hook-signature' header.
        secret (str): Sentry client secret configured for this project.

    Returns:
        bool: True if signature is valid, False otherwise.
    """
    if not signature or not secret:
        return False

    try:
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
    except Exception as e:
        logger.warning(f"Signature verification failed: {e}")
        return False


def extract_sentry_stacktrace(payload: dict) -> str:
    """
    Extract and format stack trace from Sentry webhook payload.

    Sentry payloads contain exception data with stack frames. This function
    extracts those frames and formats them in a readable way.

    Parameters:
        payload (dict): Sentry webhook payload dictionary.

    Returns:
        str: Formatted stack trace string, or empty string if none found.
    """
    stacktrace_lines = []

    # Extract from exception.values[].stacktrace.frames
    exception_values = payload.get("exception", {}).get("values", [])
    if not exception_values:
        # Try data.event.exception path
        exception_values = (
            payload.get("data", {})
            .get("event", {})
            .get("exception", {})
            .get("values", [])
        )

    if exception_values:
        for exc in exception_values:
            frames = exc.get("stacktrace", {}).get("frames", [])
            for frame in frames:
                filename = frame.get("filename", "unknown")
                lineno = frame.get("lineno", "?")
                function = frame.get("function", "")

                if function:
                    stacktrace_lines.append(f"  {filename}:{lineno} in {function}")
                else:
                    stacktrace_lines.append(f"  {filename}:{lineno}")

    return "\n".join(stacktrace_lines)


def extract_issue_short_id(payload: dict) -> Optional[str]:
    """
    Extract the Sentry issue short_id from webhook payload.

    Sentry groups events into issues. The issue short_id is used for deduplication
    so multiple events for the same issue create only one FeedbackItem.

    Parameters:
        payload (dict): Sentry webhook payload dictionary.

    Returns:
        Optional[str]: Issue short_id if present, None otherwise.
    """
    # Try data.issue.short_id first (newer webhook format)
    short_id = payload.get("data", {}).get("issue", {}).get("short_id")
    if short_id:
        return short_id

    # Fallback to top-level issue if present
    short_id = payload.get("issue", {}).get("short_id")
    return short_id


def extract_event_id(payload: dict) -> Optional[str]:
    """
    Extract the Sentry event_id from webhook payload.

    Parameters:
        payload (dict): Sentry webhook payload dictionary.

    Returns:
        Optional[str]: Event ID if present, None otherwise.
    """
    # Try data.event.event_id first
    event_id = payload.get("data", {}).get("event", {}).get("event_id")
    if event_id:
        return event_id

    # Fallback to top-level event_id
    return payload.get("event_id")


def extract_sentry_metadata(payload: dict) -> Dict:
    """
    Extract metadata fields from Sentry payload for storage.

    Parameters:
        payload (dict): Sentry webhook payload dictionary.

    Returns:
        dict: Metadata dictionary with relevant Sentry fields.
    """
    # Extract from data.event if available
    event_data = payload.get("data", {}).get("event", {})
    issue_data = payload.get("data", {}).get("issue", {})

    metadata = {
        "issue_id": issue_data.get("id") or payload.get("issue", {}).get("id"),
        "event_id": extract_event_id(payload),
        "level": event_data.get("level") or payload.get("level"),
        "platform": event_data.get("platform") or payload.get("platform"),
        "release": event_data.get("release") or payload.get("release"),
        "environment": event_data.get("environment") or payload.get("environment"),
        "tags": event_data.get("tags") or payload.get("tags", {}),
    }

    # Clean up None values
    return {k: v for k, v in metadata.items() if v is not None}


def get_environment_from_payload(payload: dict) -> Optional[str]:
    """
    Extract environment from Sentry payload.

    Parameters:
        payload (dict): Sentry webhook payload dictionary.

    Returns:
        Optional[str]: Environment string (e.g., "production", "staging"), or None.
    """
    # Try data.event.environment first
    environment = payload.get("data", {}).get("event", {}).get("environment")
    if environment:
        return environment

    # Fallback to top-level environment
    return payload.get("environment")


def get_level_from_payload(payload: dict) -> Optional[str]:
    """
    Extract error level from Sentry payload.

    Parameters:
        payload (dict): Sentry webhook payload dictionary.

    Returns:
        Optional[str]: Level string (e.g., "error", "fatal", "warning"), or None.
    """
    # Try data.event.level first
    level = payload.get("data", {}).get("event", {}).get("level")
    if level:
        return level

    # Fallback to top-level level
    return payload.get("level")


def should_ingest_event(
    payload: dict,
    allowed_environments: Optional[List[str]] = None,
    allowed_levels: Optional[List[str]] = None,
) -> bool:
    """
    Check if a Sentry event should be ingested based on filters.

    Parameters:
        payload (dict): Sentry webhook payload dictionary.
        allowed_environments (Optional[List[str]]): If set, only ingest events from these environments.
        allowed_levels (Optional[List[str]]): If set, only ingest events with these levels.

    Returns:
        bool: True if event should be ingested, False if it should be filtered out.
    """
    # Check environment filter
    if allowed_environments:
        event_env = get_environment_from_payload(payload)
        if event_env not in allowed_environments:
            logger.debug(f"Filtering out Sentry event from environment: {event_env}")
            return False

    # Check level filter
    if allowed_levels:
        event_level = get_level_from_payload(payload)
        if event_level not in allowed_levels:
            logger.debug(f"Filtering out Sentry event with level: {event_level}")
            return False

    return True
