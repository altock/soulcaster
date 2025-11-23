"""FastAPI application for FeedbackAgent data ingestion.

This module provides HTTP endpoints for ingesting feedback from multiple sources:
- Reddit posts (normalized via reddit_poller)
- Sentry webhook events
- Manual text submissions
"""

import os
from dotenv import load_dotenv

load_dotenv()

from datetime import datetime, timezone
from typing import List, Optional, Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from .models import FeedbackItem, IssueCluster, AgentJob
    from .store import (
        add_cluster,
        add_feedback_item,
        get_all_clusters,
        get_all_feedback_items,
        get_cluster,
        get_feedback_item,
        get_feedback_by_external_id,
        clear_clusters,
        set_reddit_subreddits,
        get_reddit_subreddits,
        update_cluster,
        add_job,
        get_job,
        update_job,
        update_job,
        get_jobs_by_cluster,
        get_all_jobs,
    )
    from .reddit_poller import poll_once, get_configured_subreddits as get_reddit_config_list
except ImportError:
    from models import FeedbackItem, IssueCluster, AgentJob
    from store import (
        add_cluster,
        add_feedback_item,
        get_all_clusters,
        get_all_feedback_items,
        get_cluster,
        get_feedback_item,
        get_feedback_by_external_id,
        clear_clusters,
        set_reddit_subreddits,
        get_reddit_subreddits,
        update_cluster,
        add_job,
        get_job,
        update_job,
        update_job,
        get_jobs_by_cluster,
        get_all_jobs,
    )
    from reddit_poller import poll_once, get_configured_subreddits as get_reddit_config_list

app = FastAPI(
    title="FeedbackAgent Ingestion API",
    description="API for ingesting user feedback from multiple sources",
    version="0.1.0",
)

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


@app.get("/")
def read_root():
    """Health check endpoint."""
    return {"status": "ok", "service": "feedbackagent-ingestion"}


@app.post("/ingest/reddit")
def ingest_reddit(item: FeedbackItem):
    """
    Ingest a feedback item from Reddit.

    This endpoint receives already-normalized Reddit posts from the reddit_poller.
    It checks for duplicate posts using external_id before storing new items.
    Automatically clusters new feedback items based on source and metadata.

    Args:
        item: FeedbackItem with Reddit post data containing source='reddit',
              normalized title/body, and metadata including subreddit info

    Returns:
        Status response with either:
        - {"status": "ok", "id": "uuid"} for new items
        - {"status": "duplicate", "id": "uuid"} for existing posts

    Raises:
        HTTPException: 500 if clustering or storage fails
    """
    if item.external_id:
        existing = get_feedback_by_external_id(item.source, item.external_id)
        if existing:
            return {"status": "duplicate", "id": str(existing.id)}
    add_feedback_item(item)
    _auto_cluster_feedback(item)
    return {"status": "ok", "id": str(item.id)}


@app.post("/ingest/sentry")
def ingest_sentry(payload: dict):
    """
    Ingest an error report from Sentry webhook.

    Parses Sentry's webhook payload and normalizes it into a FeedbackItem.
    Extracts exception type, message, and stack trace frames for context.
    Automatically clusters the error report with other Sentry issues.

    Args:
        payload: Raw Sentry webhook payload containing event data,
                exception information, and stack traces

    Returns:
        Status response with created feedback item ID:
        {"status": "ok", "id": "uuid"} for successful ingestion

    Expected payload structure:
        - event_id: Unique identifier for the Sentry event
        - message: Event message (used as title fallback)
        - exception.values: List of exception objects with type, value, stacktrace

    Raises:
        HTTPException: 500 if payload parsing or storage fails
    """
    try:
        event_id = payload.get("event_id")
        title = payload.get("message") or "Sentry Issue"

        # Construct body from exception data
        body = ""
        exception = payload.get("exception", {}).get("values", [])
        if exception:
            exc = exception[0]
            exc_type = exc.get("type", "Error")
            exc_value = exc.get("value", "")
            body += f"{exc_type}: {exc_value}\n\nStacktrace:\n"
            # Include first 3 stack frames for context
            for frame in exc.get("stacktrace", {}).get("frames", [])[:3]:
                body += f"  {frame.get('filename')}:{frame.get('lineno')}\n"

        item = FeedbackItem(
            id=uuid4(),
            source="sentry",
            external_id=event_id,
            title=title,
            body=body,
            metadata=payload,
            created_at=datetime.now(timezone.utc),
        )
        add_feedback_item(item)
        _auto_cluster_feedback(item)
        return {"status": "ok", "id": str(item.id)}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to process Sentry payload: {str(e)}"
        )


