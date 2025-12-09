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
    from .models import FeedbackItem, IssueCluster, AgentJob, User, Project
    from .store import (
        add_cluster,
        add_feedback_item,
        get_all_clusters,
        get_all_feedback_items,
        get_cluster,
        get_feedback_item,
        get_feedback_by_external_id,
        clear_clusters,
        set_reddit_subreddits_for_project,
        get_reddit_subreddits_for_project,
        update_cluster,
        add_job,
        get_job,
        update_job,
        get_jobs_by_cluster,
        get_all_jobs,
        create_user_with_default_project,
        create_project,
        get_projects_for_user,
        get_project,
    )
    from .reddit_poller import poll_once
except ImportError:
    from models import FeedbackItem, IssueCluster, AgentJob, User, Project
    from store import (
        add_cluster,
        add_feedback_item,
        get_all_clusters,
        get_all_feedback_items,
        get_cluster,
        get_feedback_item,
        get_feedback_by_external_id,
        clear_clusters,
        set_reddit_subreddits_for_project,
        get_reddit_subreddits_for_project,
        update_cluster,
        add_job,
        get_job,
        update_job,
        get_jobs_by_cluster,
        get_all_jobs,
        create_user_with_default_project,
        create_project,
        get_projects_for_user,
        get_project,
    )
    from reddit_poller import poll_once

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


def _require_project_id(project_id: Optional[UUID]) -> UUID:
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    return project_id


@app.post("/ingest/reddit")
def ingest_reddit(item: FeedbackItem, project_id: Optional[UUID] = Query(None)):
    """
    Ingest a feedback item from Reddit.

    This endpoint receives already-normalized Reddit posts from the reddit_poller.

    Args:
        item: FeedbackItem with Reddit post data

    Returns:
        Status response indicating success
    """
    pid = _require_project_id(project_id or item.project_id)
    item = item.model_copy(update={"project_id": pid})
    if item.external_id:
        existing = get_feedback_by_external_id(pid, item.source, item.external_id)
        if existing:
            return {"status": "duplicate", "id": str(existing.id)}
    add_feedback_item(item)
    _auto_cluster_feedback(item)
    return {"status": "ok", "id": str(item.id), "project_id": str(pid)}


