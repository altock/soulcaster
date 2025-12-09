from fastapi.testclient import TestClient

from backend import main as backend_main
from backend.github_client import issue_to_feedback_item
from backend.main import app
from backend.store import (
    get_all_feedback_items,
    get_unclustered_feedback,
)

client = TestClient(app)


def setup_function():
    # Reset in-memory sync metadata between tests
    backend_main.GITHUB_SYNC_STATE.clear()


def test_issue_to_feedback_item_shape(project_context):
    pid = project_context["project_id"]
    issue = {
        "id": 123,
        "number": 42,
        "title": "Sample issue",
        "body": "Issue body",
        "state": "open",
        "html_url": "https://github.com/org/repo/issues/42",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
        "labels": [{"name": "bug"}],
        "user": {"login": "octocat"},
        "assignees": [{"login": "helper"}],
        "milestone": {"title": "v1"},
    }

    item = issue_to_feedback_item(issue, "org/repo", pid)
    assert item.source == "github"
    assert item.repo == "org/repo"
    assert item.github_issue_number == 42
    assert item.github_issue_url.endswith("/42")
    assert item.metadata["labels"] == ["bug"]
    assert item.metadata["author"] == "octocat"
    assert item.status == "open"


def test_sync_github_repo_first_sync(project_context, monkeypatch):
    pid = project_context["project_id"]

    issue_open = {
        "id": 1,
        "number": 10,
        "title": "Open issue",
        "body": "Needs fixing",
        "state": "open",
        "html_url": "https://github.com/org/repo/issues/10",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
        "labels": [],
        "user": {"login": "alice"},
        "assignees": [],
    }
    issue_closed = issue_open | {
        "id": 2,
        "number": 11,
        "title": "Closed issue",
        "state": "closed",
        "html_url": "https://github.com/org/repo/issues/11",
    }

    monkeypatch.setattr(
        "backend.main.fetch_repo_issues",
        lambda owner, repo, since=None: [issue_open, issue_closed],
    )

    resp = client.post(f"/ingest/github/sync/org/repo?project_id={pid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["new_issues"] == 2
    assert data["closed_issues"] == 1

    # Ensure feedback stored
    items = get_all_feedback_items()
    assert len(items) == 2

    # Closed issue should not remain in unclustered
    unclustered = get_unclustered_feedback(pid)
    assert len(unclustered) == 1
    assert unclustered[0].title == "Open issue"


def test_sync_github_repo_incremental(project_context, monkeypatch):
    pid = project_context["project_id"]
    calls = {"first_since": None, "second_since": None}

    issue_open = {
        "id": 3,
        "number": 12,
        "title": "First sync issue",
        "body": "First body",
        "state": "open",
        "html_url": "https://github.com/org/repo/issues/12",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
        "labels": [],
        "user": {"login": "alice"},
        "assignees": [],
    }

    def first_fetch(owner, repo, since=None):
        calls["first_since"] = since
        return [issue_open]

    def second_fetch(owner, repo, since=None):
        calls["second_since"] = since
        return []

    monkeypatch.setattr("backend.main.fetch_repo_issues", first_fetch)
    first_resp = client.post(f"/ingest/github/sync/org/repo?project_id={pid}")
    assert first_resp.status_code == 200

    monkeypatch.setattr("backend.main.fetch_repo_issues", second_fetch)
    second_resp = client.post(f"/ingest/github/sync/org/repo?project_id={pid}")
    assert second_resp.status_code == 200

    assert calls["first_since"] is None
    assert calls["second_since"] is not None
