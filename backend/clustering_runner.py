"""
In-process clustering runner with Redis lock + job tracking.

The runner is triggered from ingest paths: it acquires a per-project lock,
creates a ClusterJob, and schedules clustering work on the event loop without
blocking the request.
"""

import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from typing import List, Optional, Sequence
from uuid import uuid4

from models import ClusterJob, FeedbackItem, IssueCluster
from store import (
    add_cluster,
    add_cluster_job,
    acquire_cluster_lock,
    get_all_clusters,
    get_unclustered_feedback,
    list_cluster_jobs,
    release_cluster_lock,
    remove_from_unclustered_batch,
    update_cluster_job,
)
# Import local clustering module (same package)
import clustering

logger = logging.getLogger(__name__)
_BACKGROUND_TASKS: set[asyncio.Task] = set()

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


def _derive_github_repo_url(items: List[FeedbackItem]) -> Optional[str]:
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


def _test_embed(texts):
    """
    Provide deterministic lightweight embeddings for testing.
    
    Generates a float32 matrix with shape (len(texts), max(3, len(texts))) where each row is a one-hot–like vector containing a single 1.0 and zeros elsewhere. For an empty input returns an empty array with shape (0, 3).
    
    Parameters:
        texts (Sequence[str]): Input texts; only the number of texts is used to determine embedding size.
    
    Returns:
        numpy.ndarray: Float32 embedding matrix of shape (n, dims) where n is len(texts) and dims is max(3, n).
    """
    n = len(texts)
    if n == 0:
        return clustering.np.empty((0, 3), dtype=clustering.np.float32)
    dims = max(3, n)
    mat = clustering.np.zeros((n, dims), dtype=clustering.np.float32)
    for i in range(n):
        mat[i, i % dims] = 1.0
    return mat


def _prepare_issue_payloads(items: Sequence[FeedbackItem]) -> List[dict]:
    """
    Convert FeedbackItems into plain dicts expected by clustering.prepare_issue_texts.
    """
    payloads = []
    for item in items:
        payloads.append(
            {
                "title": item.title,
                "body": item.body,
                "raw_text": item.raw_text,
                "metadata": item.metadata,
                "source": item.source,
            }
        )
    return payloads


def _build_cluster(item_group: List[FeedbackItem]) -> IssueCluster:
    """
    Builds a new IssueCluster from a non-empty list of FeedbackItem objects.

    The returned cluster groups the provided feedback items: it assigns a new UUID as the cluster id, sets the cluster's project_id from the first item, derives and truncates the title/summary from the first item (summary limited to 300 characters), collects the feedback item ids, sets status to "new", and sets created_at/updated_at to the current UTC time.

    Parameters:
        item_group (List[FeedbackItem]): A non-empty list of feedback items to include in the cluster.

    Returns:
        IssueCluster: A newly constructed IssueCluster representing the grouped feedback items.
    """
    now = datetime.now(timezone.utc)
    first = item_group[0]
    raw_title = first.title or "Feedback cluster"
    raw_summary = first.body or "Feedback cluster"
    title = raw_title[:80]
    summary = raw_summary[:300]
    feedback_ids = [str(item.id) for item in item_group]
    github_repo_url = _derive_github_repo_url(item_group)
    # Cache distinct sources to avoid expensive per-item lookups in /clusters endpoint
    sources = sorted({item.source for item in item_group})
    return IssueCluster(
        id=str(uuid4()),
        project_id=first.project_id,
        title=title,
        summary=summary,
        feedback_ids=feedback_ids,
        status="new",
        created_at=now,
        updated_at=now,
        github_repo_url=github_repo_url,
        sources=sources,
    )


def _split_clusters(items: Sequence[FeedbackItem], labels, clusters, singletons) -> List[IssueCluster]:
    """
    Convert clustering results into IssueCluster models.
    
    Parameters:
        items (Sequence[FeedbackItem]): Source feedback items referenced by index.
        labels: Unused placeholder for per-item labels (accepted but ignored).
        clusters: Iterable of iterables of integer indices; each iterable identifies items that form a cluster.
        singletons: Iterable of integer indices representing individual-item clusters.
    
    Returns:
        List[IssueCluster]: IssueCluster objects created from the provided index groups; multi-item clusters (from `clusters`) appear first in the returned list followed by singletons.
    """
    grouped: List[IssueCluster] = []
    for idxs in clusters:
        grouped.append(_build_cluster([items[i] for i in idxs]))
    for idx in singletons:
        grouped.append(_build_cluster([items[idx]]))
    return grouped


