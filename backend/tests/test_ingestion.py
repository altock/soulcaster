from fastapi.testclient import TestClient
from backend.main import app
from backend.store import (
    clear_feedback_items, 
    get_all_feedback_items, 
    clear_clusters, 
    get_all_clusters,
    get_unclustered_feedback,
    remove_from_unclustered
)

client = TestClient(app)

def setup_function():
    clear_feedback_items()
    clear_clusters()

def test_ingest_reddit(project_context):
    pid = project_context["project_id"]
    payload = {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "project_id": str(pid),
        "source": "reddit",
        "external_id": "t3_12345",
        "title": "Bug in the system",
        "body": "It crashes when I do X",
        "metadata": {"subreddit": "test"},
        "created_at": "2023-10-27T10:00:00Z"
    }
    response = client.post(f"/ingest/reddit?project_id={pid}", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    
    items = get_all_feedback_items()
    assert len(items) == 1
    assert items[0].title == "Bug in the system"
    assert items[0].source == "reddit"
    clusters = get_all_clusters()
    assert len(clusters) == 1
    assert clusters[0].title == "Reddit: r/test"


def test_ingest_reddit_deduplicates_external_ids(project_context):
    pid = project_context["project_id"]
    payload = {
        "id": "323e4567-e89b-12d3-a456-426614174000",
        "project_id": str(pid),
        "source": "reddit",
        "external_id": "t3_dupe",
        "title": "Original bug",
        "body": "Original body",
        "metadata": {"subreddit": "test"},
        "created_at": "2023-10-27T10:00:00Z"
    }
    first = client.post(f"/ingest/reddit?project_id={pid}", json=payload)
    assert first.status_code == 200

    dup_payload = payload | {
        "id": "423e4567-e89b-12d3-a456-426614174000",
        "title": "Duplicate bug title"
    }
    second = client.post(f"/ingest/reddit?project_id={pid}", json=dup_payload)
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"

    items = get_all_feedback_items()
    assert len(items) == 1
    assert items[0].title == "Original bug"

    clusters = get_all_clusters()
    assert len(clusters) == 1
    assert len(clusters[0].feedback_ids) == 1

def test_ingest_sentry(project_context):
    pid = project_context["project_id"]
    # Minimal Sentry webhook payload
    payload = {
        "event_id": "sentry_123",
        "project": "my-project",
        "message": "Something went wrong",
        "exception": {
            "values": [
                {
                    "type": "ValueError",
                    "value": "Invalid input",
                    "stacktrace": {
                        "frames": [
                            {"filename": "app.py", "lineno": 10}
                        ]
                    }
                }
            ]
        },
        "timestamp": 1698400800.0
    }
    response = client.post(f"/ingest/sentry?project_id={pid}", json=payload)
    assert response.status_code == 200
    
    items = get_all_feedback_items()
    assert len(items) == 1
    assert items[0].source == "sentry"
    assert items[0].external_id == "sentry_123"
    assert "ValueError: Invalid input" in items[0].body

def test_ingest_manual(project_context):
    pid = project_context["project_id"]
    payload = {
        "text": "The login button is broken on mobile."
    }
    response = client.post(f"/ingest/manual?project_id={pid}", json=payload)
    assert response.status_code == 200

    items = get_all_feedback_items()
    assert len(items) == 1
    assert items[0].source == "manual"
    assert items[0].title == "The login button is broken on mobile."
    assert items[0].body == "The login button is broken on mobile."

def test_ingest_manual_long_text(project_context):
    """Test that long text is properly truncated in title."""
    pid = project_context["project_id"]
    long_text = "A" * 200
    payload = {"text": long_text}
    response = client.post(f"/ingest/manual?project_id={pid}", json=payload)
    assert response.status_code == 200

    items = get_all_feedback_items()
    assert len(items) == 1
    assert items[0].title == long_text[:80]
    assert items[0].body == long_text

def test_ingest_sentry_minimal_payload(project_context):
    """Test Sentry ingestion with minimal payload (no exception data)."""
    pid = project_context["project_id"]
    payload = {
        "event_id": "sentry_minimal",
        "message": "Minimal error"
    }
    response = client.post(f"/ingest/sentry?project_id={pid}", json=payload)
    assert response.status_code == 200

    items = get_all_feedback_items()
    assert len(items) == 1
    assert items[0].source == "sentry"
    assert items[0].title == "Minimal error"
    assert items[0].external_id == "sentry_minimal"

def test_ingest_reddit_with_empty_body(project_context):
    """Test Reddit post with no body text."""
    pid = project_context["project_id"]
    payload = {
        "id": "223e4567-e89b-12d3-a456-426614174000",
        "project_id": str(pid),
        "source": "reddit",
        "external_id": "t3_empty",
        "title": "Bug report",
        "body": "",
        "metadata": {},
        "created_at": "2023-10-27T10:00:00Z"
    }
    response = client.post(f"/ingest/reddit?project_id={pid}", json=payload)
    assert response.status_code == 200

    items = get_all_feedback_items()
    assert len(items) == 1
    assert items[0].body == ""


# ========== Phase 1: Ingestion Moat - Unclustered Feedback Tests ==========

def test_add_feedback_writes_to_unclustered(project_context):
    """Phase 1: Verify feedback lands in unclustered set when ingested."""
    pid = project_context["project_id"]
    payload = {
        "id": "999e4567-e89b-12d3-a456-426614174000",
        "project_id": str(pid),
        "source": "reddit",
        "external_id": "t3_unclustered_test",
        "title": "Test unclustered",
        "body": "This should go to unclustered set",
        "metadata": {"subreddit": "test"},
        "created_at": "2023-10-27T10:00:00Z"
    }
    response = client.post(f"/ingest/reddit?project_id={pid}", json=payload)
    assert response.status_code == 200
    
    # Check feedback was created
    items = get_all_feedback_items()
    assert len(items) >= 1
    
    # KEY TEST: Check it's in the unclustered set
    unclustered = get_unclustered_feedback(pid)
    assert len(unclustered) >= 1
    
    # Verify the specific item is in unclustered (use the ID from payload)
    unclustered_ids = [str(item.id) for item in unclustered]
    expected_id = payload["id"]
    assert expected_id in unclustered_ids, f"Item {expected_id} not found in unclustered set. Found: {unclustered_ids}"


def test_all_sources_add_to_unclustered(project_context):
    """Phase 1: Verify all ingest sources add to unclustered set."""
    pid = project_context["project_id"]
    # Test Reddit
    reddit_payload = {
        "id": "a00e4567-e89b-12d3-a456-426614174000",
        "project_id": str(pid),
        "source": "reddit",
        "external_id": "t3_multi_test_1",
        "title": "Reddit bug",
        "body": "Reddit body",
        "metadata": {},
        "created_at": "2023-10-27T10:00:00Z"
    }
    client.post(f"/ingest/reddit?project_id={pid}", json=reddit_payload)
    
    # Test Sentry
    sentry_payload = {
        "event_id": "sentry_multi_test",
        "message": "Sentry error",
        "exception": {
            "values": [{
                "type": "Error",
                "value": "Test error"
            }]
        }
    }
    client.post(f"/ingest/sentry?project_id={pid}", json=sentry_payload)
    
    # Test Manual
    manual_payload = {"text": "Manual feedback test"}
    client.post(f"/ingest/manual?project_id={pid}", json=manual_payload)
    
    # Check all are in unclustered
    unclustered = get_unclustered_feedback(pid)
    assert len(unclustered) >= 3, f"Expected at least 3 unclustered items, got {len(unclustered)}"
    
    sources = {item.source for item in unclustered}
    assert "reddit" in sources
    assert "sentry" in sources
    assert "manual" in sources


def test_remove_from_unclustered(project_context):
    """Phase 1: Verify items can be removed from unclustered set."""
    pid = project_context["project_id"]
    payload = {
        "id": "b00e4567-e89b-12d3-a456-426614174000",
        "project_id": str(pid),
        "source": "reddit",
        "external_id": "t3_remove_test",
        "title": "Remove test",
        "body": "Test removal",
        "metadata": {},
        "created_at": "2023-10-27T10:00:00Z"
    }
    response = client.post(f"/ingest/reddit?project_id={pid}", json=payload)
    assert response.status_code == 200
    
    items = get_all_feedback_items()
    test_item = next((item for item in items if item.external_id == "t3_remove_test"), None)
    assert test_item is not None
    
    # Verify it's in unclustered
    unclustered_before = get_unclustered_feedback(pid)
    assert any(item.id == test_item.id for item in unclustered_before)
    
    # Remove from unclustered
    remove_from_unclustered(test_item.id, pid)
    
    # Verify it's no longer in unclustered
    unclustered_after = get_unclustered_feedback(pid)
    assert not any(item.id == test_item.id for item in unclustered_after), \
        f"Item {test_item.id} still in unclustered after removal"


def test_get_unclustered_feedback_empty(project_context):
    """Phase 1: Verify get_unclustered_feedback returns empty list when no items."""
    pid = project_context["project_id"]
    clear_feedback_items()
    unclustered = get_unclustered_feedback(pid)
    assert unclustered == [], "Expected empty list for unclustered feedback"


def test_duplicate_ingestion_does_not_duplicate_unclustered(project_context):
    """Phase 1: Verify duplicate external_id doesn't add multiple unclustered entries."""
    pid = project_context["project_id"]
    payload = {
        "id": "c00e4567-e89b-12d3-a456-426614174000",
        "project_id": str(pid),
        "source": "reddit",
        "external_id": "t3_duplicate_unclustered",
        "title": "Original",
        "body": "Original body",
        "metadata": {},
        "created_at": "2023-10-27T10:00:00Z"
    }
    
    # First ingestion
    first = client.post(f"/ingest/reddit?project_id={pid}", json=payload)
    assert first.status_code == 200
    
    unclustered_after_first = get_unclustered_feedback(pid)
    count_after_first = len(unclustered_after_first)
    
    # Second ingestion (duplicate)
    duplicate_payload = payload | {"id": "d00e4567-e89b-12d3-a456-426614174000"}
    second = client.post(f"/ingest/reddit?project_id={pid}", json=duplicate_payload)
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"
    
    unclustered_after_second = get_unclustered_feedback(pid)
    count_after_second = len(unclustered_after_second)
    
    assert count_after_second == count_after_first, \
        "Duplicate ingestion should not add to unclustered set"
