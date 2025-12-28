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


def _make_github_feedback(project_id: str, title: str, issue_url: str) -> FeedbackItem:
    return FeedbackItem(
        id=uuid4(),
        project_id=project_id,
        source="github",
        title=title,
        body=f"{title} body",
        raw_text=f"See {issue_url}",
        metadata={},
        created_at=clustering_runner.datetime.now(clustering_runner.timezone.utc),
        github_issue_url=issue_url,
        repo="owner/repo",
        github_issue_number=123,
        status="open",
    )


async def test_run_clustering_job_writes_clusters(monkeypatch):
    from unittest.mock import MagicMock, patch

    project_id = str(uuid4())
    clear_feedback_items(project_id)
    clear_clusters(project_id)

    add_feedback_item(_make_feedback(project_id, "Export fails"))
    add_feedback_item(_make_feedback(project_id, "Export timeout"))

    # Mock embeddings
    fake_embeddings = np.array([[0.1] * 768, [0.2] * 768])
    monkeypatch.setattr(clustering_core, "embed_texts_gemini", lambda texts: fake_embeddings)

    # Mock VectorStore - make items cluster together
    mock_vector_store = MagicMock()
    call_count = [0]
    first_cluster_id = [None]

    def mock_find_similar(embedding, top_k=20, min_score=0.0, exclude_ids=None, project_id=None):
        from vector_store import SimilarFeedback, FeedbackVectorMetadata
        call_count[0] += 1
        if call_count[0] == 1:
            return []  # First item: no similar items
        else:
            # Second item: return first item as similar with cluster_id
            return [SimilarFeedback(
                id="first-item-id",
                score=0.95,
                metadata=FeedbackVectorMetadata(
                    title="Export fails",
                    source="manual",
                    cluster_id=first_cluster_id[0],
                ),
            )]

    def mock_upsert(feedback_id, embedding, metadata, project_id=None):
        if first_cluster_id[0] is None:
            first_cluster_id[0] = metadata.cluster_id

    mock_vector_store.find_similar = mock_find_similar
    mock_vector_store.upsert_feedback = mock_upsert
    mock_vector_store.upsert_feedback_batch = MagicMock()
    mock_vector_store.update_cluster_assignment_batch = MagicMock()

    with patch("clustering_runner.VectorStore", return_value=mock_vector_store):
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


async def test_run_clustering_job_sets_cluster_repo_url(monkeypatch):
    from unittest.mock import MagicMock, patch

    project_id = str(uuid4())
    clear_feedback_items(project_id)
    clear_clusters(project_id)

    # Add only GitHub items to test github_repo_url extraction
    github_item = _make_github_feedback(
        project_id,
        "Export fails",
        "https://github.com/octocat/Hello-World/issues/1",
    )
    add_feedback_item(github_item)

    # Mock embeddings
    fake_embeddings = np.array([[0.1] * 768])
    monkeypatch.setattr(clustering_core, "embed_texts_gemini", lambda texts: fake_embeddings)

    # Mock VectorStore - single item creates new cluster
    mock_vector_store = MagicMock()
    mock_vector_store.find_similar.return_value = []  # No similar items
    mock_vector_store.upsert_feedback = MagicMock()
    mock_vector_store.update_cluster_assignment_batch = MagicMock()

    with patch("clustering_runner.VectorStore", return_value=mock_vector_store):
        job = await clustering_runner.maybe_start_clustering(project_id)
        await clustering_runner.run_clustering_job(project_id, job.id)

    clusters = get_all_clusters(project_id)
    assert len(clusters) == 1
    assert clusters[0].github_repo_url == "https://github.com/octocat/Hello-World"


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
    # Because lock was held, the job should not run and is marked failed with an explanatory error
    assert job.status == "failed"
    assert job.error == "Clustering already running for project"

    # Release lock for cleanup
    clustering_runner.release_cluster_lock(project_id, "existing-job")


async def test_vector_clustering_batch_upsert_format(monkeypatch):
    """
    Regression test: Verify upsert_feedback_batch is called with correct format.

    This catches bugs where we pass wrong keys in the batch items dict.
    """
    from unittest.mock import MagicMock, patch
    from vector_store import FeedbackVectorMetadata

    project_id = str(uuid4())
    clear_feedback_items(project_id)
    clear_clusters(project_id)

    # Add test items
    item1 = _make_feedback(project_id, "Login button broken")
    item2 = _make_feedback(project_id, "Login form not working")
    add_feedback_item(item1)
    add_feedback_item(item2)

    # Mock embeddings to avoid Gemini API call
    fake_embeddings = np.array([[0.1] * 768, [0.2] * 768])
    monkeypatch.setattr(clustering_core, "embed_texts_gemini", lambda texts: fake_embeddings)

    # Create a mock VectorStore that tracks calls
    mock_vector_store = MagicMock()
    mock_vector_store.find_similar.return_value = []  # No similar items found

    # Track upsert_feedback_batch calls
    batch_upsert_calls = []
    def track_batch_upsert(items, project_id=None):
        """Track that upsert_feedback_batch is called with correct format."""
        batch_upsert_calls.append(items)
    mock_vector_store.upsert_feedback_batch = track_batch_upsert

    # Patch VectorStore constructor in clustering_runner module
    with patch("clustering_runner.VectorStore", return_value=mock_vector_store):
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

        job = await clustering_runner.maybe_start_clustering(project_id)
        await clustering_runner.run_clustering_job(project_id, job.id)

    # Verify upsert_feedback_batch was called once with all items
    assert len(batch_upsert_calls) == 1, f"Expected 1 batch upsert call, got {len(batch_upsert_calls)}"

    items = batch_upsert_calls[0]
    assert len(items) == 2, f"Expected 2 items in batch, got {len(items)}"

    # Verify each item has correct keys and types
    for item in items:
        assert "id" in item, "item should have 'id' key"
        assert "embedding" in item, "item should have 'embedding' key"
        assert "metadata" in item, "item should have 'metadata' key"
        assert isinstance(item["id"], str), "id should be a string"
        assert isinstance(item["embedding"], list), "embedding should be a list"
        assert isinstance(item["metadata"], FeedbackVectorMetadata), "metadata should be FeedbackVectorMetadata"
        assert item["metadata"].cluster_id is not None, "cluster_id should be set"