class ManualIngestRequest(BaseModel):
    """Request model for manual feedback submission."""

    text: str


class SubredditConfig(BaseModel):
    """Payload for configuring Reddit subreddits."""

    subreddits: List[str]


@app.post("/ingest/manual")
def ingest_manual(request: ManualIngestRequest):
    """
    Ingest manually submitted feedback text.

    Creates a FeedbackItem from raw text input. Title is truncated to 80 characters
    for display purposes while preserving the full text in the body field.
    Automatically clusters manual feedback items.

    Args:
        request: ManualIngestRequest containing the feedback text

    Returns:
        Status response with created feedback item ID:
        {"status": "ok", "id": "uuid"} for successful submission

    Note:
        - Title is automatically truncated to 80 characters for UI display
        - Full text is preserved in the body field
        - Source is set to "manual" for identification
        - Created timestamp is set to current UTC time
    """
    item = FeedbackItem(
        id=uuid4(),
        source="manual",
        title=request.text[:80],  # Truncate title to 80 chars
        body=request.text,
        metadata={},
        created_at=datetime.now(timezone.utc),
    )
    add_feedback_item(item)
    _auto_cluster_feedback(item)
    return {"status": "ok", "id": str(item.id)}


# Reddit config endpoints (global, no per-user)


def _sanitize_subreddits(values: List[str]) -> List[str]:
    """
    Clean and standardize subreddit names from user input.
    
    This function processes raw subreddit names to ensure consistency:
    - Removes empty/whitespace-only entries
    - Converts to lowercase for case-insensitive matching
    - Removes duplicates while preserving order
    """
    cleaned = []
    for value in values:
        slug = value.strip()
        if not slug:
            continue  # Skip empty or whitespace-only entries
        cleaned.append(slug.lower())
    
    # Preserve order, remove duplicates using a seen set
    # This ensures we maintain the user's preferred ordering
    # while eliminating any accidental duplicates
    seen = set()
    deduped = []
    for sub in cleaned:
        if sub not in seen:
            seen.add(sub)
            deduped.append(sub)
    return deduped


@app.get("/config/reddit/subreddits")
def get_reddit_config():
    """
    Return the active subreddit list (store-backed or env fallback).

    Retrieves the current list of subreddits that the poller will monitor.
    Uses a fallback hierarchy: Redis store -> environment variables -> default.

    Returns:
        Dictionary with active subreddits:
        {"subreddits": ["claudeai", "machinelearning", ...]}

    Fallback chain:
        1. Redis-stored subreddit list (highest priority)
        2. REDDIT_SUBREDDITS env var (comma-separated)
        3. REDDIT_SUBREDDIT env var (single value)
        4. Default: ["claudeai"] (fallback)
    """
    configured = get_reddit_subreddits()
    if configured:
        return {"subreddits": configured}

    # Fallback to env defaults
    env_value = os.getenv("REDDIT_SUBREDDITS") or os.getenv("REDDIT_SUBREDDIT")
    if env_value:
        return {"subreddits": _sanitize_subreddits(env_value.split(","))}
    return {"subreddits": ["claudeai"]}


@app.post("/config/reddit/subreddits")
def set_reddit_config(payload: SubredditConfig):
    """
    Set the subreddit list used by the poller (global configuration).

    Updates the global subreddit list that will be monitored by the Reddit poller.
    Automatically sanitizes input by lowercasing and removing duplicates.
    Replaces any previously configured subreddit list.

    Args:
        payload: SubredditConfig containing list of subreddit names
                (without 'r/' prefix, case-insensitive)

    Returns:
        Dictionary with sanitized subreddit list:
        {"subreddits": ["claudeai", "programming", ...]}

    Validation:
        - At least one subreddit is required
        - Subreddit names are automatically lowercased
        - Duplicates are removed while preserving order
        - Empty or whitespace-only entries are filtered out

    Raises:
        HTTPException: 400 if no valid subreddits provided
    """
    cleaned = _sanitize_subreddits(payload.subreddits)
    if not cleaned:
        raise HTTPException(status_code=400, detail="At least one subreddit is required.")
    set_reddit_subreddits(cleaned)
    return {"subreddits": cleaned}


