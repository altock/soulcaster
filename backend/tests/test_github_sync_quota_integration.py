"""
Integration tests for GitHub sync with quota checks and CUID project IDs.

This test suite ensures that GitHub sync works correctly with:
1. CUID format project IDs (from Prisma)
2. Quota checks that need to resolve user_id from project_id
3. End-to-end flow from project creation to GitHub ingestion

REGRESSION PREVENTION: Tests the exact bug where GitHub sync returned 404
because quota checks couldn't find the project with a CUID project_id.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import main as backend_main
from main import app
from models import FeedbackItem, Project, User
from store import (
    add_feedback_item,
    count_feedback_items_for_user,
    create_user_with_default_project,
    get_all_feedback_items,
)

client = TestClient(app)


def setup_function():
    """Reset GitHub sync state between tests."""
    backend_main.GITHUB_SYNC_STATE.clear()


@pytest.fixture
def cuid_project():
    """Create a project with CUID IDs (simulating Prisma dashboard)."""
    project_id = "cmjhgajxj00031uo0rf9ivdxb"
    user_id = "cmjhgaju000011uo0ups8xhky"
    now = datetime.now(timezone.utc)

    user = User(
        id=user_id,
        email="test@example.com",
        github_id="test-user",
        created_at=now,
    )
    project = Project(
        id=project_id,
        user_id=user_id,
        name="Test Project",
        created_at=now,
    )
    create_user_with_default_project(user, project)

    return {"project_id": project_id, "user_id": user_id}


def test_github_sync_with_cuid_finds_project(cuid_project, monkeypatch):
    """
    Test that GitHub sync can find a project created with CUID.

    REGRESSION: GitHub sync was failing with 404 because quota check
    couldn't find project when using CUID project_id.
    """
    project_id = cuid_project["project_id"]

    # Mock GitHub API to return sample issues
    def mock_fetch_issues(owner, repo, since=None, token=None, **kwargs):
        return [
            {
                "id": 123,
                "number": 1,
                "title": "Test Issue",
                "body": "Test body",
                "state": "open",
                "html_url": f"https://github.com/test/repo/issues/1",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "labels": [],
                "user": {"login": "testuser"},
                "assignees": [],
                "milestone": None,
            }
        ]

    import main as backend_main
    monkeypatch.setattr(backend_main, "fetch_repo_issues", mock_fetch_issues)

    # Perform GitHub sync with CUID project_id
    response = client.post(
        "/ingest/github/sync/test/repo",
        params={"project_id": project_id},
        headers={"x-github-token": "test-token"},
    )

    # Should succeed, not 404
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["new_issues"] == 1


def test_quota_check_during_github_sync(cuid_project, monkeypatch):
    """
    Test that quota checks work during GitHub sync with CUID project_id.

    This verifies that _check_feedback_quota() can resolve the user_id
    from a CUID project_id.
    """
    project_id = cuid_project["project_id"]
    user_id = cuid_project["user_id"]

    # Mock GitHub API to return multiple issues
    def mock_fetch_issues(owner, repo, since=None, token=None, **kwargs):
        return [
            {
                "id": i,
                "number": i,
                "title": f"Issue {i}",
                "body": f"Body {i}",
                "state": "open",
                "html_url": f"https://github.com/test/repo/issues/{i}",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "labels": [],
                "user": {"login": "testuser"},
                "assignees": [],
                "milestone": None,
            }
            for i in range(1, 6)  # 5 issues
        ]

    import main as backend_main
    monkeypatch.setattr(backend_main, "fetch_repo_issues", mock_fetch_issues)

    # Sync should succeed and quota check should work
    response = client.post(
        "/ingest/github/sync/test/repo",
        params={"project_id": project_id},
        headers={"x-github-token": "test-token"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["new_issues"] == 5

    # Verify quota was checked correctly
    count = count_feedback_items_for_user(user_id)
    assert count == 5


def test_quota_limit_with_cuid_project_id(cuid_project, monkeypatch):
    """
    Test that quota limits are enforced with CUID project_id.

    This ensures that when a user hits their quota, the error is returned
    correctly (not 404 from failing to find the project).
    """
    project_id = cuid_project["project_id"]
    user_id = cuid_project["user_id"]

    # Add feedback items to hit quota (1500 limit)
    now = datetime.now(timezone.utc)
    for i in range(1500):
        item = FeedbackItem(
            id=str(uuid4()),
            project_id=project_id,
            source="manual",
            title=f"Item {i}",
            body=f"Body {i}",
            metadata={},
            created_at=now,
        )
        add_feedback_item(item)

    # Try to add one more (should hit quota)
    response = client.post(
        "/ingest/manual",
        params={"project_id": project_id},
        json={"text": "Over quota"},
    )

    # Should return 429 (quota exceeded), not 404 (project not found)
    assert response.status_code == 429
    data = response.json()
    detail = data["detail"] if isinstance(data["detail"], str) else str(data["detail"])
    assert "quota" in detail.lower()


def test_partial_batch_with_quota_and_cuid(cuid_project, monkeypatch):
    """
    Test that GitHub sync handles partial batches correctly when hitting quota.

    When quota allows only some items from a batch, the sync should:
    1. Add the allowed items
    2. Return success with partial ingestion count
    3. Not return 404 from project lookup
    """
    project_id = cuid_project["project_id"]
    user_id = cuid_project["user_id"]

    # Add items up to near quota limit (allow 5 more)
    now = datetime.now(timezone.utc)
    for i in range(1495):
        item = FeedbackItem(
            id=str(uuid4()),
            project_id=project_id,
            source="manual",
            title=f"Item {i}",
            body=f"Body {i}",
            metadata={},
            created_at=now,
        )
        add_feedback_item(item)

    # Mock GitHub API to return 10 issues (but only 5 should be ingested)
    def mock_fetch_issues(owner, repo, since=None, token=None, **kwargs):
        return [
            {
                "id": i,
                "number": i,
                "title": f"Issue {i}",
                "body": f"Body {i}",
                "state": "open",
                "html_url": f"https://github.com/test/repo/issues/{i}",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "labels": [],
                "user": {"login": "testuser"},
                "assignees": [],
                "milestone": None,
            }
            for i in range(1, 11)  # 10 issues
        ]

    import main as backend_main
    monkeypatch.setattr(backend_main, "fetch_repo_issues", mock_fetch_issues)

    # Sync should succeed with partial ingestion
    response = client.post(
        "/ingest/github/sync/test/repo",
        params={"project_id": project_id},
        headers={"x-github-token": "test-token"},
    )

    assert response.status_code == 200
    data = response.json()
    # Should only ingest 5 items (hitting the 1500 quota)
    assert data["new_issues"] == 5
    assert "total_issues" in data
    assert data["total_issues"] == 10

    # Verify total count is at quota
    count = count_feedback_items_for_user(user_id)
    assert count == 1500


def test_multiple_syncs_with_same_cuid_project(cuid_project, monkeypatch):
    """
    Test that multiple GitHub syncs work with the same CUID project_id.

    This ensures that the project lookup is consistent across multiple
    operations.
    """
    project_id = cuid_project["project_id"]

    call_count = [0]

    def mock_fetch_issues(owner, repo, since=None, token=None, **kwargs):
        call_count[0] += 1
        return [
            {
                "id": 100 + call_count[0],
                "number": call_count[0],
                "title": f"Issue {call_count[0]}",
                "body": f"Body {call_count[0]}",
                "state": "open",
                "html_url": f"https://github.com/test/repo/issues/{call_count[0]}",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "labels": [],
                "user": {"login": "testuser"},
                "assignees": [],
                "milestone": None,
            }
        ]

    import main as backend_main
    monkeypatch.setattr(backend_main, "fetch_repo_issues", mock_fetch_issues)

    # First sync
    response1 = client.post(
        "/ingest/github/sync/test/repo",
        params={"project_id": project_id},
        headers={"x-github-token": "test-token"},
    )
    assert response1.status_code == 200

    # Second sync
    response2 = client.post(
        "/ingest/github/sync/test/repo",
        params={"project_id": project_id},
        headers={"x-github-token": "test-token"},
    )
    assert response2.status_code == 200

    # Both should succeed with project lookup
    all_items = get_all_feedback_items()
    assert len(all_items) == 2  # Should have ingested 2 items total


def test_dashboard_to_github_sync_full_flow():
    """
    End-to-end test simulating the complete dashboard flow.

    This is the EXACT scenario that was failing:
    1. User signs in, dashboard creates user and project in Prisma
    2. Dashboard syncs project to backend via POST /projects
    3. User adds GitHub integration
    4. User clicks "Sync Now"
    5. Dashboard calls GitHub sync endpoint with session's project_id
    6. Backend performs quota check and ingests issues

    All of this must work without 404 errors.
    """
    # Step 1: Dashboard creates user and project (Prisma generates CUIDs)
    dashboard_user_id = "cmjhgaju000011uo0ups8xhky"
    dashboard_project_id = "cmjhgajxj00031uo0rf9ivdxb"

    # Step 2: Dashboard syncs to backend
    sync_response = client.post(
        "/projects",
        json={
            "project_id": dashboard_project_id,
            "user_id": dashboard_user_id,
            "name": "Default Project",
        },
    )
    assert sync_response.status_code == 200
    assert sync_response.json()["project"]["id"] == dashboard_project_id

    # Step 3 & 4: User adds GitHub integration and clicks sync
    # Dashboard uses session's project_id for the sync request

    # Mock GitHub API
    def mock_fetch_issues(owner, repo, since=None, token=None, **kwargs):
        return [
            {
                "id": 123,
                "number": 1,
                "title": "Bug in login",
                "body": "Users can't log in",
                "state": "open",
                "html_url": "https://github.com/myorg/myrepo/issues/1",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "labels": [{"name": "bug"}],
                "user": {"login": "user1"},
                "assignees": [],
                "milestone": None,
            }
        ]

    import main as backend_main
    import pytest
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(backend_main, "fetch_repo_issues", mock_fetch_issues)

    # Step 5 & 6: GitHub sync with session's project_id
    github_response = client.post(
        "/ingest/github/sync/myorg/myrepo",
        params={"project_id": dashboard_project_id},  # Session's project_id
        headers={"x-github-token": "ghp_test_token"},
    )

    # CRITICAL: Must succeed, not return 404
    assert github_response.status_code == 200
    data = github_response.json()
    assert data["success"] is True
    assert data["new_issues"] == 1

    # Verify the issue was ingested with correct project_id
    all_items = get_all_feedback_items()
    assert len(all_items) == 1
    assert all_items[0].project_id == dashboard_project_id

    monkeypatch.undo()
