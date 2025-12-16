import pytest
from uuid import UUID
from datetime import datetime, timezone
from models import CodingPlan
from store import InMemoryStore

def test_coding_plan_storage():
    store = InMemoryStore()
    
    plan = CodingPlan(
        id="plan-1", cluster_id="c-1", title="My Plan", 
        description="Desc",
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)
    )
    
    # Add
    saved = store.add_coding_plan(plan)
    assert saved.id == "plan-1"
    
    # Get
    retrieved = store.get_coding_plan("c-1")
    assert retrieved is not None
    assert retrieved.title == "My Plan"
    assert retrieved.cluster_id == "c-1"

def test_coding_plan_missing():
    store = InMemoryStore()
    assert store.get_coding_plan("non-existent") is None