@app.post("/admin/trigger-poll")
async def trigger_poll():
    """
    Manually trigger a Reddit poll cycle (waits for completion).

    Initiates an immediate poll of all configured subreddits.
    This is typically used for testing or to force a sync outside the normal schedule.
    The operation is blocking - it waits for all polling to complete before returning.

    Returns:
        Dictionary indicating polling results:
        - {"status": "skipped", "message": "No subreddits configured"} if no subreddits set
        - {"status": "ok", "message": "Polled X subreddits"} on successful completion

    Process:
        1. Retrieves current subreddit configuration
        2. If no subreddits configured, returns early
        3. Runs poll_once() in threadpool to avoid blocking event loop
        4. For each post found, directly ingests without HTTP overhead
        5. Automatically clusters new feedback items

    Note:
        - Uses direct ingestion to avoid HTTP request overhead
        - Runs in FastAPI's threadpool for non-blocking execution
        - Pydantic handles datetime parsing from ISO strings automatically

    Raises:
        HTTPException: 500 if polling fails or encounters errors
    """
    subreddits = get_reddit_config_list()
    if not subreddits:
        return {"status": "skipped", "message": "No subreddits configured"}
    
    from fastapi.concurrency import run_in_threadpool
    
    # Helper to ingest directly without HTTP request (avoids deadlock)
    def direct_ingest(payload: dict):
        # Convert dict payload to FeedbackItem
        # Note: payload has 'created_at' as ISO string, but FeedbackItem expects datetime
        # However, pydantic might handle string parsing if type is datetime
        # Let's check models.py or just try. Pydantic usually handles ISO strings.
        # But wait, payload['created_at'] is string. FeedbackItem.created_at is datetime.
        # Pydantic V2 handles this. V1 does too usually.
        try:
            item = FeedbackItem(**payload)
            add_feedback_item(item)
            _auto_cluster_feedback(item)
        except Exception as e:
            print(f"Error in direct ingest: {e}")
            raise e

    try:
        # Run in threadpool to avoid blocking the event loop
        # Pass direct_ingest as ingest_fn
        await run_in_threadpool(poll_once, subreddits, ingest_fn=direct_ingest)
        return {"status": "ok", "message": f"Polled {len(subreddits)} subreddits"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# Simple clustering: group by source (and subreddit for Reddit)
def _auto_cluster_feedback(item: FeedbackItem) -> IssueCluster:
    """
    Automatically cluster feedback items based on source and metadata.
    
    This is the core clustering logic that groups related feedback items together.
    Currently uses a simple heuristic: group by source and subreddit (for Reddit).
    """
    now = datetime.now(timezone.utc)
    subreddit = None
    
    # Extract subreddit from metadata for Reddit posts
    # This allows us to group Reddit feedback by specific subreddits
    if isinstance(item.metadata, dict):
        subreddit = item.metadata.get("subreddit")

    # Determine cluster title and summary based on source
    if item.source == "reddit":
        # For Reddit, include subreddit in title for better organization
        cluster_title = f"Reddit: r/{subreddit}" if subreddit else "Reddit feedback"
        cluster_summary = (
            f"Reports from r/{subreddit}" if subreddit else "Feedback from Reddit submissions"
        )
    elif item.source == "sentry":
        cluster_title = "Sentry issues"
        cluster_summary = "Error reports ingested from Sentry webhooks"
    else:
        cluster_title = "Manual feedback"
        cluster_summary = "User-submitted manual feedback"

    # Try to find an existing cluster with the same title
    # This ensures we add to existing clusters rather than creating duplicates
    existing = None
    for cluster in get_all_clusters():
        if cluster.title == cluster_title:
            existing = cluster
            break

    if existing:
        # Add this feedback item to the existing cluster if not already present
        if str(item.id) not in existing.feedback_ids:
            updated_ids = existing.feedback_ids + [str(item.id)]
            return update_cluster(
                existing.id,
                feedback_ids=updated_ids,
                updated_at=now,
            )
        return existing

    # Create new cluster if no matching cluster exists
    cluster = IssueCluster(
        id=str(uuid4()),
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
):
    """
    Retrieve feedback items with optional filtering and pagination.

    Provides paginated access to all feedback items with optional source filtering.
    Returns items in reverse chronological order (newest first).

    Args:
        source: Optional source filter - one of:
               - "reddit": Only Reddit posts
               - "sentry": Only Sentry error reports  
               - "manual": Only manually submitted feedback
        limit: Maximum number of items to return (default 100, max 1000)
        offset: Number of items to skip for pagination (default 0)

    Returns:
        Dictionary containing:
        {
            "items": [list of FeedbackItem objects],
            "total": total_items_count,
            "limit": requested_limit,
            "offset": requested_offset
        }

    Note:
        - Pagination is applied after source filtering
        - Total count reflects filtered results, not all items
        - Items are returned newest first (descending created_at)
    """
    all_items = get_all_feedback_items()

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
    }


