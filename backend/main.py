"""FastAPI application for FeedbackAgent data ingestion.

This module provides HTTP endpoints for ingesting feedback from multiple sources:
- Reddit posts (normalized via reddit_poller)
- Sentry webhook events
- Manual text submissions
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .models import FeedbackItem
from .store import (
    add_feedback_item,
    get_feedback_item,
    get_all_feedback_items,
)

app = FastAPI(
    title="FeedbackAgent Ingestion API",
    description="API for ingesting user feedback from multiple sources",
    version="0.1.0"
)

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


# Feedback Retrieval Endpoints


@app.get("/feedback")
def get_feedback(
    source: Optional[str] = Query(None, description="Filter by source (reddit, sentry, manual)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
):
    """
    Retrieve feedback items with optional filtering and pagination.

    Args:
        source: Optional source filter (reddit, sentry, manual)
        limit: Maximum number of items to return (default 100, max 1000)
        offset: Number of items to skip for pagination (default 0)

    Returns:
        Dictionary with items list and total count
    """
    all_items = get_all_feedback_items()

    # Filter by source if specified
    if source:
        all_items = [item for item in all_items if item.source == source]

    total = len(all_items)

    # Apply pagination
    paginated_items = all_items[offset : offset + limit]

    return {
        "items": paginated_items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.get("/feedback/{item_id}")
def get_feedback_by_id(item_id: UUID):
    """
    Retrieve a single feedback item by its ID.

    Args:
        item_id: UUID of the feedback item

    Returns:
        The FeedbackItem if found

    Raises:
        HTTPException: 404 if item not found
    """
    item = get_feedback_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Feedback item {item_id} not found")
    return item


@app.get("/stats")
def get_stats():
    """
    Get summary statistics about feedback items and clusters.

    Returns:
        Dictionary with:
        - total_feedback: Total number of feedback items
        - by_source: Breakdown of feedback by source
        - total_clusters: Number of clusters (placeholder for future)
    """
    all_items = get_all_feedback_items()
    total = len(all_items)

    # Count by source
    by_source = {"reddit": 0, "sentry": 0, "manual": 0}
    for item in all_items:
        by_source[item.source] += 1

    return {
        "total_feedback": total,
        "by_source": by_source,
        "total_clusters": 0,  # Placeholder for clustering feature
    }


@app.get("/clusters")
def get_clusters():
    """
    Get all issue clusters (placeholder for future clustering feature).

    Returns:
        Empty list for now, will return clustered issues in the future
    """
    # TODO: Implement clustering logic
    # For now, return empty list with proper structure
    return {
        "clusters": [],
        "total": 0,
    }