@app.post("/ingest/sentry")
def ingest_sentry(payload: dict, project_id: Optional[UUID] = Query(None)):
    """
    Ingest an error report from Sentry webhook.

    Parses Sentry's webhook payload and normalizes it into a FeedbackItem.
    Extracts exception type, message, and stack trace frames.

    Args:
        payload: Raw Sentry webhook payload

    Returns:
        Status response with created feedback item ID
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

        pid = _require_project_id(project_id)
        item = FeedbackItem(
            id=uuid4(),
            project_id=pid,
            source="sentry",
            external_id=event_id,
            title=title,
            body=body,
            metadata=payload,
            created_at=datetime.now(timezone.utc),
        )
        add_feedback_item(item)
        _auto_cluster_feedback(item)
        return {"status": "ok", "id": str(item.id), "project_id": str(pid)}

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


class CreateUserRequest(BaseModel):
    email: Optional[str] = None
    github_id: Optional[str] = None


class CreateProjectRequest(BaseModel):
    name: str
    user_id: UUID


@app.post("/users")
def create_user(payload: CreateUserRequest):
    """Create a user and their default project."""
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
def list_projects(user_id: UUID = Query(...)):
    """List projects for a user."""
    return {"projects": get_projects_for_user(user_id)}


@app.post("/projects")
def create_project_endpoint(payload: CreateProjectRequest):
    """Create a project for a user."""
    now = datetime.now(timezone.utc)
    project = Project(id=uuid4(), user_id=payload.user_id, name=payload.name, created_at=now)
    create_project(project)
    return {"project": project}


@app.post("/ingest/manual")
def ingest_manual(request: ManualIngestRequest, project_id: Optional[UUID] = Query(None)):
    """
    Ingest manually submitted feedback text.

    Creates a FeedbackItem from raw text input. Title is truncated to 80 characters.

    Args:
        request: ManualIngestRequest containing the feedback text

    Returns:
        Status response with created feedback item ID
    """
    pid = _require_project_id(project_id)
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
    _auto_cluster_feedback(item)
    return {"status": "ok", "id": str(item.id), "project_id": str(pid)}


# Reddit config endpoints (per project)


def _sanitize_subreddits(values: List[str]) -> List[str]:
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
def get_reddit_config(project_id: Optional[UUID] = Query(None)):
    """Return the active subreddit list (store-backed or env fallback) for a project."""
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
def set_reddit_config(payload: SubredditConfig, project_id: Optional[UUID] = Query(None)):
    """Set the subreddit list used by the poller (per project)."""
    cleaned = _sanitize_subreddits(payload.subreddits)
    if not cleaned:
        raise HTTPException(status_code=400, detail="At least one subreddit is required.")
    pid = _require_project_id(project_id)
    set_reddit_subreddits_for_project(cleaned, pid)
    return {"subreddits": cleaned, "project_id": str(pid)}


@app.post("/admin/trigger-poll")
async def trigger_poll(project_id: Optional[UUID] = Query(None)):
    """Manually trigger a Reddit poll cycle (waits for completion)."""
    pid = _require_project_id(project_id)
    subreddits = get_reddit_subreddits_for_project(pid) or []
    if not subreddits:
        return {"status": "skipped", "message": "No subreddits configured", "project_id": str(pid)}
    
    from fastapi.concurrency import run_in_threadpool
    
    # Helper to ingest directly without HTTP request (avoids deadlock)
    def direct_ingest(payload: dict):
        try:
            # Inject project_id so the ingested feedback stays scoped correctly
            payload["project_id"] = pid
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
        return {"status": "ok", "message": f"Polled {len(subreddits)} subreddits", "project_id": str(pid)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# Simple clustering: group by source (and subreddit for Reddit)
def _auto_cluster_feedback(item: FeedbackItem) -> IssueCluster:
    now = datetime.now(timezone.utc)
    subreddit = None
    if isinstance(item.metadata, dict):
        subreddit = item.metadata.get("subreddit")

    if item.source == "reddit":
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
    existing = None
    for cluster in get_all_clusters():
        if cluster.project_id == item.project_id and cluster.title == cluster_title:
            existing = cluster
            break

    if existing:
        if str(item.id) not in existing.feedback_ids:
            updated_ids = existing.feedback_ids + [str(item.id)]
            return update_cluster(
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
    project_id: Optional[UUID] = Query(None),
):
    """
    Retrieve feedback items with optional filtering and pagination.

    Args:
        source: Optional source filter (reddit, sentry, manual)
        limit: Maximum number of items to return (default 100, max 1000)
        offset: Number of items to skip for pagination (default 0)

    Returns:
        Dictionary with items list and total count
    """
    pid = _require_project_id(project_id)
    all_items = [item for item in get_all_feedback_items() if item.project_id == pid]

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


@app.get("/feedback/{item_id}")
def get_feedback_by_id(item_id: UUID, project_id: Optional[UUID] = Query(None)):
    """
    Retrieve a single feedback item by its ID.

    Args:
        item_id: UUID of the feedback item

    Returns:
        The FeedbackItem if found

    Raises:
        HTTPException: 404 if item not found
    """
    pid = _require_project_id(project_id)
    item = get_feedback_item(item_id)
    if item is None:
        raise HTTPException(
            status_code=404, detail=f"Feedback item {item_id} not found"
        )
    if item.project_id != pid:
        raise HTTPException(status_code=404, detail="Feedback item not found for project")
    return item


@app.get("/stats")
def get_stats(project_id: Optional[UUID] = Query(None)):
    """
    Get summary statistics about feedback items and clusters.

    Returns:
        Dictionary with:
        - total_feedback: Total number of feedback items
        - by_source: Breakdown of feedback by source
        - total_clusters: Number of clusters (placeholder for future)
    """
    pid = _require_project_id(project_id)
    all_items = [item for item in get_all_feedback_items() if item.project_id == pid]
    total = len(all_items)

    # Count by source
    by_source = {"reddit": 0, "sentry": 0, "manual": 0}
    for item in all_items:
        if item.source in by_source:
            by_source[item.source] += 1

    total_clusters = len([c for c in get_all_clusters() if c.project_id == pid])

    return {
        "total_feedback": total,
        "by_source": by_source,
        "total_clusters": total_clusters,
        "project_id": str(pid),
    }


@app.get("/clusters")
def list_clusters(project_id: Optional[UUID] = Query(None)):
    """List all issue clusters with aggregated metadata."""

    pid = _require_project_id(project_id)
    clusters = [c for c in get_all_clusters() if c.project_id == pid]
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
                "project_id": str(pid),
            }
        )
    return results


@app.get("/clusters/{cluster_id}")
def get_cluster_detail(cluster_id: str, project_id: Optional[UUID] = Query(None)):
    """Retrieve a cluster with its feedback items."""

    pid = _require_project_id(project_id)
    cluster = get_cluster(cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    if cluster.project_id != pid:
        raise HTTPException(status_code=404, detail="Cluster not found for project")

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
    response["project_id"] = str(pid)
    return response


@app.post("/clusters/{cluster_id}/start_fix")
def start_cluster_fix(cluster_id: str, project_id: Optional[UUID] = Query(None)):
    """Begin fix generation for a cluster (stub implementation)."""

    pid = _require_project_id(project_id)
    cluster = get_cluster(cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    if cluster.project_id != pid:
        raise HTTPException(status_code=404, detail="Cluster not found for project")

    updated_cluster = update_cluster(cluster_id, status="fixing")
    return {
        "status": "ok",
        "message": "Fix generation started",
        "cluster_id": updated_cluster.id,
        "project_id": str(pid),
    }


def seed_mock_data():
    """Seed a handful of feedback items and clusters for local testing."""

    now = datetime.now(timezone.utc)
    pid = uuid4()
    
    # Create a user and project so feedback validation passes
    user = User(id=uuid4(), email="test@example.com", created_at=now)
    project = Project(id=pid, user_id=user.id, name="Mock Project", created_at=now)
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
def list_jobs(project_id: Optional[UUID] = Query(None)):
    """List all tracking jobs."""
    pid = _require_project_id(project_id)
    return [job for job in get_all_jobs() if job.project_id == pid]


@app.post("/jobs")
def create_job(payload: CreateJobRequest, project_id: Optional[UUID] = Query(None)):
    """Create a new tracking job for the coding agent."""
    pid = _require_project_id(project_id)
    cluster = get_cluster(payload.cluster_id)
    if not cluster or cluster.project_id != pid:
        raise HTTPException(status_code=404, detail="Cluster not found for project")
    now = datetime.now(timezone.utc)
    job = AgentJob(
        id=uuid4(),
        project_id=pid,
        cluster_id=payload.cluster_id,
        status="pending",
        logs=None,
        created_at=now,
        updated_at=now,
    )
    add_job(job)
    return {"status": "ok", "job_id": str(job.id), "project_id": str(pid)}


@app.patch("/jobs/{job_id}")
def update_job_status(job_id: UUID, payload: UpdateJobRequest, project_id: Optional[UUID] = Query(None)):
    """Update job status and/or logs."""
    pid = _require_project_id(project_id)
    job = get_job(job_id)
    if not job or job.project_id != pid:
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
def get_job_details(job_id: UUID, project_id: Optional[UUID] = Query(None)):
    """Retrieve details of a specific job."""
    pid = _require_project_id(project_id)
    job = get_job(job_id)
    if not job or job.project_id != pid:
        raise HTTPException(status_code=404, detail="Job not found for project")
    return job


@app.get("/clusters/{cluster_id}/jobs")
def get_cluster_jobs(cluster_id: str, project_id: Optional[UUID] = Query(None)):
    """List all jobs associated with a cluster."""
    pid = _require_project_id(project_id)
    cluster_jobs = get_jobs_by_cluster(cluster_id)
    return [job for job in cluster_jobs if job.project_id == pid]
