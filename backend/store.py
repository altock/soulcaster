"""In-memory storage for FeedbackItems and IssueClusters.

This module provides a simple in-memory store for the MVP.
In production, this would be replaced with a database (Supabase/Postgres).
"""

from typing import Dict, List
from uuid import UUID
from .models import FeedbackItem, IssueCluster

# In-memory storage for feedback items, keyed by UUID
feedback_items: Dict[UUID, FeedbackItem] = {}
issue_clusters: Dict[UUID, IssueCluster] = {}


def add_feedback_item(item: FeedbackItem) -> FeedbackItem:
    """
    Store a feedback item in memory.

    Args:
        item: The FeedbackItem to store

    Returns:
        The stored FeedbackItem
    """
    feedback_items[item.id] = item
    return item


def get_feedback_item(item_id: UUID) -> FeedbackItem | None:
    """
    Retrieve a feedback item by its ID.

    Args:
        item_id: UUID of the feedback item to retrieve

    Returns:
        The FeedbackItem if found, None otherwise
    """
    return feedback_items.get(item_id)


def get_all_feedback_items() -> List[FeedbackItem]:
    """
    Retrieve all stored feedback items.

    Returns:
        List of all FeedbackItems in the store
    """
    return list(feedback_items.values())


def clear_feedback_items():
    """Clear all feedback items from the store. Used primarily for testing."""
    feedback_items.clear()


def add_cluster(cluster: IssueCluster) -> IssueCluster:
    """Store an issue cluster in memory."""

    issue_clusters[cluster.id] = cluster
    return cluster


def get_cluster(cluster_id: UUID) -> IssueCluster | None:
    """Retrieve a cluster by its ID."""

    return issue_clusters.get(cluster_id)


def get_all_clusters() -> List[IssueCluster]:
    """Retrieve all stored clusters."""

    return list(issue_clusters.values())


def update_cluster(cluster_id: UUID, **updates) -> IssueCluster:
    """Update and return a cluster with the given fields."""

    cluster = issue_clusters[cluster_id]
    updated_cluster = cluster.model_copy(update=updates)
    issue_clusters[cluster_id] = updated_cluster
    return updated_cluster


def clear_clusters():
    """Clear all clusters from the store. Used primarily for testing."""

    issue_clusters.clear()
