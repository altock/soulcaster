from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.main import app
from backend.models import FeedbackItem, IssueCluster
from backend.store import (
    add_cluster,
    add_feedback_item,
    clear_clusters,
    clear_feedback_items,
    get_cluster,
)


client = TestClient(app)


def setup_function():
    clear_clusters()
    clear_feedback_items()


def _seed_cluster_with_feedback(project_id):
    now = datetime.now(timezone.utc)

    feedback_one = FeedbackItem(
        id=uuid4(),
        project_id=project_id,
        source="reddit",
        external_id="ext_1",
        title="Crash on export",
        body="Export crashes on Safari",
        metadata={},
        created_at=now,
    )
    feedback_two = FeedbackItem(
        id=uuid4(),
        project_id=project_id,
        source="sentry",
        external_id="ext_2",
        title="Type error",
        body="TypeError: undefined",
        metadata={},
        created_at=now,
    )

    for item in (feedback_one, feedback_two):
        add_feedback_item(item)

    cluster = IssueCluster(
        id=str(uuid4()),
        project_id=project_id,
        title="Export issues",
        summary="Crashes and type errors during export flow",
        feedback_ids=[str(feedback_one.id), str(feedback_two.id)],
        status="new",
        created_at=now,
        updated_at=now,
    )
    add_cluster(cluster)
    return cluster, [feedback_one, feedback_two]


def test_list_clusters_returns_transformed_items(project_context):
    pid = project_context["project_id"]
    cluster, feedback_items = _seed_cluster_with_feedback(pid)

    response = client.get(f"/clusters?project_id={pid}")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1

    cluster_item = data[0]
    assert cluster_item["id"] == str(cluster.id)
    assert cluster_item["count"] == len(feedback_items)
    assert set(cluster_item["sources"]) == {"reddit", "sentry"}
    assert cluster_item["summary"] == cluster.summary


def test_get_cluster_detail_returns_feedback_items(project_context):
    pid = project_context["project_id"]
    cluster, feedback_items = _seed_cluster_with_feedback(pid)

    response = client.get(f"/clusters/{cluster.id}?project_id={pid}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(cluster.id)
    assert len(body["feedback_items"]) == len(feedback_items)
    returned_ids = {item["id"] for item in body["feedback_items"]}
    assert returned_ids == {str(item.id) for item in feedback_items}


def test_get_cluster_detail_missing_returns_404(project_context):
    pid = project_context["project_id"]
    response = client.get(f"/clusters/{uuid4()}?project_id={pid}")

    assert response.status_code == 404


def test_start_fix_updates_cluster_status(project_context):
    pid = project_context["project_id"]
    cluster, _ = _seed_cluster_with_feedback(pid)

    response = client.post(f"/clusters/{cluster.id}/start_fix?project_id={pid}")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    updated_cluster = get_cluster(cluster.id)
    assert updated_cluster.status == "fixing"


def test_cluster_fields_include_github_metadata(project_context):
    now = datetime.now(timezone.utc)
    pid = project_context["project_id"]
    cluster = IssueCluster(
        id=str(uuid4()),
        project_id=pid,
        title="GitHub PR Cluster",
        summary="Cluster with PR",
        feedback_ids=[],
        status="fixed",
        created_at=now,
        updated_at=now,
        github_pr_url="https://github.com/owner/repo/pull/123",
        github_branch="fix-issue-123",
        issue_title="Generated Issue Title",
        issue_description="Generated issue description for engineers.",
        github_repo_url="https://github.com/owner/repo",
    )
    add_cluster(cluster)

    # Check list endpoint
    response = client.get(f"/clusters?project_id={pid}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["github_pr_url"] == "https://github.com/owner/repo/pull/123"
    assert data[0]["issue_title"] == "Generated Issue Title"
    assert data[0]["issue_description"].startswith("Generated issue description")
    assert data[0]["github_repo_url"] == "https://github.com/owner/repo"

    # Check detail endpoint
    response = client.get(f"/clusters/{cluster.id}?project_id={pid}")
    assert response.status_code == 200
    data = response.json()
    assert data["github_pr_url"] == "https://github.com/owner/repo/pull/123"
    assert data["github_branch"] == "fix-issue-123"
    assert data["issue_title"] == "Generated Issue Title"
    assert data["github_repo_url"] == "https://github.com/owner/repo"
