"""Domain models for FeedbackAgent data ingestion layer."""

from datetime import datetime
from typing import Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AgentJob(BaseModel):
    """
    Represents a background job for the coding agent.
    """

    id: UUID
    cluster_id: str
    status: Literal["pending", "running", "success", "failed"]
    logs: Optional[str] = None
    pr_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


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

    id: str
    title: str
    summary: str
    feedback_ids: List[str]
    status: str
    created_at: datetime
    updated_at: datetime
    # Map frontend 'centroid' to this field or allow both
    centroid: Optional[List[float]] = Field(default=None, alias="embedding_centroid")
    github_branch: Optional[str] = None
    github_pr_url: Optional[str] = None
    error_message: Optional[str] = None
    issue_title: Optional[str] = None
    issue_description: Optional[str] = None
    github_repo_url: Optional[str] = None
