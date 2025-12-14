import asyncio
from uuid import uuid4

import numpy as np
import pytest

import clustering_runner
import clustering as clustering_core
from models import FeedbackItem
from store import (
    add_feedback_item,
    clear_clusters,
    clear_feedback_items,
    get_all_clusters,
    get_unclustered_feedback,
    list_cluster_jobs,
    acquire_cluster_lock,
)

anyio_backend = "asyncio"


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    """
    Specify the anyio backend to use for tests.
    
    Returns:
        backend (str): The anyio backend identifier "asyncio".
    """
    return "asyncio"


def _make_feedback(project_id: str, title: str) -> FeedbackItem:
    """
    Create a FeedbackItem for tests using the given project ID and title.
    
    Parameters:
        project_id (str): The project identifier to associate with the feedback item.
        title (str): The title text for the feedback item.
    
    Returns:
        FeedbackItem: A feedback item with a generated UUID `id`, `source` set to "manual", `title` set to the provided value, `body` set to "<title> body", empty `metadata`, and `created_at` set to the current UTC time.
    """
    return FeedbackItem(
        id=uuid4(),
        project_id=project_id,
        source="manual",
        title=title,
        body=f"{title} body",
        metadata={},
        created_at=clustering_runner.datetime.now(clustering_runner.timezone.utc),
    )


async def test_run_clustering_job_writes_clusters(monkeypatch):
    project_id = str(uuid4())
    clear_feedback_items(project_id)
    clear_clusters(project_id)

    add_feedback_item(_make_feedback(project_id, "Export fails"))
    add_feedback_item(_make_feedback(project_id, "Export timeout"))

    def fake_cluster_issues(issues, **kwargs):
        """
        Create a deterministic fake clustering result from a list of issue-like dicts.
        
        Parameters:
            issues (Iterable[Mapping]): Iterable of mappings representing issues; each mapping is expected to contain a "title" key.
        
        Returns:
            dict: A clustering result with keys:
                - "labels": numpy.ndarray of integer cluster labels (one label per input issue).
                - "clusters": list of clusters, each cluster is a list of issue indices.
                - "singletons": list of singleton issue indices.
                - "texts": list of issue titles extracted from the input.
        """
        return {
            "labels": np.array([0, 0]),
            "clusters": [[0, 1]],
            "singletons": [],
            "texts": [i["title"] for i in issues],
        }

    monkeypatch.setattr(clustering_core, "cluster_issues", fake_cluster_issues)

    job = await clustering_runner.maybe_start_clustering(project_id)
    await clustering_runner.run_clustering_job(project_id, job.id)

    clusters = get_all_clusters(project_id)
    assert len(clusters) == 1
    assert clusters[0].feedback_ids and len(clusters[0].feedback_ids) == 2
    assert get_unclustered_feedback(project_id) == []

    jobs = list_cluster_jobs(project_id)
    assert jobs
    assert jobs[0].status == "succeeded"
    assert jobs[0].stats.get("clustered") == 2


async def test_maybe_start_clustering_respects_lock(monkeypatch):
    project_id = str(uuid4())
    clear_feedback_items(project_id)
    clear_clusters(project_id)

    # Pre-acquire lock to simulate active run
    acquired = acquire_cluster_lock(project_id, "existing-job", ttl_seconds=30)
    assert acquired is True

    def fake_cluster_issues(issues, **kwargs):
        """
        Produce an empty clustering result for the provided issues.
        
        Parameters:
            issues (iterable): Input issues to cluster (not inspected by this fake implementation).
        
        Returns:
            dict: A clustering result with keys:
                - "labels": an empty numpy.ndarray of labels.
                - "clusters": an empty list of clusters.
                - "singletons": an empty list of singleton issue indices.
                - "texts": an empty list of issue texts.
        """
        return {"labels": np.array([]), "clusters": [], "singletons": [], "texts": []}

    monkeypatch.setattr(clustering_core, "cluster_issues", fake_cluster_issues)

    job = await clustering_runner.maybe_start_clustering(project_id)
    # Because lock was held, the job should remain pending and not process data
    assert job.status == "pending"

    # Release lock for cleanup
    clustering_runner.release_cluster_lock(project_id, "existing-job")