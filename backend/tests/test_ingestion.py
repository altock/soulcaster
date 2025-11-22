from fastapi.testclient import TestClient
from backend.main import app
from backend.store import clear_feedback_items, get_all_feedback_items

client = TestClient(app)

def setup_function():
    clear_feedback_items()

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
