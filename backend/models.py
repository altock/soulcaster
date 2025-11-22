"""Domain models for FeedbackAgent data ingestion layer."""

from datetime import datetime
from typing import Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel


class FeedbackItem(BaseModel):
    """
    Represents a single piece of user feedback from any source.

    This model normalizes feedback from different sources (Reddit, Sentry, manual)
    into a consistent schema for processing by the FeedbackAgent system.

    Attributes:
        id: Unique identifier for this feedback item
        source: The origin of the feedback (reddit, sentry, or manual)
        external_id: ID from the original source system (e.g., Reddit post ID)
        title: Short summary or title (max 80 chars for manual entries)
        body: Full text content of the feedback
        metadata: Source-specific data (subreddit, stack traces, etc.)
        created_at: Timestamp when the feedback was created
    """

    id: UUID
    source: Literal["reddit", "sentry", "manual"]
    external_id: Optional[str] = None
    title: str
    body: str
    metadata: Dict = {}
    created_at: datetime


class IssueCluster(BaseModel):
    """Represents a cluster of related feedback items."""

    id: UUID
    title: str
    summary: str
    feedback_ids: List[UUID]
    status: str
    created_at: datetime
    updated_at: datetime
    embedding_centroid: Optional[List[float]] = None
    github_branch: Optional[str] = None
    github_pr_url: Optional[str] = None
    error_message: Optional[str] = None
