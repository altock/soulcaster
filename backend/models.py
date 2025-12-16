"""Domain models for FeedbackAgent data ingestion layer."""

from datetime import datetime
from typing import Dict, List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field

try:
    # Pydantic v2
    from pydantic import ConfigDict
except ImportError:  # pragma: no cover
    # Pydantic v1 fallback
    ConfigDict = None  # type: ignore


class AgentJob(BaseModel):
    """
    Represents a background job for the coding agent.
    """

    id: UUID
    project_id: Union[str, UUID]  # Supports both UUID and CUID formats
    cluster_id: str
    plan_id: Optional[str] = None
    runner: Optional[str] = None
    status: Literal["pending", "running", "success", "failed"]
    logs: Optional[str] = None
    pr_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CodingPlan(BaseModel):
    """
    Represents a generated coding plan to fix a cluster of issues.
    """

    if ConfigDict:
        # Allow decoding older stored plans that may contain extra fields.
        model_config = ConfigDict(extra="ignore")
    else:  # pragma: no cover
        class Config:
            extra = "ignore"

    id: str
    cluster_id: str
    title: str
    description: str
    created_at: datetime
    updated_at: datetime


class ClusterJob(BaseModel):
    """
    Represents a clustering job tracked by the backend.
    """

    id: str
    project_id: Union[str, UUID]
    status: Literal["pending", "running", "succeeded", "failed"]
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    stats: Dict[str, int] = {}


class FeedbackItem(BaseModel):
    """
    Represents a single piece of user feedback from any source.

    This model normalizes feedback from different sources (Reddit, Sentry, manual, GitHub)
    into a consistent schema for processing by the FeedbackAgent system.

    Attributes:
        id: Unique identifier for this feedback item
        project_id: Project this feedback belongs to (multi-tenant boundary, supports UUID/CUID)
        source: The origin of the feedback (reddit, sentry, manual, or github)
        external_id: ID from the original source system (e.g., Reddit post ID)
        title: Short summary or title (max 80 chars for manual entries)
        body: Full text content of the feedback
        metadata: Source-specific data (subreddit, stack traces, etc.)
        created_at: Timestamp when the feedback was created
    """

    id: UUID
    project_id: Union[str, UUID]  # Supports both UUID and CUID formats
    source: Literal["reddit", "sentry", "manual", "github"]
    external_id: Optional[str] = None
    title: str
    body: str
    raw_text: Optional[str] = None
    metadata: Dict = {}
    created_at: datetime
    # GitHub-specific fields (optional; present when source == "github")
    repo: Optional[str] = None
    github_issue_number: Optional[int] = None
    github_issue_url: Optional[str] = None
    status: Optional[Literal["open", "closed"]] = None

    @property
    def text(self) -> str:
        """
        Provide the feedback item's text as an alias for its body for backward compatibility.
        
        Returns:
            str: The feedback text (same value as `body`).
        """
        return self.body


class IssueCluster(BaseModel):
    """Represents a cluster of related feedback items."""

    id: str
    project_id: Union[str, UUID]  # Supports both UUID and CUID formats
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


class User(BaseModel):
    """Represents an authenticated user."""

    id: Union[str, UUID]  # Supports both UUID and CUID formats
    email: Optional[str] = None
    github_id: Optional[str] = None
    created_at: datetime


class Project(BaseModel):
    """Represents a project/workspace owned by a user."""

    id: Union[str, UUID]  # Supports both UUID and CUID formats
    user_id: Union[str, UUID]
    name: str
    created_at: datetime