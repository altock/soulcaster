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
    add_feedback_to_cluster,
    get_all_clusters,
    get_cluster,
    get_unclustered_feedback,
    list_cluster_jobs,
    release_cluster_lock,
    remove_from_unclustered_batch,
    update_cluster_job,
)
# Import local clustering module (same package)
import clustering
from vector_store import (
    VectorStore,
    FeedbackVectorMetadata,
    cluster_with_vector_db,
    VECTOR_CLUSTERING_THRESHOLD,
)
from clustering_runner_v2 import VectorDBClusteringEngine

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


def _run_vector_clustering(
    items: List[FeedbackItem],
    project_id: str,
) -> dict:
    """
    Cluster feedback items using proper vector DB engine with audit trail.

    Strategy:
    1. Generate embeddings for all items
    2. Query vector DB for existing similar items (read-only, with EC handling)
    3. Cluster in-memory with explicit decision tracking (audit trail)
    4. Batch upsert everything at the end (single write)

    Returns clustering result with audit trail for explainability.
    """
    if not items:
        return {
            "new_clusters": [],
            "updated_clusters": [],
            "items_clustered": 0,
            "audit_trail": {},
        }

    # Initialize vector store and clustering engine
    try:
        vector_store = VectorStore()
        engine = VectorDBClusteringEngine(vector_store)
    except Exception as e:
        logger.error("Failed to initialize clustering engine: %s", e)
        raise

    # Prepare texts and generate embeddings
    issues_payload = _prepare_issue_payloads(items)
    texts = clustering.prepare_issue_texts(issues_payload)
    try:
        embeddings = clustering.embed_texts_gemini(texts)
    except Exception as e:
        logger.error("Failed to generate embeddings: %s", e)
        raise RuntimeError(f"Embedding generation failed: {e}") from e

    # Run the clustering engine (3-phase: query, cluster, upsert)
    clustering_result = engine.cluster_batch(items, embeddings, project_id)

    # Phase 3: Persist clusters to Redis
    new_clusters: List[IssueCluster] = []
    updated_cluster_ids: set = set()

    for cluster_id, item_ids in clustering_result.clusters.items():
        # Get the items in this cluster
        cluster_items = [item for item in items if str(item.id) in item_ids]

        if not cluster_items:
            continue

        # Check if cluster already exists in Redis
        existing_cluster = get_cluster(project_id, cluster_id)

        if existing_cluster:
            # Add items to existing cluster
            updated_cluster_ids.add(cluster_id)
            for item in cluster_items:
                add_feedback_to_cluster(cluster_id, str(item.id), project_id)
        else:
            # Create new cluster
            cluster = _build_cluster(cluster_items)
            cluster.id = cluster_id
            new_clusters.append(cluster)
            add_cluster(cluster)
            # Add all items to the cluster
            for item in cluster_items:
                add_feedback_to_cluster(cluster_id, str(item.id), project_id)

    logger.info(
        f"Clustered {clustering_result.items_clustered} items into {len(clustering_result.clusters)} clusters "
        f"({len(new_clusters)} new, {len(updated_cluster_ids)} updated) "
        f"in {clustering_result.performance_metrics.get('total', 0):.3f}s"
    )

    return {
        "new_clusters": new_clusters,
        "updated_clusters": list(updated_cluster_ids),
        "items_clustered": clustering_result.items_clustered,
        "audit_trail": clustering_result.audit_trail,
        "performance_metrics": clustering_result.performance_metrics,
    }


async def maybe_start_clustering(project_id: str) -> ClusterJob:
    """
    Create and persist a ClusterJob for the given project and, if a per-project lock is acquired, schedule the background clustering runner.
    
    If the project-level lock cannot be obtained the job is marked as failed with an explanatory error and finished timestamp; if the lock is obtained a background task is started and the job remains pending.
    
    Returns:
        ClusterJob: The persisted ClusterJob record reflecting the outcome described above.
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

    # Debug: log when task completes or fails
    def task_done_callback(t):
        _BACKGROUND_TASKS.discard(t)
        if t.exception():
            logger.error(f"Clustering task failed with exception: {t.exception()}")
        else:
            logger.info(f"Clustering task completed successfully")

    task.add_done_callback(task_done_callback)
    logger.info(f"Started clustering task for project {project_id}, job {job_id}")
    return job


async def run_clustering_job(project_id: str, job_id: str):
    """
    Run the clustering job for a project and update its ClusterJob record.

    Executes clustering for all unclustered feedback in the specified project: marks the job as running, processes unclustered items either with a deterministic testing-mode shortcut (no external embedding keys or under pytest) or with the production vector-based pipeline, persists any created IssueCluster records, removes processed items from the unclustered batch, and updates the ClusterJob with final status, finish time, and statistics. On success the job is set to "succeeded" and stats include keys such as `clustered`, `new_clusters`, and `updated_clusters` (or `singletons` in testing mode); on error the job is set to "failed" with the error message. The per-project cluster lock is released regardless of outcome.
    """
    start = datetime.now(timezone.utc)
    update_cluster_job(project_id, job_id, status="running", started_at=start)

    try:
        items = get_unclustered_feedback(project_id)
        logger.info(f"Clustering job {job_id}: Found {len(items)} unclustered items")
        if not items:
            update_cluster_job(
                project_id,
                job_id,
                status="succeeded",
                finished_at=datetime.now(timezone.utc),
                stats={"clustered": 0, "new_clusters": 0, "singletons": 0},
            )
            return

        # Always use vector-based clustering - no fake test mode
        result = _run_vector_clustering(items, project_id)

        # Remove processed items from unclustered
        processed_pairs = [(item.id, project_id) for item in items]
        remove_from_unclustered_batch(processed_pairs)

        stats = {
            "clustered": result["items_clustered"],
            "new_clusters": len(result["new_clusters"]),
            "updated_clusters": len(result["updated_clusters"]),
        }

        # Convert audit trail from dataclass to dict for storage
        audit_trail_dict = {}
        if result.get("audit_trail"):
            for item_id, decision in result["audit_trail"].items():
                # Convert ClusteringDecision dataclass to dict
                audit_trail_dict[item_id] = decision.to_dict() if hasattr(decision, 'to_dict') else {
                    "item_id": decision.item_id,
                    "cluster_id": decision.cluster_id,
                    "decision_type": decision.decision_type,
                    "similarity_score": decision.similarity_score,
                    "matched_item_id": decision.matched_item_id,
                    "timestamp": decision.timestamp.isoformat() if hasattr(decision.timestamp, 'isoformat') else str(decision.timestamp),
                    "confidence": decision.confidence,
                    "details": decision.details,
                }

        update_cluster_job(
            project_id,
            job_id,
            status="succeeded",
            finished_at=datetime.now(timezone.utc),
            stats=stats,
            audit_trail=audit_trail_dict,
            performance_metrics=result.get("performance_metrics", {}),
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