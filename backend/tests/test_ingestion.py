from fastapi.testclient import TestClient
from backend.main import app
from backend.store import clear_feedback_items, get_all_feedback_items, clear_clusters, get_all_clusters

client = TestClient(app)

def setup_function():
    clear_feedback_items()
    clear_clusters()

def test_ingest_reddit():
    payload = {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "source": "reddit",
        "external_id": "t3_12345",
        "title": "Bug in the system",
        "body": "It crashes when I do X",
        "metadata": {"subreddit": "test"},
        "created_at": "2023-10-27T10:00:00Z"
    }
    response = client.post("/ingest/reddit", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    
    items = get_all_feedback_items()
    assert len(items) == 1
    assert items[0].title == "Bug in the system"
    assert items[0].source == "reddit"
    clusters = get_all_clusters()
    assert len(clusters) == 1
    assert clusters[0].title == "Reddit: r/test"


def test_ingest_reddit_deduplicates_external_ids():
    payload = {
        "id": "323e4567-e89b-12d3-a456-426614174000",
        "source": "reddit",
        "external_id": "t3_dupe",
        "title": "Original bug",
        "body": "Original body",
        "metadata": {"subreddit": "test"},
        "created_at": "2023-10-27T10:00:00Z"
    }
    first = client.post("/ingest/reddit", json=payload)
    assert first.status_code == 200

    dup_payload = payload | {
        "id": "423e4567-e89b-12d3-a456-426614174000",
        "title": "Duplicate bug title"
    }
    second = client.post("/ingest/reddit", json=dup_payload)
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"

    items = get_all_feedback_items()
    assert len(items) == 1
    assert items[0].title == "Original bug"

    clusters = get_all_clusters()
    assert len(clusters) == 1
    assert len(clusters[0].feedback_ids) == 1

def test_ingest_sentry():
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
    response = client.post("/ingest/sentry", json=payload)
    assert response.status_code == 200
    
    items = get_all_feedback_items()
    assert len(items) == 1
    assert items[0].source == "sentry"
    assert items[0].external_id == "sentry_123"
    assert "ValueError: Invalid input" in items[0].body

def test_ingest_manual():
    payload = {
        "text": "The login button is broken on mobile."
    }
    response = client.post("/ingest/manual", json=payload)
    assert response.status_code == 200

    items = get_all_feedback_items()
    assert len(items) == 1
    assert items[0].source == "manual"
    assert items[0].title == "The login button is broken on mobile."
    assert items[0].body == "The login button is broken on mobile."

def test_ingest_manual_long_text():
    """Test that long text is properly truncated in title."""
    long_text = "A" * 200
    payload = {"text": long_text}
    response = client.post("/ingest/manual", json=payload)
    assert response.status_code == 200

    items = get_all_feedback_items()
    assert len(items) == 1
    assert items[0].title == long_text[:80]
    assert items[0].body == long_text

def test_ingest_sentry_minimal_payload():
    """Test Sentry ingestion with minimal payload (no exception data)."""
    payload = {
        "event_id": "sentry_minimal",
        "message": "Minimal error"
    }
    response = client.post("/ingest/sentry", json=payload)
    assert response.status_code == 200

    items = get_all_feedback_items()
    assert len(items) == 1
    assert items[0].source == "sentry"
    assert items[0].title == "Minimal error"
    assert items[0].external_id == "sentry_minimal"

def test_ingest_reddit_with_empty_body():
    """Test Reddit post with no body text."""
    payload = {
        "id": "223e4567-e89b-12d3-a456-426614174000",
        "source": "reddit",
        "external_id": "t3_empty",
        "title": "Bug report",
        "body": "",
        "metadata": {},
        "created_at": "2023-10-27T10:00:00Z"
    }
    response = client.post("/ingest/reddit", json=payload)
    assert response.status_code == 200

    items = get_all_feedback_items()
    assert len(items) == 1
    assert items[0].body == ""