@app.get("/feedback/{item_id}")
def get_feedback_by_id(item_id: UUID):
    """
    Retrieve a single feedback item by its ID.

    Args:
        item_id: UUID of the feedback item

    Returns:
        The FeedbackItem if found

    Raises:
        HTTPException: 404 if item not found
    """
    item = get_feedback_item(item_id)
    if item is None:
        raise HTTPException(
            status_code=404, detail=f"Feedback item {item_id} not found"
        )
    return item


@app.get("/stats")
def get_stats():
    """
    Get summary statistics about feedback items and clusters.

    Returns:
        Dictionary with:
        - total_feedback: Total number of feedback items
        - by_source: Breakdown of feedback by source
        - total_clusters: Number of clusters (placeholder for future)
    """
    all_items = get_all_feedback_items()
    total = len(all_items)

    # Count by source
    by_source = {"reddit": 0, "sentry": 0, "manual": 0}
    for item in all_items:
        if item.source in by_source:
            by_source[item.source] += 1

    total_clusters = len(get_all_clusters())

    return {
        "total_feedback": total,
        "by_source": by_source,
        "total_clusters": total_clusters,
    }


@app.get("/clusters")
def list_clusters():
    """
    List all issue clusters with aggregated metadata.

    Retrieves all clusters with summary information including counts,
    sources, and associated GitHub data. Each cluster represents a 
    grouping of related feedback items.

    Returns:
        List of cluster summaries, each containing:
        {
            "id": cluster_id,
            "title": cluster_title,
            "summary": cluster_summary,
            "count": number_of_feedback_items,
            "status": cluster_status,
            "sources": list_of_unique_sources,
            "github_pr_url": pr_url_if_exists,
            "issue_title": github_issue_title,
            "issue_description": github_issue_description,
            "github_repo_url": repository_url
        }

    Note:
        - Clusters are returned in creation order (newest first)
        - Sources are deduplicated and sorted alphabetically
        - Invalid feedback IDs are skipped during aggregation
        - GitHub fields may be null if not yet linked to a PR/issue
    """

    clusters = get_all_clusters()
    results = []
    for cluster in clusters:
        feedback_items = []
        for fid in cluster.feedback_ids:
            try:
                item = get_feedback_item(UUID(fid))
                if item:
                    feedback_items.append(item)
            except (ValueError, AttributeError):
                continue
        
        sources = sorted({item.source for item in feedback_items})
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
            }
        )
    return results


