import os

from fastapi.testclient import TestClient

from backend.main import app
from backend.store import clear_config

client = TestClient(app)


def setup_function():
    """
    Prepare the test environment by clearing persisted configuration and removing Reddit-related environment variables.
    
    Clears any stored configuration via clear_config() and removes the environment variables
    REDDIT_SUBREDDITS and REDDIT_SUBREDDIT so tests run with a clean, deterministic state.
    """
    clear_config()
    for key in ("REDDIT_SUBREDDITS", "REDDIT_SUBREDDIT"):
        os.environ.pop(key, None)


def test_get_config_uses_env_when_no_store(project_context):
    pid = project_context["project_id"]
    os.environ["REDDIT_SUBREDDITS"] = "Foo, Bar"

    response = client.get(f"/config/reddit/subreddits?project_id={pid}")

    assert response.status_code == 200
    assert response.json()["subreddits"] == ["foo", "bar"]


def test_set_config_persists_and_dedupes(project_context):
    """
    Verifies that posting subreddit configuration persists a normalized, deduplicated list and that subsequent reads return the stored value.
    
    Posts a list containing whitespace and duplicate entries, asserts the response contains trimmed, lowercased, deduplicated subreddits in preserved order, then sets the REDDIT_SUBREDDITS environment variable to confirm the GET endpoint returns the value from the store rather than from the environment.
    
    Parameters:
        project_context (dict): Test fixture providing `project_id` used as the `project_id` query parameter.
    """
    pid = project_context["project_id"]
    response = client.post(
        f"/config/reddit/subreddits?project_id={pid}",
        json={"subreddits": [" Test ", "test", "other"]},
    )

    assert response.status_code == 200
    assert response.json()["subreddits"] == ["test", "other"]

    # Should read back from store, not env
    os.environ["REDDIT_SUBREDDITS"] = "ignored"
    read_back = client.get(f"/config/reddit/subreddits?project_id={pid}")
    assert read_back.json()["subreddits"] == ["test", "other"]


def test_set_config_requires_non_empty_list(project_context):
    pid = project_context["project_id"]
    response = client.post(
        f"/config/reddit/subreddits?project_id={pid}",
        json={"subreddits": [" ", ""]},
    )
    assert response.status_code == 400