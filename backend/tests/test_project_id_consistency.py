"""
Tests for project ID consistency between dashboard and backend.

This test suite prevents regressions related to project ID mismatches that cause
404 errors during GitHub sync and quota checks.

REGRESSION: Previously, the dashboard would create projects with CUID IDs in Prisma,
but sync to the backend with only the user_id. The backend would then generate a new
UUID for the project, causing a mismatch. When GitHub sync tried to use the session's
project_id (CUID), the backend couldn't find it and returned 404.

FIX: Dashboard now sends both project_id and user_id when syncing. Backend accepts
optional project_id and uses it if provided.
"""

from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from main import app
from models import Project, User
from store import (
    create_project,
    create_user_with_default_project,
    get_project,
    get_user_id_for_project,
)

client = TestClient(app)


def test_create_project_with_custom_id():
    """
    Test that POST /projects accepts and uses a custom project_id (CUID format).

    This prevents regression where backend would ignore the dashboard's project_id
    and generate its own UUID, causing ID mismatch.
    """
    # CUID format (like Prisma generates)
    custom_project_id = "cmjhgajxj00031uo0rf9ivdxb"
    user_id = "cmjhgaju000011uo0ups8xhky"

    response = client.post(
        "/projects",
        json={
            "project_id": custom_project_id,
            "user_id": user_id,
            "name": "Test Project",
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Backend MUST use the provided project_id, not generate a new one
    assert data["project"]["id"] == custom_project_id
    assert data["project"]["user_id"] == user_id
    assert data["project"]["name"] == "Test Project"


def test_create_project_without_custom_id_uses_user_id():
    """
    Test that POST /projects falls back to user_id when no project_id is provided.

    This maintains backward compatibility for old code that doesn't send project_id.
    """
    user_id = "cmjhgaju000011uo0ups8xhky"

    response = client.post(
        "/projects",
        json={
            "user_id": user_id,
            "name": "Test Project",
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Should fall back to using user_id as project_id
    assert data["project"]["id"] == user_id
    assert data["project"]["user_id"] == user_id


def test_get_project_by_cuid():
    """
    Test that get_project() works with CUID format IDs.

    This ensures the store can retrieve projects using CUID strings,
    not just UUID format.
    """
    # Create a project with CUID
    project_id = "cmjhgajxj00031uo0rf9ivdxb"
    user_id = "cmjhgaju000011uo0ups8xhky"
    now = datetime.now(timezone.utc)

    project = Project(
        id=project_id,
        user_id=user_id,
        name="Test Project",
        created_at=now,
    )
    create_project(project)

    # Retrieve using CUID string
    retrieved = get_project(project_id)

    assert retrieved is not None
    assert retrieved.id == project_id
    assert retrieved.user_id == user_id


def test_get_user_id_for_project_with_cuid():
    """
    Test that get_user_id_for_project() works with CUID format.

    This is critical for quota checks, which use this function to resolve
    the user_id from a project_id.
    """
    # Create a project with CUID
    project_id = "cmjhgajxj00031uo0rf9ivdxb"
    user_id = "cmjhgaju000011uo0ups8xhky"
    now = datetime.now(timezone.utc)

    project = Project(
        id=project_id,
        user_id=user_id,
        name="Test Project",
        created_at=now,
    )
    create_project(project)

    # This function is called by _check_feedback_quota
    resolved_user_id = get_user_id_for_project(project_id)

    assert resolved_user_id == user_id


def test_quota_check_with_cuid_project_id():
    """
    Test that quota checks work when project_id is a CUID.

    REGRESSION TEST: This was the root cause of the 404 error.
    When GitHub sync passed a CUID project_id, _check_feedback_quota()
    couldn't find the project and returned 404.
    """
    # Create user and project with CUID IDs
    project_id = "cmjhgajxj00031uo0rf9ivdxb"
    user_id = "cmjhgaju000011uo0ups8xhky"
    now = datetime.now(timezone.utc)

    user = User(
        id=user_id,
        email="test@example.com",
        github_id=None,
        created_at=now,
    )
    project = Project(
        id=project_id,
        user_id=user_id,
        name="Test Project",
        created_at=now,
    )
    create_user_with_default_project(user, project)

    # Try to ingest feedback with the CUID project_id
    # This internally calls _check_feedback_quota(project_id)
    response = client.post(
        "/ingest/manual",
        params={"project_id": project_id},
        json={"text": "Test feedback item"},
    )

    # Should succeed, not return 404
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["project_id"] == project_id


def test_github_sync_with_cuid_project_id(monkeypatch):
    """
    Test that GitHub sync works when project_id is a CUID.

    REGRESSION TEST: This was failing with 404 because the project
    was stored with user_id but session had project_id.
    """
    # Create user and project with CUID IDs
    project_id = "cmjhgajxj00031uo0rf9ivdxb"
    user_id = "cmjhgaju000011uo0ups8xhky"
    now = datetime.now(timezone.utc)

    user = User(
        id=user_id,
        email="test@example.com",
        github_id="test-github-user",
        created_at=now,
    )
    project = Project(
        id=project_id,
        user_id=user_id,
        name="Test Project",
        created_at=now,
    )
    create_user_with_default_project(user, project)

    # Mock the GitHub API call to return empty issues
    def mock_fetch_issues(*args, **kwargs):
        return []

    import main as backend_main
    monkeypatch.setattr(backend_main, "fetch_repo_issues", mock_fetch_issues)

    # Try GitHub sync with the CUID project_id
    response = client.post(
        "/ingest/github/sync/test-org/test-repo",
        params={"project_id": project_id},
        headers={"x-github-token": "fake-token"},
    )

    # Should succeed, not return 404
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_end_to_end_dashboard_backend_sync():
    """
    Test the complete flow: dashboard creates project, syncs to backend, then uses it.

    This simulates what happens when a user signs in:
    1. Dashboard creates project in Prisma (generates CUID)
    2. Dashboard calls POST /projects with project_id and user_id
    3. Dashboard later uses the project_id for operations
    4. Backend must find the project using that project_id
    """
    # Step 1: Dashboard creates project (simulated with CUID)
    dashboard_project_id = "cmjhgajxj00031uo0rf9ivdxb"
    dashboard_user_id = "cmjhgaju000011uo0ups8xhky"

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

    # Step 3: Verify backend stored it with the correct project_id
    stored_project = get_project(dashboard_project_id)
    assert stored_project is not None
    assert stored_project.id == dashboard_project_id
    assert stored_project.user_id == dashboard_user_id

    # Step 4: Dashboard uses project_id for operations (e.g., manual ingestion)
    ingest_response = client.post(
        "/ingest/manual",
        params={"project_id": dashboard_project_id},
        json={"text": "Test feedback"},
    )
    assert ingest_response.status_code == 200
    assert ingest_response.json()["project_id"] == dashboard_project_id

    # Step 5: Verify quota check can resolve user_id from project_id
    resolved_user_id = get_user_id_for_project(dashboard_project_id)
    assert resolved_user_id == dashboard_user_id


def test_project_id_mismatch_regression():
    """
    Test the exact scenario that caused the bug.

    SCENARIO:
    - Dashboard creates project with CUID: cmjhgajxj00031uo0rf9ivdxb
    - OLD BUG: Dashboard only sent user_id to backend
    - Backend generated new UUID, stored as project:{new_uuid}
    - Session had project_id: cmjhgajxj00031uo0rf9ivdxb
    - GitHub sync used session's project_id
    - Backend couldn't find project:{cmjhgajxj00031uo0rf9ivdxb} → 404

    With the fix, this should work because dashboard sends project_id.
    """
    # Different IDs (the bug scenario)
    session_project_id = "cmjhgajxj00031uo0rf9ivdxb"  # Prisma CUID
    user_id = "cmjhgaju000011uo0ups8xhky"             # User's CUID

    # OLD BUG: Only sent user_id
    # Backend would create Project(id=user_id, user_id=user_id)
    # Stored as project:cmjhgaju000011uo0ups8xhky
    # But session had project_id=cmjhgajxj00031uo0rf9ivdxb → MISMATCH!

    # NEW FIX: Send both project_id and user_id
    client.post(
        "/projects",
        json={
            "project_id": session_project_id,  # Send the Prisma project ID
            "user_id": user_id,
            "name": "Default Project",
        },
    )

    # Now backend should have stored it as project:cmjhgajxj00031uo0rf9ivdxb
    project = get_project(session_project_id)
    assert project is not None
    assert project.id == session_project_id  # MUST match session

    # Quota check should work with session's project_id
    resolved_user = get_user_id_for_project(session_project_id)
    assert resolved_user == user_id

    # GitHub sync should work with session's project_id
    response = client.post(
        "/ingest/manual",
        params={"project_id": session_project_id},
        json={"text": "Test"},
    )
    assert response.status_code == 200  # Not 404!
