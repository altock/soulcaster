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


def _seed_cluster_with_feedback():
    now = datetime.now(timezone.utc)

    feedback_one = FeedbackItem(
        id=uuid4(),
        source="reddit",
        external_id="ext_1",
        title="Crash on export",
        body="Export crashes on Safari",
        metadata={},
        created_at=now,
    )
    feedback_two = FeedbackItem(
        id=uuid4(),
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
        id=uuid4(),
        title="Export issues",
        summary="Crashes and type errors during export flow",
        feedback_ids=[feedback_one.id, feedback_two.id],
        status="new",
        created_at=now,
        updated_at=now,
    )
    add_cluster(cluster)
    return cluster, [feedback_one, feedback_two]


def test_list_clusters_returns_transformed_items():
    cluster, feedback_items = _seed_cluster_with_feedback()

    response = client.get("/clusters")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1

    cluster_item = data[0]
    assert cluster_item["id"] == str(cluster.id)
    assert cluster_item["count"] == len(feedback_items)
    assert set(cluster_item["sources"]) == {"reddit", "sentry"}
    assert cluster_item["summary"] == cluster.summary


def test_get_cluster_detail_returns_feedback_items():
    cluster, feedback_items = _seed_cluster_with_feedback()

    response = client.get(f"/clusters/{cluster.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(cluster.id)
    assert len(body["feedback_items"]) == len(feedback_items)
    returned_ids = {item["id"] for item in body["feedback_items"]}
    assert returned_ids == {str(item.id) for item in feedback_items}


def test_get_cluster_detail_missing_returns_404():
    response = client.get(f"/clusters/{uuid4()}")

    assert response.status_code == 404


def test_start_fix_updates_cluster_status():
    cluster, _ = _seed_cluster_with_feedback()

    response = client.post(f"/clusters/{cluster.id}/start_fix")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    updated_cluster = get_cluster(cluster.id)
    assert updated_cluster.status == "fixing"
