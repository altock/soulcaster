"""FastAPI application for Soulcaster data ingestion.

This module provides HTTP endpoints for ingesting feedback from multiple sources:
- Reddit posts (normalized via reddit_poller)
- Sentry webhook events
- Manual text submissions
"""

import asyncio
import json
import logging
import os
import sys
import re
from dotenv import load_dotenv
from pathlib import Path

# Load .env.local from project root (one level up from backend/)
env_path = Path(__file__).parent.parent / ".env.local"
load_dotenv(env_path)

from datetime import datetime, timezone
import time
from typing import Dict, List, Optional, Literal, Tuple, Union
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, HTTPException, Path, Query, Request, BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
_BACKGROUND_TASKS: set[asyncio.Task] = set()

from models import FeedbackItem, IssueCluster, AgentJob, User, Project, ClusterJob, CodingPlan
from store import (
    add_cluster,
    add_feedback_item,
    add_feedback_items_batch,
    get_all_clusters,
    get_all_feedback_items,
    get_cluster,
    get_feedback_item,
    get_feedback_by_external_id,
    get_feedback_by_external_ids_batch,
    update_feedback_item,
    remove_from_unclustered,
    remove_from_unclustered_batch,
    clear_clusters,
    delete_cluster,
    set_reddit_subreddits_for_project,
    get_reddit_subreddits_for_project,
    get_datadog_webhook_secret_for_project,
    get_datadog_monitors_for_project,
    set_datadog_webhook_secret_for_project,
    set_datadog_monitors_for_project,
    update_cluster,
    add_job,
    get_job,
    update_job,
    get_jobs_by_cluster,
    get_all_jobs,
    get_job_logs,
    create_user_with_default_project,
    create_project,
    get_projects_for_user,
    get_project,
    get_cluster_job,
    list_cluster_jobs,
    get_unclustered_feedback,
    add_coding_plan,
    get_coding_plan,
    get_sentry_config as get_sentry_config_value,
    set_sentry_config as set_sentry_config_value,
    get_splunk_config as get_splunk_config_value,
    set_splunk_config as set_splunk_config_value,
    get_datadog_config as get_datadog_config_value,
    set_datadog_config as set_datadog_config_value,
    get_posthog_config as get_posthog_config_value,
    set_posthog_config as set_posthog_config_value,
    ping,
    count_feedback_items_for_user,
    count_successful_jobs_for_user,
    get_user_id_for_project,
)
from limits import check_feedback_item_limit, check_coding_job_limit, FREE_TIER_MAX_ISSUES, FREE_TIER_MAX_JOBS  # noqa: E402
from planner import generate_plan
from github_client import fetch_repo_issues, issue_to_feedback_item
from clustering_runner import maybe_start_clustering, run_clustering_job
from agent_runner import get_runner
from reddit_poller import poll_once
from splunk_client import (
    splunk_alert_to_feedback_item,
    verify_token,
    is_search_allowed,
    get_splunk_webhook_token,
    get_splunk_allowed_searches,
    set_splunk_webhook_token,
    set_splunk_allowed_searches,
)
from posthog_client import (
    posthog_event_to_feedback_item,
    fetch_posthog_events,
    get_posthog_event_types,
    set_posthog_event_types,
)
from sentry_client import (
    verify_sentry_signature,
    extract_sentry_stacktrace,
    extract_issue_short_id,
    extract_event_id,
    extract_sentry_metadata,
    should_ingest_event,
)
from datadog_client import datadog_event_to_feedback_item, verify_signature
# Ensure runners are registered
import agent_runner.sandbox