@app.get("/clusters/{cluster_id}")
def get_cluster_detail(cluster_id: str):
    """
    Retrieve a cluster with its complete feedback items.

    Gets detailed information about a specific cluster including all
    associated feedback items. This provides the full context for
    understanding an issue and its related reports.

    Args:
        cluster_id: String identifier of the cluster to retrieve

    Returns:
        Complete cluster object with feedback items:
        {
            "id": cluster_id,
            "title": cluster_title,
            "summary": cluster_summary,
            "feedback_ids": [list_of_feedback_ids],
            "status": cluster_status,
            "github_pr_url": pr_url_or_null,
            "issue_title": issue_title_or_null,
            "issue_description": issue_description_or_null,
            "github_repo_url": repo_url_or_null,
            "feedback_items": [list_of_full_FeedbackItem_objects]
        }

    Raises:
        HTTPException: 404 if cluster not found

    Note:
        - Invalid feedback IDs in cluster.feedback_ids are skipped
        - feedback_items contains the actual FeedbackItem objects
        - GitHub fields may be null if not yet linked to repository
    """

    cluster = get_cluster(cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    feedback_items = []
    for fid in cluster.feedback_ids:
        try:
            # feedback_ids are stored as strings, but get_feedback_item expects UUID
            item = get_feedback_item(UUID(fid))
            if item:
                feedback_items.append(item)
        except (ValueError, AttributeError):
            # Skip invalid UUIDs
            continue
    
    response = cluster.model_dump()
    response["feedback_items"] = feedback_items
    return response


@app.post("/clusters/{cluster_id}/start_fix")
def start_cluster_fix(cluster_id: str):
    """Begin fix generation for a cluster (stub implementation)."""

    cluster = get_cluster(cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    updated_cluster = update_cluster(cluster_id, status="fixing")
    return {"status": "ok", "message": "Fix generation started", "cluster_id": updated_cluster.id}


def seed_mock_data():
    """
    Seed a handful of feedback items and clusters for local testing.
    
    This function creates sample data that mimics real feedback from different sources.
    Useful for development, testing, and demonstration purposes.
    
    Creates:
        - 3 sample feedback items (Reddit, Sentry, Manual)
        - 1 cluster containing all feedback items
        - Properly linked relationships between items and cluster
    
    Returns:
        Dictionary with created IDs for verification/testing:
        {
            "cluster_id": "uuid",
            "feedback_ids": ["uuid1", "uuid2", "uuid3"]
        }
    """
    now = datetime.now(timezone.utc)

    # Create sample Reddit feedback item
    feedback_one = FeedbackItem(
        id=uuid4(),
        source="reddit",
        external_id="t3_mock1",
        title="Export crashes on Safari",
        body="App crashes when exporting on Safari 16.",
        metadata={"subreddit": "mock_sub"},
        created_at=now,
    )
    
    # Create sample Sentry error report
    feedback_two = FeedbackItem(
        id=uuid4(),
        source="sentry",
        external_id="evt_mock2",
        title="TypeError in export job",
        body="TypeError: cannot read properties of undefined",
        metadata={},
        created_at=now,
    )
    
    # Create sample manual feedback
    feedback_three = FeedbackItem(
        id=uuid4(),
        source="manual",
        title="Export broken",
        body="Manual report of export failing on Firefox",
        metadata={},
        created_at=now,
    )

    # Add all feedback items to the database
    for item in (feedback_one, feedback_two, feedback_three):
        add_feedback_item(item)

    # Create a cluster that groups all feedback items together
    # This simulates real-world clustering of related issues
    cluster = IssueCluster(
        id=str(uuid4()),
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
def list_jobs():
    """
    List all tracking jobs for the coding agent.

    Retrieves all AgentJob records that track the progress and status
    of fix generation tasks. Jobs are typically created when starting
    fixes for issue clusters.

    Returns:
        List of AgentJob objects containing:
        - id: Unique job identifier
        - cluster_id: Associated cluster ID
        - status: Job status (pending, running, success, failed)
        - logs: Execution logs and output
        - created_at: Job creation timestamp
        - updated_at: Last status update timestamp

    Note:
        - Jobs are ordered by creation time (newest first)
        - Logs may be null for jobs that haven't started yet
    """
    return get_all_jobs()


@app.post("/jobs")
def create_job(payload: CreateJobRequest):
    """
    Create a new tracking job for the coding agent.

    Initializes a new AgentJob record to track the progress of fix generation
    for a specific cluster. Jobs start in "pending" status and are updated
    as the coding agent makes progress.

    Args:
        payload: CreateJobRequest containing:
                - cluster_id: ID of the cluster to generate a fix for

    Returns:
        Status response with created job ID:
        {"status": "ok", "job_id": "uuid"}

    Note:
        - Job is created with "pending" status by default
        - Logs field is initialized as null
        - Timestamps are set to current UTC time
        - Each cluster can have multiple jobs (for retries, etc.)
    """
    now = datetime.now(timezone.utc)
    job = AgentJob(
        id=uuid4(),
        cluster_id=payload.cluster_id,
        status="pending",
        logs=None,
        created_at=now,
        updated_at=now,
    )
    add_job(job)
    return {"status": "ok", "job_id": str(job.id)}


@app.patch("/jobs/{job_id}")
def update_job_status(job_id: UUID, payload: UpdateJobRequest):
    """
    Update job status and/or logs for tracking progress.

    Allows updating the status and/or logs of an existing job.
    Only provided fields are updated; null fields are ignored.
    Automatically updates the updated_at timestamp.

    Args:
        job_id: UUID of the job to update
        payload: UpdateJobRequest containing optional fields:
                - status: New job status (pending, running, success, failed)
                - logs: Updated execution logs/output

    Returns:
        Status response:
        - {"status": "ok"} on successful update
        - {"status": "ok", "message": "No updates provided"} if no fields given

    Status progression:
        pending → running → success/failed

    Raises:
        HTTPException: 404 if job ID not found

    Note:
        - Both status and logs can be updated in a single call
        - updated_at is automatically set to current UTC time
        - Partial updates are supported (only provided fields change)
    """
    updates = {}
    if payload.status:
        updates["status"] = payload.status
    if payload.logs is not None:
        updates["logs"] = payload.logs
    
    if not updates:
        return {"status": "ok", "message": "No updates provided"}

    updates["updated_at"] = datetime.now(timezone.utc)
    try:
        update_job(job_id, **updates)
        return {"status": "ok"}
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


@app.get("/jobs/{job_id}")
def get_job_details(job_id: UUID):
    """Retrieve details of a specific job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/clusters/{cluster_id}/jobs")
def get_cluster_jobs(cluster_id: str):
    """List all jobs associated with a cluster."""
    return get_jobs_by_cluster(cluster_id)