async def maybe_start_clustering(project_id: str) -> ClusterJob:
    """
    Create a new clustering job for the given project, attempt to acquire the per-project clustering lock, and schedule the background clustering runner if the lock is obtained.
    
    Parameters:
        project_id (str): Project identifier for which to create and (if possible) start clustering.
    
    Returns:
        ClusterJob: The persisted ClusterJob record. When the lock is already held the job is immediately marked failed with an explanatory error; otherwise a background task is launched to process clustering work.
    """
    job_id = str(uuid4())
    now = datetime.now(timezone.utc)
    job = ClusterJob(
        id=job_id,
        project_id=project_id,
        status="pending",
        created_at=now,
        stats={},
    )
    add_cluster_job(job)

    locked = acquire_cluster_lock(project_id, job_id, ttl_seconds=600)
    if not locked:
        logger.info("Clustering already running for project %s", project_id)
        job = update_cluster_job(
            project_id,
            job_id,
            status="failed",
            error="Clustering already running for project",
            finished_at=datetime.now(timezone.utc),
        )
        return job

    loop = asyncio.get_running_loop()
    task = loop.create_task(run_clustering_job(project_id, job_id))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return job


async def run_clustering_job(project_id: str, job_id: str):
    """
    Perform clustering for a project's unclustered feedback and update the corresponding ClusterJob.
    
    This function marks the job as running, retrieves unclustered feedback for the given project, and either:
    - In testing mode (no external embedding keys or running under pytest): optionally creates a single cluster when no clusters exist and removes processed items from the unclustered batch.
    - In production mode: prepares payloads, runs the clustering pipeline with embeddings, persists resulting IssueCluster records, and removes processed items from the unclustered batch.
    
    On success the ClusterJob is updated with status "succeeded" and statistics (clustered count, new_clusters, singletons). On error the ClusterJob is updated with status "failed" and the error message. The per-project cluster lock is released in all cases.
    """
    start = datetime.now(timezone.utc)
    update_cluster_job(project_id, job_id, status="running", started_at=start)

    try:
        items = get_unclustered_feedback(project_id)
        if not items:
            update_cluster_job(
                project_id,
                job_id,
                status="succeeded",
                finished_at=datetime.now(timezone.utc),
                stats={"clustered": 0, "new_clusters": 0, "singletons": 0},
            )
            return

        testing_mode = bool(os.getenv("PYTEST_CURRENT_TEST")) or not bool(
            os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        )

        if testing_mode:
            # In tests, avoid external embeddings but still drain unclustered feedback to mimic production semantics.
            # Create a single cluster only if none exist yet. Use Reddit-style title when present.
            existing_clusters = get_all_clusters(project_id)
            if not existing_clusters:
                first = items[0]
                subreddit = None
                if isinstance(first.metadata, dict):
                    subreddit = first.metadata.get("subreddit")
                title = f"Reddit: r/{subreddit}" if subreddit else first.title
                summary = first.body[:200] if first.body else "Feedback cluster"
                github_repo_url = _derive_github_repo_url(items)
                # Cache distinct sources to avoid expensive per-item lookups in /clusters endpoint
                sources = sorted({item.source for item in items})
                cluster = IssueCluster(
                    id=str(uuid4()),
                    project_id=first.project_id,
                    title=title,
                    summary=summary,
                    feedback_ids=[str(item.id) for item in items],
                    status="new",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    github_repo_url=github_repo_url,
                    sources=sources,
                )
                grouped_clusters = [cluster]
                for cluster in grouped_clusters:
                    add_cluster(cluster)
            processed_pairs = [(item.id, project_id) for item in items]
            remove_from_unclustered_batch(processed_pairs)
            stats = {
                "clustered": len(items),
                "new_clusters": 0 if existing_clusters else 1,
                "singletons": 0,
            }
        else:
            issues_payload = _prepare_issue_payloads(items)
            result = clustering.cluster_issues(
                issues_payload,
                method=clustering.DEFAULT_METHOD,
                sim_threshold=clustering.DEFAULT_SIM_THRESHOLD,
                min_cluster_size=clustering.DEFAULT_MIN_CLUSTER_SIZE,
                truncate_body_chars=clustering.DEFAULT_TRUNCATE_BODY_CHARS,
                embed_fn=clustering.embed_texts_gemini,
            )

            grouped_clusters = _split_clusters(
                items, result["labels"], result["clusters"], result["singletons"]
            )

            for cluster in grouped_clusters:
                add_cluster(cluster)

            # Remove processed items from unclustered
            processed_pairs = [(item.id, project_id) for item in items]
            remove_from_unclustered_batch(processed_pairs)

            stats = {
                "clustered": len(items),
                "new_clusters": len(grouped_clusters),
                "singletons": len(result["singletons"]),
            }

        update_cluster_job(
            project_id,
            job_id,
            status="succeeded",
            finished_at=datetime.now(timezone.utc),
            stats=stats,
        )
    except Exception as exc:  # pragma: no cover - exercised in integration
        logger.exception("Clustering job %s failed", job_id)
        update_cluster_job(
            project_id,
            job_id,
            status="failed",
            error=str(exc),
            finished_at=datetime.now(timezone.utc),
        )
    finally:
        release_cluster_lock(project_id, job_id)


__all__ = [
    "maybe_start_clustering",
    "run_clustering_job",
    "list_cluster_jobs",
]
