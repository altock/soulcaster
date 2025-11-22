"""FastAPI application for FeedbackAgent data ingestion.

This module provides HTTP endpoints for ingesting feedback from multiple sources:
- Reddit posts (normalized via reddit_poller)
- Sentry webhook events
- Manual text submissions
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .models import FeedbackItem, IssueCluster
from .store import (
    add_cluster,
    add_feedback_item,
    get_all_clusters,
    get_feedback_item,
    get_cluster,
    update_cluster,
)

app = FastAPI(
    title="FeedbackAgent Ingestion API",
    description="API for ingesting user feedback from multiple sources",
    version="0.1.0"
)


@app.get("/")
def read_root():
    """Health check endpoint."""
    return {"status": "ok", "service": "feedbackagent-ingestion"}


@app.post("/ingest/reddit")
def ingest_reddit(item: FeedbackItem):
    """
    Ingest a feedback item from Reddit.

    This endpoint receives already-normalized Reddit posts from the reddit_poller.

    Args:
        item: FeedbackItem with Reddit post data

    Returns:
        Status response indicating success
    """
    add_feedback_item(item)
    return {"status": "ok", "id": str(item.id)}


@app.post("/ingest/sentry")
def ingest_sentry(payload: dict):
    """
    Ingest an error report from Sentry webhook.

    Parses Sentry's webhook payload and normalizes it into a FeedbackItem.
    Extracts exception type, message, and stack trace frames.

    Args:
        payload: Raw Sentry webhook payload

    Returns:
        Status response with created feedback item ID
    """
    try:
        event_id = payload.get("event_id")
        title = payload.get("message") or "Sentry Issue"

        # Construct body from exception data
        body = ""
        exception = payload.get("exception", {}).get("values", [])
        if exception:
            exc = exception[0]
            exc_type = exc.get("type", "Error")
            exc_value = exc.get("value", "")
            body += f"{exc_type}: {exc_value}\n\nStacktrace:\n"
            # Include first 3 stack frames for context
            for frame in exc.get("stacktrace", {}).get("frames", [])[:3]:
                body += f"  {frame.get('filename')}:{frame.get('lineno')}\n"

        item = FeedbackItem(
            id=uuid4(),
            source="sentry",
            external_id=event_id,
            title=title,
            body=body,
            metadata=payload,
            created_at=datetime.now(timezone.utc)
        )
        add_feedback_item(item)
        return {"status": "ok", "id": str(item.id)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process Sentry payload: {str(e)}")


class ManualIngestRequest(BaseModel):
    """Request model for manual feedback submission."""
    text: str


@app.post("/ingest/manual")
def ingest_manual(request: ManualIngestRequest):
    """
    Ingest manually submitted feedback text.

    Creates a FeedbackItem from raw text input. Title is truncated to 80 characters.

    Args:
        request: ManualIngestRequest containing the feedback text

    Returns:
        Status response with created feedback item ID
    """
    item = FeedbackItem(
        id=uuid4(),
        source="manual",
        title=request.text[:80],  # Truncate title to 80 chars
        body=request.text,
        metadata={},
        created_at=datetime.now(timezone.utc)
    )
    add_feedback_item(item)
    return {"status": "ok", "id": str(item.id)}


@app.get("/clusters")
def list_clusters():
    """List all issue clusters with aggregated metadata."""

    clusters = get_all_clusters()
    results = []
    for cluster in clusters:
        feedback_items = [get_feedback_item(fid) for fid in cluster.feedback_ids]
        sources = sorted({item.source for item in feedback_items if item})
        results.append(
            {
                "id": cluster.id,
                "title": cluster.title,
                "summary": cluster.summary,
                "count": len(cluster.feedback_ids),
                "status": cluster.status,
                "sources": sources,
                "github_pr_url": cluster.github_pr_url,
            }
        )
    return results


@app.get("/clusters/{cluster_id}")
def get_cluster_detail(cluster_id: UUID):
    """Retrieve a cluster with its feedback items."""

    cluster = get_cluster(cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    feedback_items = [get_feedback_item(fid) for fid in cluster.feedback_ids]
    response = cluster.model_dump()
    response["feedback_items"] = [item for item in feedback_items if item]
    return response


@app.post("/clusters/{cluster_id}/start_fix")
def start_cluster_fix(cluster_id: UUID):
    """Begin fix generation for a cluster (stub implementation)."""

    cluster = get_cluster(cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    updated_cluster = update_cluster(cluster_id, status="fixing")
    return {"status": "ok", "message": "Fix generation started", "cluster_id": updated_cluster.id}


def seed_mock_data():
    """Seed a handful of feedback items and clusters for local testing."""

    now = datetime.now(timezone.utc)

    feedback_one = FeedbackItem(
        id=uuid4(),
        source="reddit",
        external_id="t3_mock1",
        title="Export crashes on Safari",
        body="App crashes when exporting on Safari 16.",
        metadata={"subreddit": "mock_sub"},
        created_at=now,
    )
    feedback_two = FeedbackItem(
        id=uuid4(),
        source="sentry",
        external_id="evt_mock2",
        title="TypeError in export job",
        body="TypeError: cannot read properties of undefined",
        metadata={},
        created_at=now,
    )
    feedback_three = FeedbackItem(
        id=uuid4(),
        source="manual",
        title="Export broken",
        body="Manual report of export failing on Firefox",
        metadata={},
        created_at=now,
    )

    for item in (feedback_one, feedback_two, feedback_three):
        add_feedback_item(item)

    cluster = IssueCluster(
        id=uuid4(),
        title="Export failures",
        summary="Users report export crashes across browsers.",
        feedback_ids=[feedback_one.id, feedback_two.id, feedback_three.id],
        status="new",
        created_at=now,
        updated_at=now,
    )

    add_cluster(cluster)
    return {"cluster_id": cluster.id, "feedback_ids": [feedback_one.id, feedback_two.id, feedback_three.id]}
