"""Tests for feedback retrieval API endpoints."""

from uuid import uuid4
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from main import app
from store import clear_feedback_items, add_feedback_item, clear_clusters
from models import FeedbackItem

client = TestClient(app)


def setup_function():
    """
    Clear in-memory stores used by tests.
    
    Removes all feedback items and clusters so each test starts with an empty store.
    """
    clear_feedback_items()
    clear_clusters()


def test_get_feedback_empty(project_context):
    """Test GET /feedback with no items."""
    pid = project_context["project_id"]
    response = client.get(f"/feedback?project_id={pid}")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_get_feedback_with_items(project_context):
    """Test GET /feedback returns all items."""
    pid = project_context["project_id"]
    # Add test feedback items
    item1 = FeedbackItem(
        id=uuid4(),
        project_id=pid,
        source="reddit",
        external_id="r1",
        title="Bug in feature A",
        body="Details about bug A",
        metadata={"subreddit": "test"},
        created_at=datetime.now(timezone.utc)
    )
    item2 = FeedbackItem(
        id=uuid4(),
        project_id=pid,
        source="sentry",
        external_id="s1",
        title="Error in production",
        body="Stack trace here",
        metadata={},
        created_at=datetime.now(timezone.utc)
    )
    add_feedback_item(item1)
    add_feedback_item(item2)

    response = client.get(f"/feedback?project_id={pid}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_get_feedback_filter_by_source(project_context):
    """Test GET /feedback with source filter."""
    pid = project_context["project_id"]
    # Add items from different sources
    reddit_item = FeedbackItem(
        id=uuid4(),
        project_id=pid,
        source="reddit",
        title="Reddit bug",
        body="Bug from reddit",
        metadata={},
        created_at=datetime.now(timezone.utc)
    )
    sentry_item = FeedbackItem(
        id=uuid4(),
        project_id=pid,
        source="sentry",
        title="Sentry error",
        body="Error from sentry",
        metadata={},
        created_at=datetime.now(timezone.utc)
    )
    add_feedback_item(reddit_item)
    add_feedback_item(sentry_item)

    # Filter by reddit
    response = client.get(f"/feedback?source=reddit&project_id={pid}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["source"] == "reddit"


def test_get_feedback_pagination(project_context):
    """Test GET /feedback with limit and offset."""
    pid = project_context["project_id"]
    # Add 5 items
    for i in range(5):
        item = FeedbackItem(
            id=uuid4(),
            project_id=pid,
            source="manual",
            title=f"Item {i}",
            body=f"Body {i}",
            metadata={},
            created_at=datetime.now(timezone.utc)
        )
        add_feedback_item(item)

    # Get first 2 items
    response = client.get(f"/feedback?limit=2&offset=0&project_id={pid}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5

    # Get next 2 items
    response = client.get(f"/feedback?limit=2&offset=2&project_id={pid}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2


def test_get_feedback_by_id(project_context):
    """Test GET /feedback/{id} returns specific item."""
    pid = project_context["project_id"]
    item = FeedbackItem(
        id=uuid4(),
        project_id=pid,
        source="manual",
        title="Test item",
        body="Test body",
        metadata={"key": "value"},
        created_at=datetime.now(timezone.utc)
    )
    add_feedback_item(item)

    response = client.get(f"/feedback/{item.id}?project_id={pid}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(item.id)
    assert data["title"] == "Test item"
    assert data["metadata"]["key"] == "value"


def test_get_feedback_by_id_not_found(project_context):
    """
    Verify that requesting a feedback item by a nonexistent ID returns a 404 response and a detail message containing "not found".
    """
    pid = project_context["project_id"]
    fake_id = uuid4()
    response = client.get(f"/feedback/{fake_id}?project_id={pid}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_stats(project_context):
    """Test GET /stats returns summary statistics."""
    pid = project_context["project_id"]
    # Add items from different sources
    add_feedback_item(FeedbackItem(
        id=uuid4(), project_id=pid, source="reddit", title="R1", body="B1",
        metadata={}, created_at=datetime.now(timezone.utc)
    ))
    add_feedback_item(FeedbackItem(
        id=uuid4(), project_id=pid, source="reddit", title="R2", body="B2",
        metadata={}, created_at=datetime.now(timezone.utc)
    ))
    add_feedback_item(FeedbackItem(
        id=uuid4(), project_id=pid, source="sentry", title="S1", body="B3",
        metadata={}, created_at=datetime.now(timezone.utc)
    ))
    add_feedback_item(FeedbackItem(
        id=uuid4(), project_id=pid, source="manual", title="M1", body="B4",
        metadata={}, created_at=datetime.now(timezone.utc)
    ))

    response = client.get(f"/stats?project_id={pid}")
    assert response.status_code == 200
    data = response.json()
    assert data["total_feedback"] == 4
    assert data["by_source"]["reddit"] == 2
    assert data["by_source"]["sentry"] == 1
    assert data["by_source"]["manual"] == 1
    assert data["total_clusters"] == 0  # Placeholder for future


def test_get_feedback_with_cuid_project():
    """Ensure /feedback accepts CUID project_id without 422."""
    cuid = "cmiy0tdxz00022mo0aa3ywqsx"
    item = FeedbackItem(
        id=uuid4(),
        project_id=cuid,
        source="github",
        external_id="ext-cuid-1",
        title="CUID item",
        body="Body",
        metadata={},
        created_at=datetime.now(timezone.utc),
    )
    add_feedback_item(item)

    response = client.get(f"/feedback?project_id={cuid}")
    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == cuid
    assert data["total"] == 1
    assert data["items"][0]["project_id"] == cuid


def test_get_stats_with_cuid_project():
    """Ensure /stats accepts CUID project_id without 422."""
    cuid = "cmiy0tdxz00022mo0bb4zxrty"
    add_feedback_item(
        FeedbackItem(
            id=uuid4(),
            project_id=cuid,
            source="manual",
            external_id="ext-cuid-2",
            title="CUID stats",
            body="Body",
            metadata={},
            created_at=datetime.now(timezone.utc),
        )
    )

    response = client.get(f"/stats?project_id={cuid}")
    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == cuid
    assert data["total_feedback"] == 1