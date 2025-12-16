# Test full flow: POST /start_fix -> Orchestrator -> Sandbox Runner
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from main import app
from models import IssueCluster, AgentJob, FeedbackItem
from store import add_cluster, add_coding_plan, get_job, add_feedback_item, get_cluster
from datetime import datetime, timezone
from uuid import uuid4, UUID

client = TestClient(app)

@pytest.fixture
def sample_data(project_context):
    pid = project_context["project_id"]
    
    feedback = FeedbackItem(
        id=uuid4(),
        project_id=pid,
        source="github",
        title="Issue: CI failing",
        body="CI is failing on main",
        raw_text="https://github.com/octocat/Hello-World/issues/1",
        metadata={},
        created_at=datetime.now(timezone.utc),
        repo="octocat/Hello-World",
        github_issue_number=1,
        github_issue_url="https://github.com/octocat/Hello-World/issues/1",
        status="open",
    )
    add_feedback_item(feedback)

    # Create cluster
    cluster = IssueCluster(
        id="cluster-123", project_id=pid, title="Test Cluster", summary="Summary",
        feedback_ids=[str(feedback.id)], status="new", created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    add_cluster(cluster)
    
    return {"pid": pid, "cluster": cluster, "feedback": feedback}

@patch("main.generate_plan")
@patch("agent_runner.sandbox.SandboxKilocodeRunner.start", new_callable=AsyncMock)
def test_start_fix_creates_plan_and_job(mock_runner_start, mock_generate_plan, sample_data, monkeypatch):
    # Setup
    pid = sample_data["pid"]
    cid = sample_data["cluster"].id
    monkeypatch.setenv("ENABLE_AGENT_RUNNER_IN_TESTS", "true")
    
    # Mock plan generation
    mock_plan = AsyncMock()
    mock_plan.id = "plan-abc"
    mock_plan.cluster_id = cid
    mock_generate_plan.return_value = mock_plan # synchronous return for generate_plan mock
    
    # We need to mock generate_plan to return a real Pydantic model or mock behaving like one specific for the real code
    # Actually, planner.generate_plan is synchronous.
    from models import CodingPlan
    real_plan = CodingPlan(
        id="plan-abc", cluster_id=cid, title="Generated Plan", description="Desc",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    mock_generate_plan.return_value = real_plan

    # Call Endpoint
    response = client.post(f"/clusters/{cid}/start_fix?project_id={pid}")
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "job_id" in data
    
    # Verify job created
    job_id = UUID(data["job_id"])
    job = get_job(job_id)
    assert job is not None
    assert job.cluster_id == cid
    assert job.status == "pending"
    assert job.runner == "sandbox_kilo" # Default
    
    # Verify cluster status updated
    updated_cluster = get_cluster(str(pid), cid)
    assert updated_cluster.status == "fixing"

    # Verify runner was called (eventually, or inline if no background tasks in TestClient?)
    # TestClient doesn't run BackgroundTasks automatically unless we use a context or something?
    # Actually FastAPI TestClient triggers BackgroundTasks after response.
    # However, since we mock get_running_loop inside the fallback block or use background_tasks, 
    # and TestClient handles background_tasks synchronously-ish.
    
    # Wait/Check if mock called.
    # In main.py we use background_tasks.add_task(_run_agent). Starlette TestClient runs these.
    mock_runner_start.assert_called_once()
    
    # Check args passed to runner
    args, _ = mock_runner_start.call_args
    job_arg, plan_arg, cluster_arg = args
    assert job_arg.id == job_id
    assert plan_arg.id == "plan-abc"
    assert cluster_arg.id == cid
    assert cluster_arg.github_repo_url == "https://github.com/octocat/Hello-World"

def test_get_plan_endpoint(sample_data):
    cid = sample_data["cluster"].id
    pid = sample_data["pid"]
    
    # Initially 404
    resp = client.get(f"/clusters/{cid}/plan?project_id={pid}")
    assert resp.status_code == 404
    
    # Add plan
    from models import CodingPlan
    plan = CodingPlan(
        id="p1", cluster_id=cid, title="P1", description="D", 
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    add_coding_plan(plan)
    
    # Now 200
    resp = client.get(f"/clusters/{cid}/plan?project_id={pid}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "P1"

@patch("main.generate_plan")
def test_manual_plan_generation(mock_gen, sample_data):
    cid = sample_data["cluster"].id
    pid = sample_data["pid"]
    
    from models import CodingPlan
    mock_gen.return_value = CodingPlan(
        id="p2", cluster_id=cid, title="Gen", description="D", 
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    
    resp = client.post(f"/clusters/{cid}/plan?project_id={pid}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Gen"
    mock_gen.assert_called_once()