app = FastAPI(
    title="Soulcaster Ingestion API",
    description="API for ingesting user feedback from multiple sources",
    version="0.1.0",
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Log all unhandled exceptions with full details."""
    logger.exception(f"Unhandled exception for {request.method} {request.url}: {exc}")
    raise

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
    ],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GitHub sync state tracking: (project_id, repo_name) -> sync metadata
# Note: project_id is stored as string to match endpoint usage
GITHUB_SYNC_STATE: Dict[Tuple[str, str], Dict[str, str]] = {}


@app.get("/")
def read_root():
    """
    Return a basic service status payload for the root HTTP endpoint.
    
    Returns:
        dict: Payload containing:
            status (str): "ok" when the service is healthy.
            service (str): The service identifier ("soulcaster-ingestion").
    """
    return {"status": "ok", "service": "soulcaster-ingestion"}


@app.get("/health")
def health_check():
    """
    Report service and storage connectivity status for health monitoring.
    
    When healthy, returns a dictionary with keys:
    - `status`: "healthy"
    - `service`: service identifier
    - `environment`: runtime environment
    - `storage`: "connected" or "disconnected"
    - `timestamp`: ISO 8601 UTC timestamp
    
    Returns:
        dict: Health payload described above.
    
    Raises:
        HTTPException: With a 503 status and an error payload when the storage check or other internal check fails.
    """
    try:
        environment = os.getenv("ENVIRONMENT", "development")
        store_healthy = ping()

        return {
            "status": "healthy",
            "service": "soulcaster-backend",
            "environment": environment,
            "storage": "connected" if store_healthy else "disconnected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "service": "soulcaster-backend",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )


def _require_project_id(project_id: Optional[UUID | str]) -> str:
    """
    Validate that a project_id is present and return it as a string.
    
    Parameters:
        project_id (Optional[UUID | str]): The project identifier to validate.
    
    Returns:
        str: The provided project_id converted to a string.
    
    Raises:
        HTTPException: With status code 400 if project_id is missing.
    """
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    return str(project_id)


def _check_feedback_quota(project_id: str, count: int = 1):
    """
    Validate that adding feedback items won't exceed user quota.

    Args:
        project_id: Project ID to check quota for.
        count: Number of items to add (default 1).

    Raises:
        HTTPException(429): If quota exceeded.
        HTTPException(404): If project not found.
    """
    try:
        user_id = get_user_id_for_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    can_add, current_count = check_feedback_item_limit(user_id, count)

    if not can_add:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "quota_exceeded",
                "message": f"Free tier limit of {FREE_TIER_MAX_ISSUES} issues reached",
                "current_count": current_count,
                "limit": FREE_TIER_MAX_ISSUES,
                "requested": count
            }
        )


_GITHUB_REPO_RE = re.compile(
    r"https?://github\.com/(?P<owner>[^/\s]+)/(?P<repo>[^/\s#?]+)",
    re.IGNORECASE,
)


def _extract_github_repo_url(text: str) -> Optional[str]:
    match = _GITHUB_REPO_RE.search(text or "")
    if not match:
        return None
    owner = match.group("owner")
    repo = match.group("repo").replace(".git", "")
    return f"https://github.com/{owner}/{repo}"


def _infer_cluster_github_repo_url(items: List[FeedbackItem]) -> Optional[str]:
    for item in items:
        if item.github_issue_url:
            derived = _extract_github_repo_url(item.github_issue_url)
            if derived:
                return derived
    for item in items:
        if item.repo and "/" in item.repo:
            owner, repo = item.repo.split("/", 1)
            return f"https://github.com/{owner}/{repo}"
    for item in items:
        for text in (item.title, item.body, item.raw_text or ""):
            derived = _extract_github_repo_url(text)
            if derived:
                return derived
    return None


def _kickoff_clustering(project_id: str):
    """
    Trigger clustering for the given project, preferring asynchronous fire-and-forget execution.
    
    If an asyncio event loop is running, schedules a non-blocking clustering job for the project.
    If no event loop is available (e.g., in test environments), runs clustering synchronously so callers can observe results. Any exceptions raised during inline execution are logged.
    
    Parameters:
        project_id (str): Identifier of the project whose unclustered feedback should be clustered.
    """
    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(maybe_start_clustering(project_id))
        _BACKGROUND_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_TASKS.discard)
    except RuntimeError:
        # No running loop (e.g., during pytest/TestClient); run clustering inline so tests see clusters.
        logger.warning("No running event loop; clustering not started for project %s", project_id)
        try:
            async def _inline():
                """
                Start and execute a clustering job for the current project_id inline.
                
                This coroutine starts a clustering job for the surrounding `project_id` and runs that job to completion within the current async context.
                """
                job = await maybe_start_clustering(project_id)
                if job.status == "pending":
                    await run_clustering_job(project_id, job.id)

            asyncio.run(_inline())
        except Exception:
            logger.exception("Inline clustering failed for project %s", project_id)


# ============================================================
# PHASE 2: REDDIT INTEGRATION (Currently deferred)
# ============================================================
@app.post("/ingest/reddit")
def ingest_reddit(item: FeedbackItem, project_id: Optional[str] = Query(None)):
    """
    Create or deduplicate a Reddit-sourced FeedbackItem and associate it with a project.
    
    If `project_id` is provided it overrides `item.project_id`; otherwise the function requires
    `item.project_id` to be present. If an existing item with the same `external_id` and source
    exists for the project, the existing item's id is returned and no new item is created.
    
    Parameters:
        project_id (UUID | None): Optional project UUID to associate the item with. If omitted,
            the item's own `project_id` is used.
    
    Returns:
        dict: `{'status': 'duplicate', 'id': <id>}` if a matching external_id already exists;
        `{'status': 'ok', 'id': <id>, 'project_id': <project_id>}` on successful creation.
    
    Raises:
        HTTPException: If no project_id is available (neither argument nor item.project_id).
    """
    pid = _require_project_id(project_id or item.project_id)
    pid_str = str(pid)
    item = item.model_copy(update={"project_id": pid})
    if item.external_id:
        existing = get_feedback_by_external_id(pid_str, item.source, item.external_id)
        if existing:
            return {"status": "duplicate", "id": str(existing.id)}

    # Only enforce quota for inserts that will actually create a new item
    _check_feedback_quota(pid_str, count=1)
    add_feedback_item(item)
    _kickoff_clustering(pid_str)
    return {"status": "ok", "id": str(item.id), "project_id": pid_str}


# ============================================================
# PHASE 2: SENTRY INTEGRATION (Enhanced)
# ============================================================
@app.post("/ingest/sentry")
async def ingest_sentry(
    request: Request,
    project_id: Optional[str] = Query(None),
    sentry_hook_signature: Optional[str] = Header(None, alias="sentry-hook-signature"),
):
    """
    Enhanced Sentry webhook ingestion with signature verification, issue deduplication, and filtering.

    Features:
    - HMAC-SHA256 signature verification (if webhook_secret configured)
    - Deduplication by issue short_id (groups events by issue)
    - Stack trace extraction and normalization
    - Environment and level filtering

    Parameters:
        request (Request): FastAPI request object (for reading body).
        project_id (UUID | None): UUID of the project to associate the FeedbackItem with.
        sentry_hook_signature (str | None): HMAC signature from Sentry webhook header.

    Returns:
        dict: {"status": "ok", "id": "<item-uuid>", "project_id": "<project-uuid>"}
              or {"status": "filtered"} if event was filtered out.

    Raises:
        HTTPException: 401 if signature verification fails, 500 if processing fails.
    """
    try:
        pid = _require_project_id(project_id)
        enabled = get_sentry_config_value(pid, "enabled")
        if enabled is False:
            return {"status": "filtered", "project_id": str(pid)}

        # Read raw body and parse JSON
        body = await request.body()
        payload = json.loads(body.decode('utf-8'))

        # Verify signature if configured
        webhook_secret = get_sentry_config_value(pid, "webhook_secret")
        if webhook_secret:
            if not sentry_hook_signature:
                raise HTTPException(
                    status_code=401,
                    detail="Missing sentry-hook-signature header"
                )

            if not verify_sentry_signature(body, sentry_hook_signature, webhook_secret):
                raise HTTPException(
                    status_code=401,
                    detail="Invalid webhook signature"
                )

        # Check environment and level filters
        allowed_environments = get_sentry_config_value(pid, "environments")
        allowed_levels = get_sentry_config_value(pid, "levels")

        if not should_ingest_event(payload, allowed_environments, allowed_levels):
            # Event filtered out - return success but don't create item
            return {"status": "filtered", "project_id": str(pid)}

        # Extract issue short_id for deduplication (prefer over event_id)
        issue_short_id = extract_issue_short_id(payload)
        event_id = extract_event_id(payload)
        external_id = issue_short_id or event_id

        # Check for existing item with same external_id
        if external_id:
            existing = get_feedback_by_external_id(pid, "sentry", external_id)
            if existing:
                return {"status": "duplicate", "id": str(existing.id), "project_id": str(pid)}

        # Extract data from payload
        title = payload.get("message") or payload.get("data", {}).get("event", {}).get("message") or "Sentry Issue"
        stacktrace = extract_sentry_stacktrace(payload)
        metadata = extract_sentry_metadata(payload)

        # Construct body with exception details and stack trace
        exception_values = payload.get("exception", {}).get("values", [])
        if not exception_values:
            exception_values = (
                payload.get("data", {})
                .get("event", {})
                .get("exception", {})
                .get("values", [])
            )

        body = ""
        if exception_values:
            exc = exception_values[0]
            exc_type = exc.get("type", "Error")
            exc_value = exc.get("value", "")
            body += f"{exc_type}: {exc_value}\n"

        if stacktrace:
            body += f"\nStacktrace:\n{stacktrace}"

        # Check quota before creating item
        _check_feedback_quota(str(pid), count=1)

        # Create FeedbackItem
        item = FeedbackItem(
            id=uuid4(),
            project_id=pid,
            source="sentry",
            external_id=external_id,
            title=title,
            body=body,
            metadata=metadata,
            created_at=datetime.now(timezone.utc),
        )
        add_feedback_item(item)
        _kickoff_clustering(str(pid))
        return {"status": "ok", "id": str(item.id), "project_id": str(pid)}

    except HTTPException:
        # Re-raise HTTP exceptions (signature failures, etc.)
        raise
    except Exception as e:
        logger.exception(f"Failed to process Sentry payload: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to process Sentry payload: {str(e)}"
        ) from e


# ============================================================
# SPLUNK INTEGRATION
# ============================================================
@app.post("/ingest/splunk/webhook")
def ingest_splunk_webhook(
    payload: dict,
    project_id: Optional[str] = Query(None),
    token: Optional[str] = Query(None),
    x_splunk_token: Optional[str] = Header(None, alias="X-Splunk-Token"),
):
    """
    Receive Splunk alert webhooks and convert them to FeedbackItems.

    Splunk alerts are sent via webhook when saved searches trigger. This endpoint
    authenticates the request using a project-specific token, optionally filters
    by allowed search names, and creates a FeedbackItem for clustering.

    Parameters:
        payload (dict): Splunk alert webhook payload containing result, sid, search_name, etc.
        project_id (str): Project UUID to associate the feedback with (required).
        token (str, optional): Authentication token via query parameter.
        x_splunk_token (str, optional): Authentication token via X-Splunk-Token header.

    Returns:
        dict: {"status": "ok"|"duplicate"|"filtered", "id": "<uuid>", "project_id": "<uuid>"}
              Returns "filtered" status when search is not in allowed list.

    Raises:
        HTTPException: 401 if token is missing/invalid, 400 if project_id missing.
    """
    pid = _require_project_id(project_id)
    enabled = get_splunk_config_value(pid, "enabled")
    if enabled is False:
        return {"status": "filtered", "project_id": pid}

    # Token authentication: check query param first, then header
    provided_token = token or x_splunk_token
    if not verify_token(provided_token, pid):
        raise HTTPException(status_code=401, detail="Invalid or missing authentication token")

    # Optional: Filter by allowed saved searches
    search_name = payload.get("search_name", "")
    if not is_search_allowed(search_name, pid):
        # Return success but don't create item (silent filter)
        return {"status": "filtered", "project_id": pid}

    # Convert to FeedbackItem
    try:
        item = splunk_alert_to_feedback_item(payload, pid)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to process Splunk payload: {str(e)}"
        ) from e

    # Deduplication by external_id (sid)
    if item.external_id:
        existing = get_feedback_by_external_id(pid, item.source, item.external_id)
        if existing:
            return {"status": "duplicate", "id": str(existing.id), "project_id": pid}

    # Check quota before storing
    _check_feedback_quota(pid, count=1)

    # Store and trigger clustering
    add_feedback_item(item)
    _kickoff_clustering(pid)

    return {"status": "ok", "id": str(item.id), "project_id": pid}


# ============================================================
# DATADOG INTEGRATION
# ============================================================
@app.post("/ingest/datadog/webhook")
async def ingest_datadog_webhook(
    request: Request,
    payload: dict,
    project_id: Optional[str] = Query(None),
    x_datadog_signature: Optional[str] = Header(None, alias="X-Datadog-Signature"),
):
    """
    Ingest Datadog webhook alerts and convert them to FeedbackItems.

    Supports:
    - Signature verification (if webhook secret is configured)
    - Monitor filtering (if specific monitors are configured)
    - Hourly deduplication (same alert within an hour is deduplicated)

    Parameters:
        request: FastAPI request object (for signature verification).
        payload: Datadog webhook payload.
        project_id: Project identifier; required.
        x_datadog_signature: Optional signature header for webhook verification.

    Returns:
        dict: Status response with "ok", "duplicate", or "filtered".

    Raises:
        HTTPException: If signature is invalid (401) or processing fails (500).
    """
    pid = _require_project_id(project_id)
    enabled = get_datadog_config_value(pid, "enabled")
    if enabled is False:
        return {"status": "filtered", "project_id": pid}

    # 1. Verify signature if secret is configured
    webhook_secret = get_datadog_webhook_secret_for_project(pid)
    if webhook_secret:
        if not x_datadog_signature:
            raise HTTPException(status_code=401, detail="Missing X-Datadog-Signature header")

        # Get raw body for signature verification
        body_bytes = await request.body()
        if not verify_signature(body_bytes, x_datadog_signature, webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # 2. Check monitor filter
    configured_monitors = get_datadog_monitors_for_project(pid)
    if configured_monitors is not None:
        # None means no filter (accept all)
        # Empty list or specific IDs means filter is active
        monitor_id = str(payload.get("id", ""))

        # Check if wildcard or specific match
        if "*" not in configured_monitors and monitor_id not in configured_monitors:
            return {
                "status": "filtered",
                "message": "Monitor not configured for ingestion",
                "project_id": pid,
            }

    # 3. Convert to FeedbackItem
    try:
        item = datadog_event_to_feedback_item(payload, pid)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to convert Datadog event: {str(e)}"
        ) from e

    # 4. Check for duplicate (deduplication by external_id)
    if item.external_id:
        existing = get_feedback_by_external_id(pid, item.source, item.external_id)
        if existing:
            return {"status": "duplicate", "id": str(existing.id), "project_id": pid}

    # Check quota before adding item
    _check_feedback_quota(pid, count=1)

    # 5. Add item and trigger clustering
    add_feedback_item(item)
    _kickoff_clustering(pid)

    return {"status": "ok", "id": str(item.id), "project_id": pid}


# ============================================================
# POSTHOG INTEGRATION
# ============================================================
@app.post("/ingest/posthog/webhook")
def ingest_posthog_webhook(payload: dict, project_id: Optional[str] = Query(None)):
    """
    Normalize a PostHog webhook payload into a FeedbackItem, persist it under the given project, and trigger automatic clustering.

    PostHog webhook payloads have a nested structure with hook metadata and event data.
    The actual event is in payload["data"].

    Parameters:
        payload (dict): Raw JSON payload received from PostHog's webhook.
        project_id (str | None): UUID of the project to associate the created FeedbackItem; required and validated by the function.

    Returns:
        dict: A response containing keys "status" (always "ok" on success), "id" (created feedback item UUID as a string), and "project_id" (associated project UUID as a string).

    Raises:
        HTTPException: If project_id is missing (400) or if processing fails (500).
    """
    # Validate project_id first (this will raise HTTPException with 400 if missing)
    pid = _require_project_id(project_id)
    enabled = get_posthog_config_value(pid, "enabled")
    if enabled is False:
        return {"status": "filtered", "project_id": str(pid)}

    try:
        # Extract the event data from the webhook payload
        # PostHog webhook structure: {"hook": {...}, "data": {event data}}
        event_data = payload.get("data", {})

        # Convert PostHog event to FeedbackItem
        item = posthog_event_to_feedback_item(event_data, pid)

        # Check for deduplication
        if item.external_id:
            existing = get_feedback_by_external_id(pid, item.source, item.external_id)
            if existing:
                return {"status": "duplicate", "id": str(existing.id), "project_id": pid}

        # Check quota before storing
        _check_feedback_quota(pid, count=1)

        # Store the feedback item
        add_feedback_item(item)

        # Trigger clustering
        _kickoff_clustering(pid)

        return {"status": "ok", "id": str(item.id), "project_id": pid}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to process PostHog payload: {str(e)}"
        ) from e


@app.post("/ingest/posthog/sync")
def ingest_posthog_sync(project_id: Optional[str] = Query(None)):
    """
    Pull events from PostHog API and ingest them as FeedbackItems.

    This endpoint fetches events from PostHog since the last sync timestamp
    and creates FeedbackItems for each event. Configuration (API key, project ID,
    event types) is read from Redis.

    Parameters:
        project_id (str | None): UUID of the project to associate events with; required.

    Returns:
        dict: Summary of sync operation with keys:
            - status (str): "ok" on success
            - events_synced (int): Number of events fetched and stored
            - project_id (str): The project UUID as a string

    Raises:
        HTTPException: If project_id is missing (400) or sync fails (500).
    """
    # Validate project_id first (this will raise HTTPException with 400 if missing)
    pid = _require_project_id(project_id)
    enabled = get_posthog_config_value(pid, "enabled")
    if enabled is False:
        return {"status": "filtered", "project_id": str(pid)}

    try:
        # TODO: Read configuration from Redis
        # For now, return success with 0 events synced
        # Future implementation will:
        # 1. Read config:posthog:{project_id}:api_key
        # 2. Read config:posthog:{project_id}:project_id
        # 3. Read config:posthog:{project_id}:event_types
        # 4. Read config:posthog:{project_id}:last_synced
        # 5. Call fetch_posthog_events()
        # 6. Create FeedbackItems for each event
        # 7. Update last_synced timestamp

        return {"status": "ok", "events_synced": 0, "project_id": pid}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to sync PostHog events: {str(e)}"
        ) from e


class ManualIngestRequest(BaseModel):
    """Request model for manual feedback submission."""

    text: str


class SubredditConfig(BaseModel):
    """Payload for configuring Reddit subreddits."""

    subreddits: List[str]


class CreateUserRequest(BaseModel):
    email: Optional[str] = None
    github_id: Optional[str] = None


class CreateProjectRequest(BaseModel):
    name: str
    user_id: Union[str, UUID]  # Supports both UUID and CUID formats
    project_id: Optional[Union[str, UUID]] = None  # Optional: use this ID if provided


@app.post("/users")
def create_user(payload: CreateUserRequest):
    """
    Create a new user and a default project owned by that user.
    
    Creates a User record and a Project named "My Project", persists them together, and returns both objects.
    
    Parameters:
        payload (CreateUserRequest): Request data containing optional `email` and `github_id` for the new user.
    
    Returns:
        dict: A dictionary with keys `user` (the created User) and `default_project` (the created Project).
    """
    now = datetime.now(timezone.utc)
    user = User(id=uuid4(), email=payload.email, github_id=payload.github_id, created_at=now)
    default_project = Project(
        id=uuid4(),
        user_id=user.id,
        name="My Project",
        created_at=now,
    )
    create_user_with_default_project(user, default_project)
    return {"user": user, "default_project": default_project}


@app.get("/projects")
def list_projects(user_id: Union[str, UUID] = Query(...)):
    """List projects for a user. Accepts both UUID and CUID formats."""
    return {"projects": get_projects_for_user(user_id)}


@app.post("/projects")
def create_project_endpoint(payload: CreateProjectRequest):
    """
    Create a new Project for the specified user.

    Parameters:
        payload (CreateProjectRequest): Request containing `name` for the new project and the `user_id` of its owner.

    Returns:
        dict: A mapping with key `"project"` whose value is the created Project instance.
    """
    now = datetime.now(timezone.utc)
    # Use provided project_id if available, otherwise use user_id as project_id
    pid = payload.project_id if payload.project_id else payload.user_id

    # Check if project already exists to prevent silent overwrites
    existing = get_project(pid)
    if existing:
        # If project exists with same user_id, return it (idempotent)
        if str(existing.user_id) == str(payload.user_id):
            return {"project": existing}
        # If project exists with different user_id, raise conflict error
        raise HTTPException(
            status_code=409,
            detail=f"Project {pid} already exists for a different user"
        )

    project = Project(id=pid, user_id=payload.user_id, name=payload.name, created_at=now)
    create_project(project)
    return {"project": project}


@app.post("/ingest/manual")
def ingest_manual(request: ManualIngestRequest, project_id: Optional[str] = Query(None)):
    """
    Create and persist a FeedbackItem from manual text, then trigger automatic clustering.
    
    The submitted text becomes the item's body; the item's title is the first 80 characters of the text.
    
    Parameters:
        request (ManualIngestRequest): Object containing the manual feedback text in `text`.
        project_id (UUID | None): Optional project UUID to associate the item with; a project_id is required and will be validated.
    
    Returns:
        dict: {"status": "ok", "id": "<created-item-uuid>", "project_id": "<project-uuid>"} containing the created item's ID and the project it was assigned to.
    """
    pid = _require_project_id(project_id)
    _check_feedback_quota(str(pid), count=1)
    item = FeedbackItem(
        id=uuid4(),
        project_id=pid,
        source="manual",
        title=request.text[:80],  # Truncate title to 80 chars
        body=request.text,
        metadata={},
        created_at=datetime.now(timezone.utc),
    )
    add_feedback_item(item)
    _kickoff_clustering(str(pid))
    return {"status": "ok", "id": str(item.id), "project_id": str(pid)}


@app.post("/ingest/github/sync/{repo_name:path}")
async def ingest_github_sync(
    request: Request,
    repo_name: str = Path(..., description="GitHub repo in the form owner/repo"),
    project_id: Optional[str] = Query(None),
    x_github_token: Optional[str] = Header(None, alias="X-GitHub-Token"),
):
    """
    Synchronize GitHub issues for a repository into project-scoped FeedbackItems.

    Only ingests open issues. For initial sync, fetches only open issues to avoid
    historical closed issues. For incremental sync, fetches all updated issues
    to detect newly closed ones and archives them (marks status as "closed" and
    removes from unclustered set). Pull requests are ignored. The in-memory sync
    state for the (project, repo) pair is updated with `last_synced` and `issue_count`.

    Parameters:
        request: FastAPI request object (headers inspected for debugging).
        repo_name: GitHub repository in the form "owner/repo".
        project_id: Project identifier; required.
        x_github_token: Optional OAuth token supplied via the X-GitHub-Token header.

    Returns:
        dict: Summary of the sync with keys:
            - success (bool): True when sync completed.
            - repo (str): repository full name ("owner/repo").
            - new_issues (int): number of newly created feedback items.
            - updated_issues (int): number of updated feedback items.
            - archived_issues (int): number of previously open issues that were archived because they're now closed.
            - total_issues (int): total issues fetched from GitHub.
            - last_synced (str): ISO 8601 UTC timestamp when the sync finished.
            - project_id (str): the project_id used for the sync.
            - synced_ids (List[str]): UUIDs of feedback items created or updated.

    Raises:
        HTTPException: if project_id is missing, repo_name is invalid, or fetching issues from GitHub fails (returns 502).
    """
    logger.info("=== GitHub Sync Request ===")
    logger.info(f"repo_name: {repo_name}")
    logger.info(f"project_id: {project_id}")
    logger.info(f"x_github_token present: {bool(x_github_token)}")
    if x_github_token:
        logger.info(f"x_github_token length: {len(x_github_token)}")
    logger.debug(f"All headers: {dict(request.headers)}")
    
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    logger.info(f"Validated project_id: {project_id}")

    if "/" not in repo_name:
        logger.error(f"Invalid repo_name format: {repo_name}")
        raise HTTPException(status_code=400, detail="repo_name must be in the form owner/repo")

    owner, repo = repo_name.split("/", 1)
    repo_full_name = f"{owner}/{repo}"
    state_key = (project_id, repo_full_name)
    since = GITHUB_SYNC_STATE.get(state_key, {}).get("last_synced")
    logger.info(f"Syncing {repo_full_name}, since={since}")

    overall_start = time.monotonic()

    # For initial sync (no since), only fetch open issues to avoid ingesting historical closed issues.
    # For incremental sync (since is set), fetch all updated issues to detect newly closed ones.
    issue_state = "all" if since else "open"

    try:
        fetch_start = time.monotonic()
        logger.info(f"Fetching issues from GitHub API for {owner}/{repo} (state={issue_state})...")
        fetch_kwargs = {
            "since": since,
            "max_pages": int(os.getenv("GITHUB_SYNC_MAX_PAGES", "20")),
            "max_issues": int(os.getenv("GITHUB_SYNC_MAX_ISSUES", "2000")),
            "state": issue_state,
        }
        if x_github_token:
            fetch_kwargs["token"] = x_github_token
        issues = fetch_repo_issues(owner, repo, **fetch_kwargs)
        logger.info(
            "Fetched %d issues from GitHub (%.2fs)",
            len(issues),
            time.monotonic() - fetch_start,
        )
    except Exception as exc:
        logger.exception(f"GitHub sync failed for {repo_full_name}")
        raise HTTPException(status_code=502, detail=f"GitHub sync failed: {exc}") from exc
    if not issues:
        return {
            "success": True,
            "repo": repo_full_name,
            "new_issues": 0,
            "updated_issues": 0,
            "archived_issues": 0,
            "total_issues": 0,
            "last_synced": datetime.now(timezone.utc).isoformat(),
            "project_id": project_id,
            "synced_ids": [],
        }

    new_count = 0
    updated_count = 0
    archived_count = 0
    synced_ids: List[str] = []

    external_ids = [str(issue.get("id")) for issue in issues if issue.get("id") is not None]
    existing_feedback_map = get_feedback_by_external_ids_batch(project_id, "github", external_ids)

    new_items: List[FeedbackItem] = []  # Truly new items (will be added to unclustered set)
    items_to_update: List[FeedbackItem] = []  # Existing items to update (won't touch unclustered)
    to_archive: List[Tuple[UUID, str]] = []  # (feedback_id, project_id) pairs to archive

    for issue in issues:
        external_id = str(issue.get("id"))
        existing = existing_feedback_map.get(external_id)
        is_closed = issue.get("state") == "closed"

        if is_closed:
            # For closed issues: archive if they exist in our store, skip if they don't
            if existing:
                to_archive.append((existing.id, project_id))
                archived_count += 1
            # Don't add closed issues that aren't already in our store
            continue

        # Open issue: add or update
        if existing:
            # Refresh fields while preserving the stored UUID
            feedback_item = issue_to_feedback_item(issue, repo_full_name, project_id).model_copy(
                update={"id": existing.id}
            )
            items_to_update.append(feedback_item)
            updated_count += 1
        else:
            feedback_item = issue_to_feedback_item(issue, repo_full_name, project_id)
            new_items.append(feedback_item)
            new_count += 1

        synced_ids.append(str(feedback_item.id))

    # Batch write new items (adds to unclustered set for clustering)
    if new_items:
        # Check quota with batch size and handle partial batch if needed
        try:
            _check_feedback_quota(project_id, count=len(new_items))
            write_start = time.monotonic()
            add_feedback_items_batch(new_items)
            logger.info(
                "Wrote %d new feedback items (%.2fs)",
                len(new_items),
                time.monotonic() - write_start,
            )
        except HTTPException as e:
            if e.status_code == 429:
                # Partial batch: add what we can
                try:
                    user_id = get_user_id_for_project(project_id)
                    _, current_count = check_feedback_item_limit(user_id, 0)
                    allowed = max(0, FREE_TIER_MAX_ISSUES - current_count)

                    if allowed > 0:
                        logger.warning(f"Quota limit: adding {allowed}/{len(new_items)} items")
                        write_start = time.monotonic()
                        add_feedback_items_batch(new_items[:allowed])
                        logger.info(
                            "Wrote %d new feedback items (partial, quota limited) (%.2fs)",
                            allowed,
                            time.monotonic() - write_start,
                        )
                        # Update counts to reflect partial write
                        new_count = allowed
                        synced_ids = synced_ids[:allowed]
                    else:
                        raise
                except ValueError:
                    raise HTTPException(status_code=404, detail="Project not found")
            else:
                raise

    # Update existing items without re-adding to unclustered set (prevents duplicate clusters)
    if items_to_update:
        update_start = time.monotonic()
        for item in items_to_update:
            update_feedback_item(
                project_id,
                item.id,
                title=item.title,
                body=item.body,
                metadata=item.metadata,
            )
        logger.info(
            "Updated %d existing feedback items (%.2fs)",
            len(items_to_update),
            time.monotonic() - update_start,
        )

    # Archive closed items: update status to "closed" and remove from unclustered
    if to_archive:
        archive_start = time.monotonic()
        for feedback_id, pid in to_archive:
            update_feedback_item(pid, feedback_id, status="closed")
        remove_from_unclustered_batch(to_archive)
        logger.info(
            "Archived %d closed issues (%.2fs)",
            len(to_archive),
            time.monotonic() - archive_start,
        )

    # Only trigger clustering if there are truly new items (not updates)
    if new_items:
        _kickoff_clustering(project_id)

    now_iso = datetime.now(timezone.utc).isoformat()
    GITHUB_SYNC_STATE[state_key] = {
        "last_synced": now_iso,
        "issue_count": str(len(new_items) + len(items_to_update)),
    }

    logger.info(
        "Sync complete: %d new, %d updated, %d archived in %.2fs",
        new_count,
        updated_count,
        archived_count,
        time.monotonic() - overall_start,
    )

    return {
        "success": True,
        "repo": repo_full_name,
        "new_issues": new_count,
        "updated_issues": updated_count,
        "archived_issues": archived_count,
        "total_issues": len(issues),
        "last_synced": now_iso,
        "project_id": project_id,
        "synced_ids": synced_ids,
    }


# Reddit config endpoints (per project)


def _sanitize_subreddits(values: List[str]) -> List[str]:
    """
    Normalize a list of subreddit strings by trimming whitespace, converting to lowercase, removing empty entries, and deduplicating while preserving the original order.
    
    Empty or all-whitespace input strings are dropped.
    
    Returns:
        List[str]: Cleaned subreddit slugs in their original order with duplicates removed.
    """
    cleaned = []
    for value in values:
        slug = value.strip()
        if not slug:
            continue
        cleaned.append(slug.lower())
    # Preserve order, remove duplicates
    seen = set()
    deduped = []
    for sub in cleaned:
        if sub not in seen:
            seen.add(sub)
            deduped.append(sub)
    return deduped


@app.get("/config/reddit/subreddits")
def get_reddit_config(project_id: Optional[str] = Query(None)):
    """
    Get the active subreddit list for a project.
    
    Checks the project's stored subreddit configuration; if none exists, falls back to the REDDIT_SUBREDDITS or REDDIT_SUBREDDIT environment variable, and if still unset returns ["claudeai"].
    
    Parameters:
        project_id (UUID): Project UUID used to scope the subreddit configuration lookup.
    
    Returns:
        dict: A dictionary with keys `subreddits` (List[str]) and `project_id` (str) representing the resolved subreddit list and the project id.
    """
    pid = _require_project_id(project_id)
    configured = get_reddit_subreddits_for_project(pid)
    if configured:
        return {"subreddits": configured, "project_id": str(pid)}

    # Fallback to env defaults
    env_value = os.getenv("REDDIT_SUBREDDITS") or os.getenv("REDDIT_SUBREDDIT")
    if env_value:
        return {"subreddits": _sanitize_subreddits(env_value.split(",")), "project_id": str(pid)}
    return {"subreddits": ["claudeai"], "project_id": str(pid)}


@app.post("/config/reddit/subreddits")
def set_reddit_config(payload: SubredditConfig, project_id: Optional[str] = Query(None)):
    """
    Set the subreddits configured for polling for a specific project.

    Validates and normalizes the provided subreddit names, requires a project_id, persists the cleaned list for that project, and returns the stored subreddits and project id.

    Parameters:
        payload (SubredditConfig): Object containing `subreddits`, the list of subreddit strings to set.
        project_id (UUID | None): Project identifier used to scope the configuration.

    Returns:
        dict: {"subreddits": List[str], "project_id": str} — the cleaned subreddit list and the project id as a string.

    Raises:
        HTTPException: If the cleaned subreddit list is empty (400) or if `project_id` is missing/invalid (400).
    """
    cleaned = _sanitize_subreddits(payload.subreddits)
    if not cleaned:
        raise HTTPException(status_code=400, detail="At least one subreddit is required.")
    pid = _require_project_id(project_id)
    set_reddit_subreddits_for_project(cleaned, pid)
    return {"subreddits": cleaned, "project_id": str(pid)}


# ============================================================
# SPLUNK CONFIG ENDPOINTS
# ============================================================

class SplunkTokenConfig(BaseModel):
    """Payload for configuring Splunk webhook token."""
    token: str


class SplunkSearchesConfig(BaseModel):
    """Payload for configuring Splunk allowed searches."""
    searches: List[str]


class SplunkConfigUpdate(BaseModel):
    """Payload for updating Splunk configuration in one request."""
    webhook_token: Optional[str] = None
    allowed_searches: Optional[List[str]] = None


@app.get("/config/splunk")
def get_splunk_config(project_id: Optional[str] = Query(None)):
    """
    Get the Splunk configuration for a project.

    Returns the webhook token, allowed searches list, and enabled state.

    Parameters:
        project_id (str): Project identifier.

    Returns:
        dict: {
            "webhook_token": str or None,
            "allowed_searches": List[str] or None,
            "enabled": bool (default True),
            "project_id": str
        }
    """
    pid = _require_project_id(project_id)
    token = get_splunk_webhook_token(pid)
    searches = get_splunk_allowed_searches(pid)
    enabled = get_splunk_config_value(pid, "enabled")
    if enabled is None:
        enabled = True  # Default to enabled

    return {
        "webhook_token": token,
        "allowed_searches": searches,
        "enabled": enabled,
        "project_id": str(pid)
    }


@app.post("/config/splunk")
def update_splunk_config(payload: SplunkConfigUpdate, project_id: Optional[str] = Query(None)):
    """
    Update the Splunk configuration for a project in a single request.

    Parameters:
        payload (SplunkConfigUpdate): Object containing the webhook token and/or allowed searches.
        project_id (str): Project identifier.

    Returns:
        dict: {"status": "ok"}
    """
    pid = _require_project_id(project_id)
    if payload.webhook_token is not None:
        set_splunk_webhook_token(pid, payload.webhook_token)
    if payload.allowed_searches is not None:
        set_splunk_allowed_searches(pid, payload.allowed_searches)

    return {"status": "ok"}


@app.post("/config/splunk/token")
def set_splunk_token(payload: SplunkTokenConfig, project_id: Optional[str] = Query(None)):
    """
    Set the Splunk webhook token for a project.

    Parameters:
        payload (SplunkTokenConfig): Object containing the webhook token.
        project_id (str): Project identifier.

    Returns:
        dict: {"status": "ok"}
    """
    pid = _require_project_id(project_id)
    set_splunk_webhook_token(pid, payload.token)

    return {"status": "ok"}


@app.post("/config/splunk/searches")
def set_splunk_searches(payload: SplunkSearchesConfig, project_id: Optional[str] = Query(None)):
    """
    Set the allowed Splunk searches for a project.

    Parameters:
        payload (SplunkSearchesConfig): Object containing the list of allowed search names.
        project_id (str): Project identifier.

    Returns:
        dict: {"status": "ok"}
    """
    pid = _require_project_id(project_id)
    set_splunk_allowed_searches(pid, payload.searches)

    return {"status": "ok"}


# ============================================================
# DATADOG CONFIG ENDPOINTS
# ============================================================

class DatadogSecretConfig(BaseModel):
    """Payload for configuring Datadog webhook secret."""
    secret: str


class DatadogMonitorsConfig(BaseModel):
    """Payload for configuring Datadog allowed monitors."""
    monitors: List[str]


@app.get("/config/datadog")
def get_datadog_config(project_id: Optional[str] = Query(None)):
    """
    Get the Datadog configuration for a project.

    Returns the webhook secret, allowed monitors list, and enabled state.

    Parameters:
        project_id (str): Project identifier.

    Returns:
        dict: {
            "webhook_secret": str or None,
            "allowed_monitors": List[str] or None,
            "enabled": bool (default True),
            "project_id": str
        }
    """
    pid = _require_project_id(project_id)
    secret = get_datadog_webhook_secret_for_project(pid)
    monitors = get_datadog_monitors_for_project(pid)
    enabled = get_datadog_config_value(pid, "enabled")
    if enabled is None:
        enabled = True  # Default to enabled

    return {
        "webhook_secret": secret,
        "allowed_monitors": monitors,
        "enabled": enabled,
        "project_id": str(pid)
    }


@app.post("/config/datadog/secret")
def set_datadog_secret(payload: DatadogSecretConfig, project_id: Optional[str] = Query(None)):
    """
    Set the Datadog webhook secret for a project.

    Parameters:
        payload (DatadogSecretConfig): Object containing the webhook secret.
        project_id (str): Project identifier.

    Returns:
        dict: {"status": "ok"}
    """
    pid = _require_project_id(project_id)
    set_datadog_webhook_secret_for_project(payload.secret, pid)

    return {"status": "ok"}


@app.post("/config/datadog/monitors")
def set_datadog_monitors(payload: DatadogMonitorsConfig, project_id: Optional[str] = Query(None)):
    """
    Set the allowed Datadog monitors for a project.

    Parameters:
        payload (DatadogMonitorsConfig): Object containing the list of monitor IDs or ["*"].
        project_id (str): Project identifier.

    Returns:
        dict: {"status": "ok"}
    """
    pid = _require_project_id(project_id)
    set_datadog_monitors_for_project(payload.monitors, pid)

    return {"status": "ok"}


# ============================================================
# POSTHOG CONFIG ENDPOINTS
# ============================================================

class PostHogEventTypesConfig(BaseModel):
    """Payload for configuring PostHog event types."""
    event_types: List[str]


@app.get("/config/posthog")
def get_posthog_config(project_id: Optional[str] = Query(None)):
    """
    Get the PostHog configuration for a project.

    Returns the event types to track and enabled state.

    Parameters:
        project_id (str): Project identifier.

    Returns:
        dict: {
            "event_types": List[str] or None,
            "enabled": bool (default True),
            "project_id": str
        }
    """
    pid = _require_project_id(project_id)
    event_types = get_posthog_event_types(pid)
    enabled = get_posthog_config_value(pid, "enabled")
    if enabled is None:
        enabled = True  # Default to enabled

    return {
        "event_types": event_types,
        "enabled": enabled,
        "project_id": str(pid)
    }


@app.post("/config/posthog/events")
def set_posthog_events(payload: PostHogEventTypesConfig, project_id: Optional[str] = Query(None)):
    """
    Set the PostHog event types to track for a project.

    Parameters:
        payload (PostHogEventTypesConfig): Object containing the list of event types.
        project_id (str): Project identifier.

    Returns:
        dict: {"status": "ok"}
    """
    pid = _require_project_id(project_id)
    set_posthog_event_types(pid, payload.event_types)

    return {"status": "ok"}


# ============================================================
# SENTRY CONFIG ENDPOINTS
# ============================================================

class SentrySecretConfig(BaseModel):
    """Payload for configuring Sentry webhook secret."""
    secret: str


class SentryEnvironmentsConfig(BaseModel):
    """Payload for configuring Sentry allowed environments."""
    environments: List[str]


class SentryLevelsConfig(BaseModel):
    """Payload for configuring Sentry allowed levels."""
    levels: List[str]


class SentryConfigUpdate(BaseModel):
    """Payload for updating Sentry configuration in one request."""
    webhook_secret: Optional[str] = None
    environments: Optional[List[str]] = None
    levels: Optional[List[str]] = None


class IntegrationEnabledConfig(BaseModel):
    """Payload for configuring integration enabled state."""
    enabled: bool


@app.get("/config/sentry")
def get_sentry_config_endpoint(project_id: Optional[str] = Query(None)):
    """
    Get the Sentry configuration for a project.

    Returns the webhook secret, allowed environments, allowed levels, and enabled state.

    Parameters:
        project_id (str): Project identifier.

    Returns:
        dict: {
            "webhook_secret": str or None,
            "allowed_environments": List[str] or None,
            "allowed_levels": List[str] or None,
            "enabled": bool (default True),
            "project_id": str
        }
    """
    pid = _require_project_id(project_id)
    secret = get_sentry_config_value(pid, "webhook_secret")
    environments = get_sentry_config_value(pid, "environments")
    levels = get_sentry_config_value(pid, "levels")
    enabled = get_sentry_config_value(pid, "enabled")
    if enabled is None:
        enabled = True  # Default to enabled

    return {
        "webhook_secret": secret,
        "allowed_environments": environments,
        "allowed_levels": levels,
        "enabled": enabled,
        "project_id": str(pid)
    }


@app.post("/config/sentry")
def update_sentry_config(payload: SentryConfigUpdate, project_id: Optional[str] = Query(None)):
    """
    Update the Sentry configuration for a project in a single request.

    Parameters:
        payload (SentryConfigUpdate): Object containing webhook secret, environments, and/or levels.
        project_id (str): Project identifier.

    Returns:
        dict: {"status": "ok"}
    """
    pid = _require_project_id(project_id)
    if payload.webhook_secret is not None:
        set_sentry_config_value(pid, "webhook_secret", payload.webhook_secret)
    if payload.environments is not None:
        set_sentry_config_value(pid, "environments", payload.environments)
    if payload.levels is not None:
        set_sentry_config_value(pid, "levels", payload.levels)

    return {"status": "ok"}


@app.post("/config/sentry/secret")
def set_sentry_secret(payload: SentrySecretConfig, project_id: Optional[str] = Query(None)):
    """
    Set the Sentry webhook secret for a project.

    Parameters:
        payload (SentrySecretConfig): Object containing the webhook secret.
        project_id (str): Project identifier.

    Returns:
        dict: {"status": "ok"}
    """
    pid = _require_project_id(project_id)
    set_sentry_config_value(pid, "webhook_secret", payload.secret)

    return {"status": "ok"}


@app.post("/config/sentry/environments")
def set_sentry_environments(payload: SentryEnvironmentsConfig, project_id: Optional[str] = Query(None)):
    """
    Set the allowed Sentry environments for a project.

    Parameters:
        payload (SentryEnvironmentsConfig): Object containing the list of environment names.
        project_id (str): Project identifier.

    Returns:
        dict: {"status": "ok"}
    """
    pid = _require_project_id(project_id)
    set_sentry_config_value(pid, "environments", payload.environments)

    return {"status": "ok"}


@app.post("/config/sentry/levels")
def set_sentry_levels(payload: SentryLevelsConfig, project_id: Optional[str] = Query(None)):
    """
    Set the allowed Sentry levels for a project.

    Parameters:
        payload (SentryLevelsConfig): Object containing the list of level names.
        project_id (str): Project identifier.

    Returns:
        dict: {"status": "ok"}
    """
    pid = _require_project_id(project_id)
    set_sentry_config_value(pid, "levels", payload.levels)

    return {"status": "ok"}


# ============================================================
# GENERIC INTEGRATION ENABLED STATE ENDPOINT
# ============================================================

@app.post("/config/{integration}/enabled")
def set_integration_enabled(
    integration: str,
    payload: IntegrationEnabledConfig,
    project_id: Optional[str] = Query(None)
):
    """
    Set the enabled state for any integration.

    Supports: splunk, datadog, posthog, sentry

    Parameters:
        integration (str): Integration name (splunk, datadog, posthog, sentry).
        payload (IntegrationEnabledConfig): Object containing the enabled boolean.
        project_id (str): Project identifier.

    Returns:
        dict: {"status": "ok"}

    Raises:
        HTTPException: 400 if integration is not supported.
    """
    pid = _require_project_id(project_id)

    # Validate integration name
    valid_integrations = ["splunk", "datadog", "posthog", "sentry"]
    if integration not in valid_integrations:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid integration: {integration}. Must be one of {valid_integrations}"
        )

    # Route to appropriate config function
    if integration == "splunk":
        set_splunk_config_value(pid, "enabled", payload.enabled)
    elif integration == "datadog":
        set_datadog_config_value(pid, "enabled", payload.enabled)
    elif integration == "posthog":
        set_posthog_config_value(pid, "enabled", payload.enabled)
    elif integration == "sentry":
        set_sentry_config_value(pid, "enabled", payload.enabled)

    return {"status": "ok"}


@app.post("/admin/trigger-poll")
async def trigger_poll(project_id: Optional[str] = Query(None)):
    """
    Run a single Reddit polling cycle for the given project and ingest any discovered posts into the store, then trigger clustering for ingested items.
    
    Parameters:
        project_id (Optional[str]): Project identifier used to scope the poll; required by the endpoint and validated.
    
    Returns:
        dict: Status payload. On success: `{"status": "ok", "message": "Polled N subreddits", "project_id": "<uuid>"}`. If no subreddits are configured: `{"status": "skipped", "message": "No subreddits configured", "project_id": "<uuid>"}`.
    
    Raises:
        HTTPException: With status 500 if polling or ingestion fails.
    """
    pid = _require_project_id(project_id)
    subreddits = get_reddit_subreddits_for_project(pid) or []
    if not subreddits:
        return {"status": "skipped", "message": "No subreddits configured", "project_id": str(pid)}
    
    # Helper to ingest directly without HTTP request (avoids deadlock)
    def direct_ingest(payload: dict):
        """
        Create and store a FeedbackItem from a raw payload and trigger clustering for its project.

        Injects the current `project_id` into the payload, constructs and persists a FeedbackItem, and starts the non-blocking clustering process for that project.

        Parameters:
            payload (dict): Mapping of fields accepted by FeedbackItem; `project_id` will be set before item creation.
        """
        try:
            # Inject project_id so the ingested feedback stays scoped correctly
            payload["project_id"] = pid
            item = FeedbackItem(**payload)

            # Check quota before adding item
            _check_feedback_quota(str(pid), count=1)

            add_feedback_item(item)
            _kickoff_clustering(str(pid))
        except Exception as e:
            print(f"Error in direct ingest: {e}")
            raise e

    try:
        # Run in threadpool to avoid blocking the event loop
        # Pass direct_ingest as ingest_fn
        await run_in_threadpool(poll_once, subreddits, ingest_fn=direct_ingest)
        return {"status": "ok", "message": f"Polled {len(subreddits)} subreddits", "project_id": str(pid)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# Simple clustering: group by source (and subreddit for Reddit)
def _auto_cluster_feedback(item: FeedbackItem) -> IssueCluster:
    """
    Determines an IssueCluster for a FeedbackItem based on its source (and subreddit when present) and ensures the item is associated with that cluster, creating a new cluster if none exists for the same project and title.
    
    Parameters:
        item (FeedbackItem): The feedback item to assign to a cluster.
    
    Returns:
        IssueCluster: The existing or newly created cluster that contains the item.
    """
    now = datetime.now(timezone.utc)
    subreddit = None
    if isinstance(item.metadata, dict):
        subreddit = item.metadata.get("subreddit")

    if item.source == "reddit":
        cluster_title = f"Reddit: r/{subreddit}" if subreddit else "Reddit feedback"
        cluster_summary = (
            f"Reports from r/{subreddit}" if subreddit else "Feedback from Reddit submissions"
        )
    elif item.source == "github":
        repo_name = None
        if isinstance(item.metadata, dict):
            repo_name = item.metadata.get("repo")
        repo_name = repo_name or getattr(item, "repo", None) or "GitHub repository"
        cluster_title = f"GitHub: {repo_name}"
        cluster_summary = f"Issues from GitHub repository {repo_name}"
    elif item.source == "sentry":
        cluster_title = "Sentry issues"
        cluster_summary = "Error reports ingested from Sentry webhooks"
    else:
        cluster_title = "Manual feedback"
        cluster_summary = "User-submitted manual feedback"

    # Try to find an existing cluster with the same title
    project_id = str(item.project_id)
    existing = None
    for cluster in get_all_clusters(project_id):
        if cluster.title == cluster_title:
            existing = cluster
            break

    if existing:
        if str(item.id) not in existing.feedback_ids:
            updated_ids = [*existing.feedback_ids, str(item.id)]
            return update_cluster(
                project_id,
                existing.id,
                feedback_ids=updated_ids,
                updated_at=now,
            )
        return existing

    # Create new cluster
    cluster = IssueCluster(
        id=str(uuid4()),
        project_id=item.project_id,
        title=cluster_title,
        summary=cluster_summary,
        feedback_ids=[str(item.id)],
        status="new",
        created_at=now,
        updated_at=now,
    )
    add_cluster(cluster)
    return cluster


# Feedback Retrieval Endpoints


@app.get("/feedback")
def get_feedback(
    source: Optional[str] = Query(
        None, description="Filter by source (reddit, sentry, manual)"
    ),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of items to return"
    ),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    project_id: Optional[str] = Query(None),
):
    """
    Retrieve feedback items for a project with optional source filtering and pagination.
    
    Filters items to the provided project_id and, if specified, by source.
    Requires a valid project_id; a missing project_id will result in an HTTP 400.
    
    Parameters:
        source (Optional[str]): Filter by source — "reddit", "sentry", or "manual".
        limit (int): Maximum number of items to return (1 to 1000).
        offset (int): Number of items to skip for pagination (>= 0).
        project_id (Optional[UUID]): Project UUID used to scope results; required.
    
    Returns:
        dict: {
            "items": List[FeedbackItem] — the page of feedback items,
            "total": int — total number of matching items for the project,
            "limit": int — the limit used,
            "offset": int — the offset used,
            "project_id": str — the project UUID as a string
        }
    """
    pid = _require_project_id(project_id)
    all_items = get_all_feedback_items(str(pid))

    # Filter by source if specified
    if source:
        all_items = [item for item in all_items if item.source == source]

    total = len(all_items)

    # Apply pagination
    paginated_items = all_items[offset : offset + limit]

    return {
        "items": paginated_items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "project_id": str(pid),
    }


class FeedbackUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    metadata: Optional[dict] = None
    github_repo_url: Optional[str] = None
    status: Optional[str] = None
    repo: Optional[str] = None
    raw_text: Optional[str] = None


@app.put("/feedback/{item_id}")
def update_feedback_entry(
    item_id: Union[UUID, str], payload: FeedbackUpdate, project_id: Optional[str] = Query(None)
):
    """
    Update mutable fields on a FeedbackItem scoped to a project.
    """
    pid = _require_project_id(project_id)
    pid_str = str(pid)
    existing = get_feedback_item(pid_str, item_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Feedback item not found")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return {"status": "ok", "id": str(item_id), "project_id": pid_str}

    updated = update_feedback_item(pid_str, item_id, **updates)
    return {"status": "ok", "item": updated}


@app.get("/feedback/{item_id}")
def get_feedback_by_id(item_id: Union[UUID, str], project_id: Optional[str] = Query(None)):
    """
    Retrieve a feedback item by its ID within the specified project.
    
    Parameters:
        item_id (UUID): ID of the feedback item to retrieve.
        project_id (UUID, optional): Project scope for the lookup; required and validated by the endpoint.
    
    Returns:
        FeedbackItem: The matching feedback item.
    
    Raises:
        HTTPException: 404 if the item does not exist or does not belong to the specified project.
    """
    pid = _require_project_id(project_id)
    item = get_feedback_item(str(pid), item_id)
    if item is None:
        raise HTTPException(
            status_code=404, detail=f"Feedback item {item_id} not found"
        )
    return item


@app.get("/stats")
def get_stats(project_id: Optional[str] = Query(None)):
    """
    Return statistics for a project's feedback items and clusters.
    
    Returns:
        A dictionary containing:
        - total_feedback (int): Number of feedback items for the project.
        - by_source (dict): Counts of feedback items grouped by source keys `"reddit"`, `"sentry"`, and `"manual"`.
        - total_clusters (int): Number of clusters associated with the project.
        - project_id (str): The project's UUID as a string.
    """
    pid = _require_project_id(project_id)
    pid_str = str(pid)
    all_items = get_all_feedback_items(pid_str)
    total = len(all_items)

    # Count by source
    by_source = {"reddit": 0, "sentry": 0, "manual": 0}
    for item in all_items:
        if item.source in by_source:
            by_source[item.source] += 1

    total_clusters = len(get_all_clusters(pid_str))

    return {
        "total_feedback": total,
        "by_source": by_source,
        "total_clusters": total_clusters,
        "project_id": str(pid),
    }


@app.get("/clusters")
def list_clusters(project_id: Optional[str] = Query(None)):
    """
    List issue clusters for a project, including aggregated metadata.
    
    Parameters:
        project_id (UUID): Project identifier used to scope clusters. Required.
    
    Returns:
        list[dict]: A list of cluster summaries. Each dict contains:
            - id: cluster id (str)
            - title: cluster title (str)
            - summary: cluster summary (str)
            - count: number of feedback items referenced by the cluster (int)
            - status: cluster status (str)
            - sources: sorted list of distinct feedback sources present in the cluster (list[str])
            - github_pr_url: URL of an associated GitHub PR, if any (str or None)
            - issue_title: suggested issue title, if any (str or None)
            - issue_description: suggested issue description, if any (str or None)
            - github_repo_url: associated GitHub repository URL, if any (str or None)
            - project_id: the project id as a string (str)
    """

    pid = _require_project_id(project_id)
    pid_str = str(pid)
    clusters = get_all_clusters(pid_str)  # Already sorted by created_at desc from ZSET
    results = []
    for cluster in clusters:
        # Use cached sources from cluster (populated at creation time)
        # Fallback to empty list for clusters created before this optimization
        sources = cluster.sources if cluster.sources else []
        results.append(
            {
                "id": cluster.id,
                "title": cluster.title,
                "summary": cluster.summary,
                "count": len(cluster.feedback_ids),
                "status": cluster.status,
                "sources": sources,
                "github_pr_url": cluster.github_pr_url,
                "issue_title": cluster.issue_title,
                "issue_description": cluster.issue_description,
                "github_repo_url": cluster.github_repo_url,
                "project_id": pid_str,
            }
        )
    return results


@app.get("/clusters/{cluster_id}")
def get_cluster_detail(cluster_id: str, project_id: Optional[str] = Query(None)):
    """
    Retrieve a cluster scoped to the requested project and include its resolved feedback items.
    
    Validates that the specified cluster exists and belongs to the provided project_id, resolves any feedback items referenced by the cluster (skipping invalid IDs), and returns the cluster representation augmented with a `feedback_items` list and `project_id`.
    
    Parameters:
        cluster_id (str): The cluster's identifier.
        project_id (UUID | None): Project scope to validate the cluster against; required.
    
    Returns:
        dict: Cluster data as a mapping with additional keys:
            - `feedback_items` (list): Resolved feedback item objects associated with the cluster.
            - `project_id` (str): The project UUID as a string.
    
    Raises:
        HTTPException: 404 if the cluster does not exist or does not belong to the specified project.
    """

    pid = _require_project_id(project_id)
    pid_str = str(pid)
    cluster = get_cluster(pid_str, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    feedback_items = []
    for fid in cluster.feedback_ids:
        try:
            # feedback_ids are stored as strings, but get_feedback_item expects UUID
            item = get_feedback_item(pid_str, UUID(fid))
            if item:
                feedback_items.append(item)
        except (ValueError, AttributeError):
            # Skip invalid UUIDs
            continue
    
    response = cluster.model_dump()
    response["feedback_items"] = feedback_items
    response["project_id"] = str(pid)
    return response


@app.post("/cluster-jobs")
async def create_cluster_job(project_id: Optional[str] = Query(None)):
    """
    Create and start a clustering job for the specified project without waiting for completion.
    
    Returns:
        dict: A summary containing:
            - job_id (str): Identifier of the created clustering job.
            - status (str): Initial status of the job.
            - project_id (str): Normalized project identifier used to start the job.
    """
    pid = _require_project_id(project_id)
    job = await maybe_start_clustering(pid)
    return {"job_id": job.id, "status": job.status, "project_id": pid}


@app.get("/cluster-jobs/{job_id}")
def get_cluster_job_status(job_id: str, project_id: Optional[str] = Query(None)):
    """
    Retrieve a cluster job by ID scoped to the specified project.
    
    Raises:
    	HTTPException: 404 if no cluster job with the given ID exists for the project.
    
    Returns:
    	ClusterJob: The cluster job record.
    """
    pid = _require_project_id(project_id)
    job = get_cluster_job(pid, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Cluster job not found")
    return job


@app.get("/cluster-jobs")
def list_cluster_job_status(project_id: Optional[str] = Query(None), limit: int = Query(20, ge=1, le=50)):  # noqa: E501
    """
    Retrieve recent clustering jobs for the given project.
    
    Parameters:
        project_id: Project identifier to scope the returned jobs.
        limit: Maximum number of jobs to return (1-50).
    
    Returns:
        dict: {"jobs": list of ClusterJob objects, "project_id": project id string}
    """
    pid = _require_project_id(project_id)
    jobs = list_cluster_jobs(pid, limit=limit)
    return {"jobs": jobs, "project_id": pid}


@app.get("/clustering/status")
def clustering_status(project_id: Optional[str] = Query(None)):
    """
    Report clustering queue status for the specified project.
    
    Parameters:
        project_id (Optional[str]): Project identifier; if omitted or invalid, a 400 HTTPException is raised and the request is rejected.
    
    Returns:
        dict: A mapping with the following keys:
            - "pending_unclustered" (int): Number of feedback items awaiting clustering.
            - "is_clustering" (bool): `true` if a clustering job is currently running, `false` otherwise.
            - "last_job" (ClusterJob|None): The most recent cluster job record, or `None` if none exist.
            - "project_id" (str): Normalized project id used for the query.
    
    Raises:
        HTTPException: If `project_id` is missing or invalid.
    """
    pid = _require_project_id(project_id)
    pending = len(get_unclustered_feedback(pid))
    recent = list_cluster_jobs(pid, limit=10)
    last_job = recent[0] if recent else None
    is_clustering = any(job.status == "running" for job in recent)
    return {"pending_unclustered": pending, "is_clustering": is_clustering, "last_job": last_job, "project_id": pid}


@app.post("/clusters/cleanup")
def cleanup_duplicate_clusters(project_id: Optional[str] = Query(None)):
    """
    Merge clusters whose centroids are similar and remove duplicate clusters within a project.
    
    Groups clusters transitively using centroid similarity (threshold from vector_store.CLEANUP_MERGE_THRESHOLD, currently 0.65), selects a kept cluster per group (preferring clusters with status "fixing" or the largest feedback count), merges feedback IDs and recomputes the centroid for the kept cluster, then deletes the other clusters in each group.
    
    Parameters:
        project_id (Optional[str]): Project identifier taken from the request query; required to scope the cleanup.
    
    Returns:
        dict: Summary of the cleanup operation with the following keys:
            - success (bool): `True` on successful completion.
            - message (str): Human-readable status message.
            - total_clusters (int): Number of clusters examined.
            - duplicate_groups (int): Number of groups containing more than one cluster.
            - merged_groups (int): Number of groups that were merged (kept one cluster and removed others).
            - deleted_clusters (int): Number of clusters deleted.
            - remaining_clusters (int): Number of clusters remaining after deletions.
    """
    from vector_store import find_similar_clusters, CLEANUP_MERGE_THRESHOLD
    import json
    import numpy as np

    pid = _require_project_id(project_id)
    clusters = get_all_clusters(pid)

    if not clusters:
        return {
            "success": True,
            "message": "No clusters to clean up",
            "total_clusters": 0,
            "duplicate_groups": 0,
            "merged_groups": 0,
            "deleted_clusters": 0,
            "remaining_clusters": 0,
        }

    # Build centroid map
    cluster_centroids = {}
    cluster_info = {}
    for cluster in clusters:
        cluster_info[cluster.id] = {
            "id": cluster.id,
            "title": cluster.title,
            "status": cluster.status,
            "feedback_ids": cluster.feedback_ids or [],
            "centroid": cluster.centroid or [],
        }
        if cluster.centroid:
            cluster_centroids[cluster.id] = cluster.centroid

    # Find similar clusters
    merge_candidates = find_similar_clusters(cluster_centroids, CLEANUP_MERGE_THRESHOLD)

    if not merge_candidates:
        return {
            "success": True,
            "message": "No duplicate clusters found",
            "total_clusters": len(clusters),
            "duplicate_groups": 0,
            "merged_groups": 0,
            "deleted_clusters": 0,
            "remaining_clusters": len(clusters),
        }

    # Use Union-Find to group transitively
    n = len(clusters)
    cluster_ids = [c.id for c in clusters]
    id_to_idx = {cid: i for i, cid in enumerate(cluster_ids)}
    parent = list(range(n))

    def find(x):
        """
        Finds the representative (root) of element x in the disjoint-set forest and compresses the path.
        
        Parameters:
            x (int): Element identifier whose set representative is requested.
        
        Returns:
            int: The representative (root) of the set containing x. The parent links for x (and intermediate nodes) are updated to point directly to this root.
        """
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x, y):
        """
        Merge the disjoint-set containing x with the disjoint-set containing y.
        
        Modifies the union-find parent mapping so that the roots of x and y become part of the same set.
        
        Parameters:
            x: An element (identifier) in the disjoint-set structure.
            y: Another element (identifier) in the disjoint-set structure.
        """
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Union similar clusters
    for candidate in merge_candidates:
        idx1 = id_to_idx.get(candidate["cluster1"])
        idx2 = id_to_idx.get(candidate["cluster2"])
        if idx1 is not None and idx2 is not None:
            union(idx1, idx2)

    # Group by parent
    groups = {}
    for i in range(n):
        root = find(i)
        if root not in groups:
            groups[root] = []
        groups[root].append(cluster_ids[i])

    # Filter to only groups with duplicates
    duplicate_groups = [g for g in groups.values() if len(g) > 1]

    merged_count = 0
    deleted_count = 0

    for group in duplicate_groups:
        group_clusters = [cluster_info[cid] for cid in group]

        # Keep cluster with most feedback items, or prefer "fixing" status
        group_clusters.sort(key=lambda c: (
            0 if c["status"] == "fixing" else 1,
            -len(c["feedback_ids"]),
        ))

        keep = group_clusters[0]
        duplicates = group_clusters[1:]

        # Collect all feedback IDs
        all_feedback_ids = set(keep["feedback_ids"])
        all_centroids = [keep["centroid"]] if keep["centroid"] else []

        for dup in duplicates:
            for fid in dup["feedback_ids"]:
                all_feedback_ids.add(fid)
            if dup["centroid"]:
                all_centroids.append(dup["centroid"])

        # Update kept cluster with merged feedback IDs
        new_feedback_ids = list(all_feedback_ids)

        # Calculate new centroid as average
        new_centroid = None
        if len(all_centroids) > 1:
            new_centroid = np.mean(all_centroids, axis=0).tolist()
        elif len(all_centroids) == 1:
            new_centroid = all_centroids[0]

        # Update the kept cluster
        update_cluster(
            pid,
            keep["id"],
            feedback_ids=new_feedback_ids,
            centroid=new_centroid,
        )

        # Delete duplicate clusters
        for dup in duplicates:
            delete_cluster(pid, dup["id"])
            deleted_count += 1

        merged_count += 1

    return {
        "success": True,
        "message": "Duplicate clusters cleaned up successfully",
        "total_clusters": len(clusters),
        "duplicate_groups": len(duplicate_groups),
        "merged_groups": merged_count,
        "deleted_clusters": deleted_count,
        "remaining_clusters": len(clusters) - deleted_count,
    }


@app.get("/clusters/analyze")
def analyze_cluster_quality(project_id: Optional[str] = Query(None)):
    """
    Analyze cluster quality and detect overly-broad clusters that should be split.

    Returns a health report for all clusters in the project, identifying:
    - Healthy clusters (good internal cohesion)
    - Loose clusters (low internal cohesion, may contain mixed content)
    - Split recommendations for clusters that have natural sub-groups

    Parameters:
        project_id (Optional[str]): Project identifier.

    Returns:
        dict: Cluster health report with split recommendations.
    """
    from cluster_analysis import (
        analyze_project_clusters,
        LOOSE_CLUSTER_THRESHOLD,
    )
    from vector_store import get_vector_store

    pid = _require_project_id(project_id)
    clusters = get_all_clusters(pid)

    if not clusters:
        return {
            "success": True,
            "project_id": pid,
            "total_clusters": 0,
            "healthy_clusters": 0,
            "loose_clusters": 0,
            "split_recommendations": [],
        }

    # Convert to dict format expected by analyze_project_clusters
    cluster_dicts = [
        {"id": c.id, "feedback_ids": c.feedback_ids or []}
        for c in clusters
    ]

    try:
        vector_store = get_vector_store()
        report = analyze_project_clusters(
            project_id=pid,
            clusters=cluster_dicts,
            vector_store=vector_store,
            loose_threshold=LOOSE_CLUSTER_THRESHOLD,
        )

        return {
            "success": True,
            "project_id": pid,
            "total_clusters": report.total_clusters,
            "healthy_clusters": report.healthy_clusters,
            "loose_clusters": report.loose_clusters,
            "split_recommendations": [
                {
                    "cluster_id": rec.cluster_id,
                    "reason": rec.reason,
                    "current_avg_similarity": rec.current_cohesion.avg_similarity,
                    "current_quality": rec.current_cohesion.quality,
                    "suggested_subcluster_count": len(rec.suggested_subclusters),
                    "subcluster_cohesions": rec.subcluster_cohesions,
                }
                for rec in report.split_recommendations
            ],
        }
    except Exception as e:
        logger.exception("Cluster analysis failed")
        return {
            "success": False,
            "error": str(e),
            "project_id": pid,
        }


@app.get("/clusters/{cluster_id}/plan")
def get_cluster_plan(cluster_id: str, project_id: Optional[str] = Query(None)):
    """
    Retrieve the latest coding plan for a cluster.
    
    Parameters:
    	cluster_id (str): ID of the cluster to fetch the plan for.
    	project_id (Optional[str]): Project scope to validate access; if not provided, a project id is required via query and validated.
    
    Returns:
    	CodingPlan: The most recently stored coding plan for the specified cluster.
    
    Raises:
    	HTTPException: 404 if the cluster does not exist or if no coding plan has been generated for the cluster.
    """
    pid = _require_project_id(project_id)

    # 1. Check if cluster exists (and matches project_id if provided)
    cluster = get_cluster(pid, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    # 2. Get existing plan
    plan = get_coding_plan(cluster_id)
    if not plan:
        # Optionally, we could auto-generate here if missing.
        # For now, return 404 so UI can show "Generate" button.
        raise HTTPException(status_code=404, detail="No plan found for this cluster")

    return plan


@app.post("/clusters/{cluster_id}/plan")
def generate_cluster_plan(cluster_id: str, project_id: Optional[str] = Query(None)):
    """
    Generate or regenerate a coding plan for a cluster using the LLM.
    """
    pid = _require_project_id(project_id)

    # 1. Validate cluster
    cluster = get_cluster(pid, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    # 2. Fetch feedback items for context
    items = []
    for fid in cluster.feedback_ids:
        # Ideally we have a batch get, but loop is fine for prototype
        # We need to find the item. Ideally store.get_feedback_item logic handles lookup.
        # But get_feedback_item requires project_id. IssueCluster has project_id.
        item = get_feedback_item(str(cluster.project_id), UUID(fid))
        if item:
            items.append(item)

    # 3. Call planner
    plan = generate_plan(cluster, items)

    # 4. Save plan
    add_coding_plan(plan)

    return plan


@app.post("/clusters/{cluster_id}/start_fix")
async def start_cluster_fix(
    cluster_id: str,
    project_id: Optional[str] = Query(None),
    background_tasks: BackgroundTasks = None, # type: ignore (FastAPI injection)
    x_github_token: Optional[str] = Header(None, alias="X-GitHub-Token")
):
    """
    Trigger the coding agent to fix the issues in the cluster.
    Accepts optional X-GitHub-Token header for per-user GitHub authentication.
    Falls back to GITHUB_TOKEN environment variable if header is not provided.
    """
    pid = _require_project_id(project_id)
    pid_str = str(pid)
    cluster = get_cluster(pid_str, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    # If the cluster doesn't have a repo URL yet, infer it from linked GitHub issue URLs in its feedback.
    items_for_context: List[FeedbackItem] = []
    for fid in cluster.feedback_ids:
        try:
            item = get_feedback_item(pid_str, UUID(fid))
        except Exception:
            item = None
        if item:
            items_for_context.append(item)

    if not cluster.github_repo_url:
        inferred_repo_url = _infer_cluster_github_repo_url(items_for_context)
        # Fallback is for prototyping so "Start Fix" doesn't hard-fail when
        # the cluster has no GitHub context yet.
        fallback_repo_url = (
            os.getenv("DEFAULT_GITHUB_REPO_URL") or "https://github.com/naga-k/bad-ux-mart"
        ).strip()
        repo_url = inferred_repo_url or fallback_repo_url
        cluster = update_cluster(
            pid_str,
            cluster_id,
            github_repo_url=repo_url,
            updated_at=datetime.now(timezone.utc),
        )
    else:
        # If we previously set a fallback repo URL but feedback now contains a real GitHub repo,
        # prefer the inferred value so subsequent fix runs target the right repository.
        inferred_repo_url = _infer_cluster_github_repo_url(items_for_context)
        if inferred_repo_url and inferred_repo_url != cluster.github_repo_url:
            cluster = update_cluster(
                pid_str,
                cluster_id,
                github_repo_url=inferred_repo_url,
                updated_at=datetime.now(timezone.utc),
            )

    # 1. Get or generate plan
    plan = get_coding_plan(cluster_id)
    if not plan:
        # Auto-generate if missing
        plan = generate_plan(cluster, items_for_context)
        add_coding_plan(plan)

    # 2. Determine runner
    runner_name = os.getenv("CODING_AGENT_RUNNER", "sandbox_kilo")
    try:
        runner = get_runner(runner_name)
    except ValueError:
        # Fallback to sandbox_kilo if env var is weird, or just error out
        # Here we error out to be safe
        raise HTTPException(status_code=500, detail=f"Runner '{runner_name}' not configured")

    # 2.5. Check quota before creating job
    try:
        user_id = get_user_id_for_project(pid_str)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    can_create, current_count = check_coding_job_limit(user_id)
    if not can_create:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "quota_exceeded",
                "message": f"Free tier limit of {FREE_TIER_MAX_JOBS} successful coding jobs reached",
                "current_count": current_count,
                "limit": FREE_TIER_MAX_JOBS
            }
        )

    # 3. Create Job
    job = AgentJob(
        id=uuid4(),
        project_id=pid,
        cluster_id=cluster_id,
        plan_id=plan.id,
        runner=runner_name,
        status="pending",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    add_job(job)

    # 4. Dispatch
    update_cluster(
        pid_str,
        cluster_id,
        status="fixing",
        error_message=None,
        updated_at=datetime.now(timezone.utc),
    )

    async def _run_agent():
        await runner.start(job, plan, cluster, github_token=x_github_token)

    # In unit tests, avoid launching real external runners (E2B/AWS) unless explicitly enabled.
    # Starlette's TestClient executes BackgroundTasks after the response, which can flip
    # cluster status to "failed" if the runner tries to use the network.
    is_pytest = bool(os.getenv("PYTEST_CURRENT_TEST"))
    enable_runner_in_tests = os.getenv("ENABLE_AGENT_RUNNER_IN_TESTS", "").lower() in {"1", "true", "yes"}
    if (not is_pytest) or enable_runner_in_tests:
        if background_tasks:
            background_tasks.add_task(_run_agent)
        else:
            # Fallback for sync contexts
            try:
                loop = asyncio.get_running_loop()
                task = loop.create_task(_run_agent())
                _BACKGROUND_TASKS.add(task)
                task.add_done_callback(_BACKGROUND_TASKS.discard)
            except RuntimeError:
                # No loop (e.g. sync test client), run inline?
                # Running inline might deadlock if it uses async.
                # Ideally tests use AsyncClient.
                pass

    return {
        "status": "ok",
        "message": f"Fix started with runner {runner_name}",
        "job_id": str(job.id),
        "cluster_id": cluster.id,
        "project_id": pid_str,
    }


def seed_mock_data():
    """
    Create and persist a small set of mock data (user, project, three feedback items, and one cluster) for local testing.
    
    The function inserts a mock user and project, three FeedbackItem records covering reddit, sentry, and manual sources, and a single IssueCluster that references those items.
    
    Returns:
        result (dict): A dictionary containing:
            - cluster_id (str): The ID of the created cluster.
            - feedback_ids (list[UUID]): The UUIDs of the created feedback items.
    """

    now = datetime.now(timezone.utc)
    user_id = str(uuid4())
    pid = str(uuid4())
    
    # Create a user and project so feedback validation passes
    user = User(id=user_id, email="test@example.com", created_at=now)
    project = Project(id=pid, user_id=user_id, name="Mock Project", created_at=now)
    create_user_with_default_project(user, project)

    feedback_one = FeedbackItem(
        id=uuid4(),
        project_id=pid,
        source="reddit",
        external_id="t3_mock1",
        title="Export crashes on Safari",
        body="App crashes when exporting on Safari 16.",
        metadata={"subreddit": "mock_sub"},
        created_at=now,
    )
    feedback_two = FeedbackItem(
        id=uuid4(),
        project_id=pid,
        source="sentry",
        external_id="evt_mock2",
        title="TypeError in export job",
        body="TypeError: cannot read properties of undefined",
        metadata={},
        created_at=now,
    )
    feedback_three = FeedbackItem(
        id=uuid4(),
        project_id=pid,
        source="manual",
        title="Export broken",
        body="Manual report of export failing on Firefox",
        metadata={},
        created_at=now,
    )

    for item in (feedback_one, feedback_two, feedback_three):
        add_feedback_item(item)

    cluster = IssueCluster(
        id=str(uuid4()),
        project_id=pid,
        title="Export failures",
        summary="Users report export crashes across browsers.",
        feedback_ids=[str(feedback_one.id), str(feedback_two.id), str(feedback_three.id)],
        status="new",
        created_at=now,
        updated_at=now,
    )

    add_cluster(cluster)
    return {"cluster_id": cluster.id, "feedback_ids": [feedback_one.id, feedback_two.id, feedback_three.id]}


# --- Agent Jobs ---


class CreateJobRequest(BaseModel):
    cluster_id: str


class UpdateJobRequest(BaseModel):
    status: Optional[Literal["pending", "running", "success", "failed"]] = None
    logs: Optional[str] = None


@app.get("/jobs")
def list_jobs(project_id: Optional[str] = Query(None)):
    """
    List AgentJob records for the specified project.
    
    Parameters:
        project_id (UUID): Project identifier used to scope the returned jobs. If omitted or None, an HTTP 400 error is raised.
    
    Returns:
        jobs (List[AgentJob]): List of jobs that belong to the given project.
    """
    pid = _require_project_id(project_id)
    return [job for job in get_all_jobs() if str(job.project_id) == pid]


@app.post("/jobs")
def create_job(payload: CreateJobRequest, project_id: Optional[str] = Query(None)):
    """
    Create a new agent tracking job for the specified cluster within a project.
    
    Parameters:
        payload (CreateJobRequest): Request containing `cluster_id` of the cluster to attach the job to.
        project_id (UUID, optional): Project UUID to scope the job; required and validated by the endpoint.
    
    Returns:
        dict: {"status": "ok", "job_id": <str>, "project_id": <str>} with the created job's id and the project id.
    
    Raises:
        HTTPException: 404 if the cluster does not exist or does not belong to the given project.
    """
    pid = _require_project_id(project_id)
    pid_str = str(pid)
    cluster = get_cluster(pid_str, payload.cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found for project")

    # Check quota before creating job
    try:
        user_id = get_user_id_for_project(pid_str)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    can_create, current_count = check_coding_job_limit(user_id)
    if not can_create:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "quota_exceeded",
                "message": f"Free tier limit of {FREE_TIER_MAX_JOBS} successful coding jobs reached",
                "current_count": current_count,
                "limit": FREE_TIER_MAX_JOBS
            }
        )

    now = datetime.now(timezone.utc)
    job = AgentJob(
        id=uuid4(),
        project_id=pid_str,
        cluster_id=payload.cluster_id,
        status="pending",
        logs=None,
        created_at=now,
        updated_at=now,
    )
    add_job(job)
    return {"status": "ok", "job_id": str(job.id), "project_id": pid_str}


@app.patch("/jobs/{job_id}")
def update_job_status(job_id: Union[UUID, str], payload: UpdateJobRequest, project_id: Optional[str] = Query(None)):
    """
    Update the status and/or logs of an AgentJob scoped to a project.
    
    Parameters:
        job_id (UUID): Identifier of the job to update.
        payload (UpdateJobRequest): Fields to update; may include `status` and/or `logs`.
        project_id (Optional[UUID]): Project scope; required to locate the job.
    
    Returns:
        dict: On no-op, `{"status": "ok", "message": "No updates provided"}`.
              On successful update, `{"status": "ok", "project_id": "<project_id>"}`.
    
    Raises:
        HTTPException: If the job does not exist or does not belong to the specified project (404).
    """
    pid = _require_project_id(project_id)
    job = get_job(job_id)
    if not job or str(job.project_id) != pid:
        raise HTTPException(status_code=404, detail="Job not found for project")

    updates = {}
    if payload.status:
        updates["status"] = payload.status
    if payload.logs is not None:
        updates["logs"] = payload.logs
    
    if not updates:
        return {"status": "ok", "message": "No updates provided"}

    updates["updated_at"] = datetime.now(timezone.utc)
    update_job(job_id, **updates)
    return {"status": "ok", "project_id": str(pid)}


@app.get("/jobs/{job_id}")
def get_job_details(job_id: Union[UUID, str], project_id: Optional[str] = Query(None)):
    """
    Retrieve the specified AgentJob scoped to the given project.
    
    Parameters:
        job_id (UUID): ID of the job to retrieve.
        project_id (UUID, optional): Project scope to validate ownership; required and validated by the endpoint.
    
    Returns:
        AgentJob: The job matching `job_id` that belongs to `project_id`.
    
    Raises:
        HTTPException: Raised with status 404 if the job does not exist or does not belong to the project.
    """
    pid = _require_project_id(project_id)
    job = get_job(job_id)
    if not job or str(job.project_id) != pid:
        raise HTTPException(status_code=404, detail="Job not found for project")
    return job


@app.get("/jobs/{job_id}/logs")
def get_job_log_lines(
    job_id: Union[UUID, str],
    project_id: Optional[str] = Query(None),
):
    """
    Retrieve logs for a job, preferring blob storage for completed jobs and falling back to in-memory logs.
    
    Returns:
        A dictionary containing:
        - `job_id` (str): The job UUID as a string.
        - `project_id` (str): The resolved project id.
        - `source` (str): `"blob"` if logs were fetched from blob storage, `"memory"` if from the in-memory buffer.
        - `chunks` (List[str]): A list of log chunks; for blob this contains a single entry with the blob contents, for memory it contains either a single concatenated string or is empty.
    
    Raises:
        HTTPException: 404 if the job does not exist or does not belong to the specified project.
    """
    pid = _require_project_id(project_id)
    job = get_job(job_id)
    if not job or str(job.project_id) != pid:
        raise HTTPException(status_code=404, detail="Job not found for project")

    # For completed jobs with blob_url, fetch from Blob
    if job.blob_url and job.status in ("success", "failed"):
        try:
            from blob_storage import fetch_job_logs_from_blob
            logs = fetch_job_logs_from_blob(job.blob_url)
            return {
                "job_id": str(job_id),
                "project_id": str(pid),
                "source": "blob",
                "chunks": [logs],
            }
        except Exception:
            logger.exception(f"Failed to fetch logs from Blob for job {job_id}")
            # Fall through to memory as fallback

    # For running jobs or fallback, fetch from memory
    import job_logs_manager
    logs = job_logs_manager.get_logs(job_id)
    full_logs = "".join(logs) if logs else ""

    return {
        "job_id": str(job_id),
        "project_id": str(pid),
        "source": "memory",
        "chunks": [full_logs] if full_logs else [],
    }


@app.get("/clusters/{cluster_id}/jobs")
def get_cluster_jobs(cluster_id: str, project_id: Optional[str] = Query(None)):
    """
    Return the AgentJob records for the given cluster that belong to the specified project.
    
    Filters jobs by `cluster_id` and the provided `project_id` (required); if `project_id` is missing an HTTP 400 is raised.
    
    Returns:
        List[AgentJob]: Jobs belonging to the cluster and project.
    """
    pid = _require_project_id(project_id)
    cluster_jobs = get_jobs_by_cluster(cluster_id)
    return [job for job in cluster_jobs if str(job.project_id) == pid]