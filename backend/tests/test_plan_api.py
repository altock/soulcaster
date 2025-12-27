from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app
from models import IssueCluster, CodingPlan
from store import add_cluster, clear_clusters, add_coding_plan, clear_coding_plans, get_coding_plan

client = TestClient(app)

def setup_function():
    clear_clusters()
    clear_coding_plans()

def test_generate_plan_error_handling(project_context):
    pid = project_context["project_id"]
    cluster = IssueCluster(
        id=str(uuid4()),
        project_id=pid,
        title="Test Cluster",
        summary="Summary",
        feedback_ids=[],
        status="new",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    add_cluster(cluster)

    with patch("main.generate_plan") as mock_generate:
        mock_generate.side_effect = Exception("Service Unavailable")
        
        response = client.post(f"/clusters/{cluster.id}/plan?project_id={pid}")
        
        assert response.status_code == 503
        assert "Service Unavailable" in response.json()["detail"]
        
        # Verify no plan was saved
        assert get_coding_plan(cluster.id) is None

def test_update_plan_success(project_context):
    pid = project_context["project_id"]
    cluster = IssueCluster(
        id=str(uuid4()),
        project_id=pid,
        title="Test Cluster",
        summary="Summary",
        feedback_ids=[],
        status="new",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    add_cluster(cluster)
    
    plan = CodingPlan(
        id=str(uuid4()),
        cluster_id=cluster.id,
        title="Original Title",
        description="Original Description",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    add_coding_plan(plan)

    payload = {
        "title": "Updated Title",
        "description": "Updated Description"
    }
    
    response = client.patch(f"/clusters/{cluster.id}/plan?project_id={pid}", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["description"] == "Updated Description"
    
    # Verify in store
    updated = get_coding_plan(cluster.id)
    assert updated.title == "Updated Title"
    assert updated.description == "Updated Description"

def test_update_plan_partial(project_context):
    pid = project_context["project_id"]
    cluster = IssueCluster(
        id=str(uuid4()),
        project_id=pid,
        title="Test Cluster",
        summary="Summary",
        feedback_ids=[],
        status="new",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    add_cluster(cluster)
    
    plan = CodingPlan(
        id=str(uuid4()),
        cluster_id=cluster.id,
        title="Original Title",
        description="Original Description",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    add_coding_plan(plan)

    payload = {
        "title": "New Title"
    }
    
    response = client.patch(f"/clusters/{cluster.id}/plan?project_id={pid}", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "New Title"
    assert data["description"] == "Original Description"

def test_update_plan_not_found(project_context):
    pid = project_context["project_id"]
    cluster = IssueCluster(
        id=str(uuid4()),
        project_id=pid,
        title="Test Cluster",
        summary="Summary",
        feedback_ids=[],
        status="new",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    add_cluster(cluster)
    
    response = client.patch(f"/clusters/{cluster.id}/plan?project_id={pid}", json={"title": "test"})
    assert response.status_code == 404
