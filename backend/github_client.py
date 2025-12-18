"""
Minimal GitHub client utilities used by the ingestion backend.

Responsible for:
- Fetching issues (excluding pull requests) with optional incremental sync.
- Converting GitHub issue payloads into `FeedbackItem` instances.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import requests

from models import FeedbackItem

logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com"


def _auth_headers(token: Optional[str] = None) -> Dict[str, str]:
    """
    Build GitHub API headers with optional authentication.
    
    Args:
        token: GitHub access token (from OAuth or env). If not provided,
               falls back to GITHUB_TOKEN environment variable.
    """
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "FeedbackAgent/1.0",
    }
    # Use provided token, or fall back to env var
    auth_token = token or os.getenv("GITHUB_TOKEN")
    if auth_token:
        headers["Authorization"] = f"token {auth_token}"
    return headers


def _parse_next_link(link_header: Optional[str]) -> Optional[str]:
    """Extract the 'next' link from a GitHub Link header, if present."""
    if not link_header:
        return None
    parts = link_header.split(",")
    for part in parts:
        section = part.split(";")
        if len(section) < 2:
            continue
        url_part, rel_part = section[0].strip(), section[1].strip()
        if rel_part == 'rel="next"':
            return url_part.strip("<> ")
    return None


def _parse_github_datetime(value: str) -> datetime:
    """Parse GitHub datetime strings like 2024-01-01T00:00:00Z."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def fetch_repo_issues(
    owner: str,
    repo: str,
    since: Optional[str] = None,
    token: Optional[str] = None,
    max_pages: int = 20,
    max_issues: int = 2000,
    state: str = "open",
) -> List[Dict[str, Any]]:
    """
    Fetch issues (excluding pull requests) for a repository.

    Args:
        owner: GitHub repo owner.
        repo: Repository name.
        since: Optional ISO 8601 timestamp (e.g., "2024-01-01T00:00:00Z") to fetch issues updated since then.
        token: Optional GitHub access token (from user OAuth session).
        max_pages: Maximum number of pages to fetch.
        max_issues: Maximum number of issues to fetch.
        state: Issue state filter - "open", "closed", or "all". Defaults to "open".

    Returns:
        List of issue dicts (pull requests filtered out).

    Raises:
        requests.HTTPError: If the GitHub API request fails (e.g., 422 for invalid since format).
    """
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/issues"
    params = {
        "state": state,
        "per_page": 100,
        "sort": "updated",
        "direction": "desc",
    }
    if since:
        params["since"] = since

    issues: List[Dict[str, Any]] = []
    session = requests.Session()
    page = 0
    seen_urls = set()

    while url:
        page += 1
        if page > max_pages:
            logger.warning(
                "Stopping fetch for %s/%s after reaching max_pages=%s", owner, repo, max_pages
            )
            break
        if url in seen_urls:
            logger.warning("Detected repeated page URL, stopping pagination: %s", url)
            break
        seen_urls.add(url)

        resp = session.get(url, headers=_auth_headers(token), params=params, timeout=15)
        resp.raise_for_status()
        page_items = resp.json()

        # Filter out pull requests
        for issue in page_items:
            if issue.get("pull_request"):
                continue
            issues.append(issue)
            if len(issues) >= max_issues:
                logger.warning(
                    "Stopping fetch for %s/%s after reaching max_issues=%s",
                    owner,
                    repo,
                    max_issues,
                )
                return issues

        # Handle pagination
        link = resp.headers.get("Link")
        url = _parse_next_link(link)
        params = None  # Only include params on first request

        # Log rate limit info when available
        remaining = resp.headers.get("X-RateLimit-Remaining")
        limit = resp.headers.get("X-RateLimit-Limit")
        reset = resp.headers.get("X-RateLimit-Reset")
        if remaining and limit:
            logger.info(
                "GitHub rate limit: %s/%s remaining%s",
                remaining,
                limit,
                f", resets at {datetime.fromtimestamp(int(reset), tz=timezone.utc)}" if reset else "",
            )

    return issues


def issue_to_feedback_item(issue: Dict[str, Any], repo_full_name: str, project_id: str) -> FeedbackItem:
    """
    Convert a GitHub issue payload to a FeedbackItem.

    Args:
        issue: GitHub issue JSON.
        repo_full_name: "owner/repo".
        project_id: Project scope for the feedback item.
    """
    created_at = _parse_github_datetime(issue["created_at"])
    updated_at = issue.get("updated_at")
    metadata: Dict[str, Any] = {
        "labels": [label.get("name") for label in issue.get("labels", [])],
        "state": issue.get("state"),
        "comments": issue.get("comments", 0),
        "created_at": issue.get("created_at"),
        "updated_at": updated_at,
        "author": issue.get("user", {}).get("login"),
        "assignees": [assignee.get("login") for assignee in issue.get("assignees", [])],
        "milestone": (issue.get("milestone") or {}).get("title"),
    }

    return FeedbackItem(
        id=uuid4(),
        project_id=project_id,
        source="github",
        external_id=str(issue.get("id")),
        title=issue.get("title") or f"{repo_full_name} issue #{issue.get('number')}",
        body=issue.get("body") or "",
        raw_text=(issue.get("body") or issue.get("title") or ""),
        metadata=metadata,
        created_at=created_at,
        repo=repo_full_name,
        github_issue_number=issue.get("number"),
        github_issue_url=issue.get("html_url"),
        status=issue.get("state"),
    )

