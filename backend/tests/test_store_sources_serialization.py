"""Tests for sources field serialization in store.py."""

from datetime import datetime, timezone
from uuid import uuid4

from models import IssueCluster
from store import add_cluster, clear_clusters, get_cluster


def setup_function():
    """Clear persistent clusters before each test."""
    clear_clusters()


def test_sources_list_serialization_and_deserialization():
    """Test that sources list is properly JSON-encoded on write and decoded on read.
    
    This test validates the fix for the issue where sources was being converted
    to a Python repr string (e.g., "['github', 'sentry']") instead of proper JSON.
    """
    project_id = str(uuid4())
    cluster_id = str(uuid4())
    now = datetime.now(timezone.utc)
    
    # Create a cluster with sources as a list
    original_sources = ["github", "sentry", "reddit"]
    cluster = IssueCluster(
        id=cluster_id,
        project_id=project_id,
        title="Test Cluster",
        summary="Testing sources serialization",
        feedback_ids=["feedback1", "feedback2"],
        status="new",
        created_at=now,
        updated_at=now,
        sources=original_sources,
    )
    
    # Add the cluster to the store
    add_cluster(cluster)
    
    # Retrieve the cluster from the store
    retrieved_cluster = get_cluster(project_id, cluster_id)
    
    # Validate that sources is still a list and has the correct values
    assert retrieved_cluster is not None, "Cluster should be retrieved successfully"
    assert isinstance(retrieved_cluster.sources, list), "sources should be a list, not a string"
    assert retrieved_cluster.sources == original_sources, "sources values should match original"
    assert set(retrieved_cluster.sources) == {"github", "sentry", "reddit"}, "sources should contain all original items"


def test_sources_empty_list():
    """Test that empty sources list is properly handled."""
    project_id = str(uuid4())
    cluster_id = str(uuid4())
    now = datetime.now(timezone.utc)
    
    cluster = IssueCluster(
        id=cluster_id,
        project_id=project_id,
        title="Test Cluster",
        summary="Testing empty sources",
        feedback_ids=["feedback1"],
        status="new",
        created_at=now,
        updated_at=now,
        sources=[],
    )
    
    add_cluster(cluster)
    retrieved_cluster = get_cluster(project_id, cluster_id)
    
    assert retrieved_cluster is not None
    assert isinstance(retrieved_cluster.sources, list)
    assert retrieved_cluster.sources == []


def test_sources_none_value():
    """Test that None sources value is properly handled."""
    project_id = str(uuid4())
    cluster_id = str(uuid4())
    now = datetime.now(timezone.utc)
    
    cluster = IssueCluster(
        id=cluster_id,
        project_id=project_id,
        title="Test Cluster",
        summary="Testing None sources",
        feedback_ids=["feedback1"],
        status="new",
        created_at=now,
        updated_at=now,
        sources=None,
    )
    
    add_cluster(cluster)
    retrieved_cluster = get_cluster(project_id, cluster_id)
    
    assert retrieved_cluster is not None
    # None or empty list are both acceptable for None sources
    assert retrieved_cluster.sources is None or retrieved_cluster.sources == []
