"""FastAPI application for FeedbackAgent data ingestion.

This module provides HTTP endpoints for ingesting feedback from multiple sources:
- Reddit posts (normalized via reddit_poller)
- Sentry webhook events
- Manual text submissions
"""

import asyncio
import logging
import os
import sys
import re
from dotenv import load_dotenv

load_dotenv()

from datetime import datetime, timezone
import time
from typing import Dict, List, Optional, Literal, Tuple
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, HTTPException, Path, Query, Request, BackgroundTasks
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
    set_reddit_subreddits_for_project,
    get_reddit_subreddits_for_project,
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
)
from planner import generate_plan
from github_client import fetch_repo_issues, issue_to_feedback_item
from clustering_runner import maybe_start_clustering, run_clustering_job
from agent_runner import get_runner
# Ensure runners are registered
import agent_runner.sandbox
import agent_runner.aws

app = FastAPI(
    title="FeedbackAgent Ingestion API",
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
    """Health check endpoint."""
    return {"status": "ok", "service": "feedbackagent-ingestion"}


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
    add_feedback_item(item)
    _kickoff_clustering(pid_str)
    return {"status": "ok", "id": str(item.id), "project_id": pid_str}


# ============================================================
# PHASE 2: SENTRY INTEGRATION (Currently deferred)
# ============================================================
@app.post("/ingest/sentry")
def ingest_sentry(payload: dict, project_id: Optional[str] = Query(None)):
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
        _kickoff_clustering(str(pid))
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
    
    Fetches issues from the specified GitHub repository, creates or updates FeedbackItems in the target project using each issue's external ID, removes closed issues from the unclustered set, and triggers asynchronous clustering when there are items to cluster. Pull requests are ignored. The in-memory sync state for the (project, repo) pair is updated with `last_synced` and `issue_count`.
    
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
            - closed_issues (int): number of issues marked closed and removed from unclustered.
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

    try:
        fetch_start = time.monotonic()
        logger.info(f"Fetching issues from GitHub API for {owner}/{repo}...")
        fetch_kwargs = {
            "since": since,
            "max_pages": int(os.getenv("GITHUB_SYNC_MAX_PAGES", "20")),
            "max_issues": int(os.getenv("GITHUB_SYNC_MAX_ISSUES", "2000")),
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
            "closed_issues": 0,
            "total_issues": 0,
            "last_synced": datetime.now(timezone.utc).isoformat(),
            "project_id": project_id,
            "synced_ids": [],
        }

    new_count = 0
    updated_count = 0
    closed_count = 0
    synced_ids: List[str] = []

    external_ids = [str(issue.get("id")) for issue in issues if issue.get("id") is not None]
    existing_feedback_map = get_feedback_by_external_ids_batch(project_id, "github", external_ids)

    feedback_items: List[FeedbackItem] = []
    closed_pairs: List[Tuple[UUID, str]] = []
    to_cluster: List[FeedbackItem] = []

    for issue in issues:
        external_id = str(issue.get("id"))
        existing = existing_feedback_map.get(external_id)

        if existing:
            # Refresh fields while preserving the stored UUID
            feedback_item = issue_to_feedback_item(issue, repo_full_name, project_id).model_copy(
                update={"id": existing.id}
            )
            updated_count += 1
        else:
            feedback_item = issue_to_feedback_item(issue, repo_full_name, project_id)
            new_count += 1

        feedback_items.append(feedback_item)

        if issue.get("state") == "closed":
            closed_pairs.append((feedback_item.id, project_id))
            closed_count += 1
        else:
            to_cluster.append(feedback_item)

        synced_ids.append(str(feedback_item.id))

    # Batch write all feedback items
    write_start = time.monotonic()
    add_feedback_items_batch(feedback_items)
    logger.info(
        "Wrote %d feedback items (%.2fs)",
        len(feedback_items),
        time.monotonic() - write_start,
    )

    # Batch remove closed items from unclustered
    if closed_pairs:
        prune_start = time.monotonic()
        remove_from_unclustered_batch(closed_pairs)
        logger.info(
            "Removed %d closed items from unclustered (%.2fs)",
            len(closed_pairs),
            time.monotonic() - prune_start,
        )

    if to_cluster:
        _kickoff_clustering(project_id)

    now_iso = datetime.now(timezone.utc).isoformat()
    GITHUB_SYNC_STATE[state_key] = {
        "last_synced": now_iso,
        "issue_count": str(len(issues)),
    }

    logger.info(
        "Sync complete: %d new, %d updated, %d closed in %.2fs",
        new_count,
        updated_count,
        closed_count,
        time.monotonic() - overall_start,
    )
    
    return {
        "success": True,
        "repo": repo_full_name,
        "new_issues": new_count,
        "updated_issues": updated_count,
        "closed_issues": closed_count,
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
    
    from fastapi.concurrency import run_in_threadpool
    
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
    item_id: UUID, payload: FeedbackUpdate, project_id: Optional[str] = Query(None)
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
def get_feedback_by_id(item_id: UUID, project_id: Optional[str] = Query(None)):
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
    clusters = get_all_clusters(pid_str)
    results = []
    for cluster in clusters:
        feedback_items = []
        for fid in cluster.feedback_ids:
            try:
                item = get_feedback_item(pid_str, UUID(fid))
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
def list_cluster_job_status(project_id: Optional[str] = Query(None), limit: int = Query(20, ge=1, le=50)):
    """
    Retrieve recent clustering jobs for the given project.
    
    Parameters:
        project_id: Project identifier to scope the returned jobs.
        limit: Maximum number of jobs to return (1–50).
    
    Returns:
        dict: {"jobs": list of ClusterJob objects, "project_id": project id string}
    """
    pid = _require_project_id(project_id)
    jobs = list_cluster_jobs(pid, limit=limit)
    return {"jobs": jobs, "project_id": pid}


@app.get("/clustering/status")
def clustering_status(project_id: Optional[str] = Query(None)):
    """
    Report clustering queue status for a project.
    
    Parameters:
        project_id (Optional[str]): Project identifier; if omitted or invalid, a 400 HTTPException is raised.
    
    Returns:
        dict: {
            "pending_unclustered": int,   # number of feedback items awaiting clustering
            "is_clustering": bool,        # `true` if a clustering job is currently running
            "last_job": ClusterJob|None,  # the most recent cluster job record or `None`
            "project_id": str             # normalized project id
        }
    
    Raises:
        HTTPException: If `project_id` is missing or invalid.
    """
    pid = _require_project_id(project_id)
    pending = len(get_unclustered_feedback(pid))
    recent = list_cluster_jobs(pid, limit=10)
    last_job = recent[0] if recent else None
    is_clustering = any(job.status == "running" for job in recent)
    return {"pending_unclustered": pending, "is_clustering": is_clustering, "last_job": last_job, "project_id": pid}


@app.get("/clusters/{cluster_id}/plan")
def get_cluster_plan(cluster_id: str, project_id: Optional[str] = Query(None)):
    """
    Retrieve the latest generated coding plan for a cluster.
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

    # 1. Valdiate cluster
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
    from fastapi import BackgroundTasks

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
def update_job_status(job_id: UUID, payload: UpdateJobRequest, project_id: Optional[str] = Query(None)):
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
def get_job_details(job_id: UUID, project_id: Optional[str] = Query(None)):
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
    job_id: UUID,
    project_id: Optional[str] = Query(None),
    cursor: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
):
    """
    Retrieve persisted log chunks for a job.

    This endpoint is designed for UI log tailing without forcing the backend to print logs to stdout.
    """
    pid = _require_project_id(project_id)
    job = get_job(job_id)
    if not job or str(job.project_id) != pid:
        raise HTTPException(status_code=404, detail="Job not found for project")
    chunks, next_cursor, has_more = get_job_logs(job_id, cursor=cursor, limit=limit)
    return {
        "job_id": str(job_id),
        "project_id": str(pid),
        "cursor": cursor,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "chunks": chunks,
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
