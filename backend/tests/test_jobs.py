from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from main import app
from models import AgentJob, IssueCluster
from store import (
    add_cluster,
    add_job,
    clear_clusters,
    clear_jobs,
    get_job,
)


client = TestClient(app)


def setup_function():
    """
    Run before each test to clear persisted clusters and jobs, ensuring a clean test state.
    
    This setup function removes all stored IssueCluster and AgentJob entries so tests run with no leftover data from prior executions.
    """
    clear_clusters()
    clear_jobs()


def _seed_cluster(project_id):
    """
    Create and persist a test IssueCluster associated with the given project.
    
    Parameters:
        project_id (str): Identifier of the project to associate with the created cluster.
    
    Returns:
        IssueCluster: The created and stored IssueCluster instance with generated id and timestamps.
    """
    now = datetime.now(timezone.utc)
    cluster = IssueCluster(
        id=str(uuid4()),
        project_id=project_id,
        title="Test Cluster",
        summary="Test Summary",
        feedback_ids=[],
        status="new",
        created_at=now,
        updated_at=now,
    )
    add_cluster(cluster)
    return cluster


def test_create_job(project_context):
    """
    Create a job for a seeded cluster and verify the job is persisted and initialized as pending.
    
    This test seeds an IssueCluster for the given project, posts a create-job request scoped to that project, asserts the HTTP response indicates success and includes a job id, then retrieves the created job and asserts it is associated with the seeded cluster and has status "pending".
    
    Parameters:
        project_context (dict): Pytest fixture providing context for the test, including the key `"project_id"`.
    """
    pid = project_context["project_id"]
    cluster = _seed_cluster(pid)
    response = client.post(f"/jobs?project_id={pid}", json={"cluster_id": str(cluster.id)})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "job_id" in data

    job = get_job(uuid4())  # We don't know ID, but we can search or rely on ID return
    # Better: verify ID returned is valid
    job_id = data["job_id"]
    job = get_job(job_id) # Should work if passing string, but get_job expects UUID usually?
    # store.py: get_job(job_id: UUID)
    # Let's convert string to UUID
    from uuid import UUID
    job = get_job(UUID(job_id))
    
    assert job is not None
    assert job.cluster_id == cluster.id
    assert job.status == "pending"


def test_update_job_status(project_context):
    pid = project_context["project_id"]
    cluster = _seed_cluster(pid)
    now = datetime.now(timezone.utc)
    job = AgentJob(
        id=uuid4(),
        project_id=pid,
        cluster_id=cluster.id,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    add_job(job)

    response = client.patch(f"/jobs/{job.id}?project_id={pid}", json={"status": "running"})

    assert response.status_code == 200
    
    updated = get_job(job.id)
    assert updated.status == "running"


def test_update_job_logs(project_context):
    """
    Verifies that a job's logs can be updated via the PATCH /jobs/{id} endpoint within a project.
    
    Creates a pending AgentJob for the given project and cluster, sends a PATCH request with new logs, and asserts the endpoint returns HTTP 200 and the persisted job's `logs` field matches the provided content.
    """
    pid = project_context["project_id"]
    cluster = _seed_cluster(pid)
    now = datetime.now(timezone.utc)
    job = AgentJob(
        id=uuid4(),
        project_id=pid,
        cluster_id=cluster.id,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    add_job(job)

    log_content = "Starting fix process..."
    response = client.patch(f"/jobs/{job.id}?project_id={pid}", json={"logs": log_content})

    assert response.status_code == 200
    
    updated = get_job(job.id)
    assert updated.logs == log_content


def test_get_job_details(project_context):
    """
    Verify that retrieving a job by ID returns its details scoped to the project.
    
    Seeds a cluster and a job for the given project, performs GET /jobs/{id}?project_id={pid}, and asserts the response contains the job's `id`, `status`, and `logs`.
    """
    pid = project_context["project_id"]
    cluster = _seed_cluster(pid)
    now = datetime.now(timezone.utc)
    job = AgentJob(
        id=uuid4(),
        project_id=pid,
        cluster_id=cluster.id,
        status="pending",
        logs="Initial logs",
        created_at=now,
        updated_at=now,
    )
    add_job(job)

    response = client.get(f"/jobs/{job.id}?project_id={pid}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(job.id)
    assert data["status"] == "pending"
    assert data["logs"] == "Initial logs"


def test_get_cluster_jobs(project_context):
    """
    Verify that the cluster jobs endpoint returns all jobs for a given cluster and project.
    
    Creates a cluster for the provided project, inserts two jobs tied to that cluster and project, calls GET /clusters/{cluster.id}/jobs with the project's query parameter, and asserts the response is HTTP 200 and contains both job IDs.
    
    Parameters:
        project_context (dict): Test fixture providing at least a "project_id" key used to scope created resources and the request.
    """
    pid = project_context["project_id"]
    cluster = _seed_cluster(pid)
    now = datetime.now(timezone.utc)
    
    # Create 2 jobs
    job1 = AgentJob(
        id=uuid4(),
        project_id=pid,
        cluster_id=cluster.id,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    add_job(job1)
    
    job2 = AgentJob(
        id=uuid4(),
        project_id=pid,
        cluster_id=cluster.id,
        status="success",
        created_at=now,
        updated_at=now,
    )
    add_job(job2)

    response = client.get(f"/clusters/{cluster.id}/jobs?project_id={pid}")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    ids = {item["id"] for item in data}
    assert str(job1.id) in ids
    assert str(job2.id) in ids