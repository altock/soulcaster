import pytest
from uuid import UUID
from datetime import datetime, timezone
from models import CodingPlan
from store import InMemoryStore


def test_coding_plan_storage():
    store = InMemoryStore()

    plan = CodingPlan(
        id="plan-1",
        project_id="proj-1",
        cluster_id="c-1",
        title="My Plan",
        description="Desc",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # Add
    saved = store.add_coding_plan(plan)
    assert saved.id == "plan-1"

    # Get (project-scoped)
    retrieved = store.get_coding_plan("proj-1", "c-1")
    assert retrieved is not None
    assert retrieved.title == "My Plan"
    assert retrieved.cluster_id == "c-1"
    assert retrieved.project_id == "proj-1"


def test_coding_plan_missing():
    store = InMemoryStore()
    assert store.get_coding_plan("proj-1", "non-existent") is None


def test_coding_plan_project_isolation():
    """Test that coding plans are isolated by project_id."""
    store = InMemoryStore()

    plan1 = CodingPlan(
        id="plan-1",
        project_id="proj-1",
        cluster_id="cluster-1",
        title="Plan for Project 1",
        description="Desc 1",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    plan2 = CodingPlan(
        id="plan-2",
        project_id="proj-2",
        cluster_id="cluster-1",  # Same cluster_id, different project
        title="Plan for Project 2",
        description="Desc 2",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    store.add_coding_plan(plan1)
    store.add_coding_plan(plan2)

    # Each project should get its own plan
    retrieved1 = store.get_coding_plan("proj-1", "cluster-1")
    retrieved2 = store.get_coding_plan("proj-2", "cluster-1")

    assert retrieved1 is not None
    assert retrieved2 is not None
    assert retrieved1.title == "Plan for Project 1"
    assert retrieved2.title == "Plan for Project 2"

    # Different project should not find the plan
    assert store.get_coding_plan("proj-3", "cluster-1") is None


def test_coding_plan_requires_project_id():
    """Test that adding a plan without project_id raises ValueError."""
    store = InMemoryStore()

    plan = CodingPlan(
        id="plan-1",
        cluster_id="c-1",
        title="My Plan",
        description="Desc",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    with pytest.raises(ValueError, match="project_id is required"):
        store.add_coding_plan(plan)
