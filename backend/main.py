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
    """
    Ensure a project_id is provided; return the validated project UUID.
    
    Parameters:
        project_id (Optional[UUID]): The project identifier to validate.
    
    Returns:
        UUID: The provided `project_id` when present.
    
    Raises:
        HTTPException: With status code 400 if `project_id` is missing.
    """
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    return project_id


@app.post("/ingest/reddit")
def ingest_reddit(item: FeedbackItem, project_id: Optional[UUID] = Query(None)):
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
    Normalize a Sentry webhook payload into a FeedbackItem, persist it under the given project, and trigger automatic clustering.
    
    Parameters:
        payload (dict): Raw JSON payload received from Sentry's webhook.
        project_id (UUID | None): UUID of the project to associate the created FeedbackItem; required and validated by the function.
    
    Returns:
        dict: A response containing keys `"status"` (always `"ok"` on success), `"id"` (created feedback item UUID as a string), and `"project_id"` (associated project UUID as a string).
    
    Raises:
        HTTPException: If processing fails, an HTTP 500 error is raised with details about the failure.
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
def list_projects(user_id: UUID = Query(...)):
    """List projects for a user."""
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
    project = Project(id=uuid4(), user_id=payload.user_id, name=payload.name, created_at=now)
    create_project(project)
    return {"project": project}


@app.post("/ingest/manual")
def ingest_manual(request: ManualIngestRequest, project_id: Optional[UUID] = Query(None)):
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
def get_reddit_config(project_id: Optional[UUID] = Query(None)):
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
def set_reddit_config(payload: SubredditConfig, project_id: Optional[UUID] = Query(None)):
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


@app.post("/admin/trigger-poll")
async def trigger_poll(project_id: Optional[UUID] = Query(None)):
    """
    Trigger a single Reddit polling cycle for the specified project and wait for completion.
    
    Polls the project's configured subreddits and ingests any found posts directly into the store, then runs automatic clustering for each ingested item. If no subreddits are configured for the project, the operation is skipped.
    
    Parameters:
        project_id (Optional[UUID]): Project identifier used to scope the poll; required and validated by the endpoint.
    
    Returns:
        dict: A status payload. Examples:
            - {"status": "ok", "message": "Polled N subreddits", "project_id": "<uuid>"} on success.
            - {"status": "skipped", "message": "No subreddits configured", "project_id": "<uuid>"} if no subreddits are set.
    
    Raises:
        HTTPException: With status 500 if the polling or ingest process fails.
    """
    pid = _require_project_id(project_id)
    subreddits = get_reddit_subreddits_for_project(pid) or []
    if not subreddits:
        return {"status": "skipped", "message": "No subreddits configured", "project_id": str(pid)}
    
    from fastapi.concurrency import run_in_threadpool
    
    # Helper to ingest directly without HTTP request (avoids deadlock)
    def direct_ingest(payload: dict):
        """
        Ingest a raw feedback payload into storage and trigger automatic clustering for its project.
        
        The function constructs a FeedbackItem from the provided payload (after injecting the current project id), persists it, and runs the automatic clustering routine for the new item. Any exception raised during construction, persistence, or clustering is propagated.
        
        Parameters:
            payload (dict): Raw mapping of fields acceptable to FeedbackItem; the function will inject the current `project_id` before creating the item.
        """
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
    Return statistics for a project's feedback items and clusters.
    
    Returns:
        A dictionary containing:
        - total_feedback (int): Number of feedback items for the project.
        - by_source (dict): Counts of feedback items grouped by source keys `"reddit"`, `"sentry"`, and `"manual"`.
        - total_clusters (int): Number of clusters associated with the project.
        - project_id (str): The project's UUID as a string.
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
    """
    Start fix generation for the specified cluster.
    
    Returns:
        result (dict): Response containing:
            - status (str): "ok"
            - message (str): confirmation message
            - cluster_id (str): ID of the updated cluster
            - project_id (str): project UUID as a string
    
    Raises:
        HTTPException: 404 if the cluster does not exist or does not belong to the specified project.
    """

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
    """
    Create and persist a small set of mock data (user, project, three feedback items, and one cluster) for local testing.
    
    The function inserts a mock user and project, three FeedbackItem records covering reddit, sentry, and manual sources, and a single IssueCluster that references those items.
    
    Returns:
        result (dict): A dictionary containing:
            - cluster_id (str): The ID of the created cluster.
            - feedback_ids (list[UUID]): The UUIDs of the created feedback items.
    """

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
    """
    List AgentJob records for the specified project.
    
    Parameters:
        project_id (UUID): Project identifier used to scope the returned jobs. If omitted or None, an HTTP 400 error is raised.
    
    Returns:
        jobs (List[AgentJob]): List of jobs that belong to the given project.
    """
    pid = _require_project_id(project_id)
    return [job for job in get_all_jobs() if job.project_id == pid]


@app.post("/jobs")
def create_job(payload: CreateJobRequest, project_id: Optional[UUID] = Query(None)):
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
    if not job or job.project_id != pid:
        raise HTTPException(status_code=404, detail="Job not found for project")
    return job


@app.get("/clusters/{cluster_id}/jobs")
def get_cluster_jobs(cluster_id: str, project_id: Optional[UUID] = Query(None)):
    """
    Return the AgentJob records for the given cluster that belong to the specified project.
    
    Filters jobs by `cluster_id` and the provided `project_id` (required); if `project_id` is missing an HTTP 400 is raised.
    
    Returns:
        List[AgentJob]: Jobs belonging to the cluster and project.
    """
    pid = _require_project_id(project_id)
    cluster_jobs = get_jobs_by_cluster(cluster_id)
    return [job for job in cluster_jobs if job.project_id == pid]