from datetime import datetime, timezone
from uuid import UUID

import pytest

from backend.models import Project, User
from backend.store import (
    InMemoryStore,
    clear_clusters,
    clear_feedback_items,
    clear_jobs,
    create_user_with_default_project,
)

# Stable IDs for tests
DEFAULT_USER_ID = UUID("11111111-1111-1111-1111-111111111111")
DEFAULT_PROJECT_ID = UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture(scope="session", autouse=True)
def mock_store():
    """
    Force the use of InMemoryStore for all tests, ignoring Redis configuration.
    """
    memory_store = InMemoryStore()
    # Replace global store
    import backend.store as store_module

    store_module._STORE = memory_store
    yield memory_store


@pytest.fixture(autouse=True)
def clear_data(mock_store):
    """Clear project-scoped data between tests."""
    clear_jobs()
    clear_clusters()
    clear_feedback_items()


@pytest.fixture()
def project_context():
    """Create a user and default project for each test."""
    now = datetime.now(timezone.utc)
    user = User(id=DEFAULT_USER_ID, email="test@example.com", github_id=None, created_at=now)
    project = Project(id=DEFAULT_PROJECT_ID, user_id=user.id, name="My Project", created_at=now)
    create_user_with_default_project(user, project)
    return {"user_id": user.id, "project_id": project.id}
