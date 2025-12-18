from datetime import datetime, timezone
from uuid import UUID

import pytest

from models import Project, User
from store import (
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
    import store as store_module

    store_module._STORE = memory_store
    yield memory_store


@pytest.fixture(autouse=True)
def clear_data(mock_store):
    """
    Clear test data at project scope so each test starts with a clean in-memory store.
    
    Removes all jobs, clusters, and feedback items.
    """
    clear_jobs()
    clear_clusters()
    clear_feedback_items()
    from store import clear_coding_plans
    clear_coding_plans()


@pytest.fixture
def anyio_backend():
    """
    Select the AnyIO backend used by tests.
    
    Returns:
        str: The name of the AnyIO backend to use, `"asyncio"`.
    """
    return "asyncio"


@pytest.fixture()
def project_context():
    """
    Create and register a default test user and project, then return their identifiers.
    
    The created user and project are timestamped with the current UTC time and persisted via the store helper.
    
    Returns:
        dict: A mapping with keys "user_id" and "project_id" containing the created UUIDs.
    """
    now = datetime.now(timezone.utc)
    user = User(id=DEFAULT_USER_ID, email="test@example.com", github_id=None, created_at=now)
    project = Project(id=DEFAULT_PROJECT_ID, user_id=user.id, name="My Project", created_at=now)
    create_user_with_default_project(user, project)
    return {"user_id": user.id, "project_id": project.id}