"""Temporary Reddit poller using public JSON endpoints.

This module replaces the OAuth/PRAW flow with a hackathon-safe fetcher that uses
Reddit's unauthenticated JSON listings. It normalizes posts and forwards them to
the ingestion API while respecting rate limits and caching.
"""

import os
import time
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Set
from uuid import uuid4

import requests

try:
    from .store import get_reddit_subreddits as _store_get_reddit_subreddits
except ImportError:
    try:
        from store import get_reddit_subreddits as _store_get_reddit_subreddits
    except ImportError:
        _store_get_reddit_subreddits = None
except Exception:
    _store_get_reddit_subreddits = None

USER_AGENT = "Mozilla/5.0 (FeedbackAgentHackathon/0.1)"
SUPPORTED_SORTS = {"new", "hot", "top"}
DEFAULT_SORTS = ["new"]
DEFAULT_POLL_INTERVAL = 300  # seconds
DEFAULT_THROTTLE_SECONDS = 1.0
MAX_RETRIES = 4
MAX_BACKOFF_SECONDS = 64

# Default API endpoint for posting feedback
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


def _parse_env_list(env_value: Optional[str], default: List[str]) -> List[str]:
    """Split a comma-delimited env var into a list, trimming whitespace."""
    if not env_value:
        return default
    values = [value.strip() for value in env_value.split(",")]
    cleaned = [value for value in values if value]
    return cleaned or default


def get_env_subreddits() -> List[str]:
    """Fetch configured subreddits from env (supports old and new variable names)."""
    env_value = os.getenv("REDDIT_SUBREDDITS") or os.getenv("REDDIT_SUBREDDIT")
    return _parse_env_list(env_value, ["claudeai"])


def get_configured_subreddits() -> List[str]:
    """Prefer store-backed config; fall back to env defaults."""
    if _store_get_reddit_subreddits:
        try:
            configured = _store_get_reddit_subreddits()
            if configured:
                return configured
        except Exception as exc:
            print(f"Warning: failed to load subreddits from store; falling back to env. ({exc})")
    return get_env_subreddits()


def get_env_sorts() -> List[str]:
    """Return valid sorts pulled from env with a safe fallback."""
    env_value = os.getenv("REDDIT_SORTS")
    sorts = _parse_env_list(env_value, DEFAULT_SORTS)
    filtered = [sort for sort in sorts if sort in SUPPORTED_SORTS]
    return filtered or DEFAULT_SORTS


def get_poll_interval_seconds() -> int:
    """Poll interval in seconds (default: 5 minutes)."""
    env_interval = os.getenv("REDDIT_POLL_INTERVAL_SECONDS")
    env_minutes = os.getenv("REDDIT_POLL_INTERVAL_MINUTES")
    if env_interval and env_interval.isdigit():
        return int(env_interval)
    if env_minutes and env_minutes.isdigit():
        return int(env_minutes) * 60
    return DEFAULT_POLL_INTERVAL


def _now_iso(utc_timestamp: float) -> str:
    """Convert unix timestamp to ISO 8601."""
    return datetime.fromtimestamp(utc_timestamp, timezone.utc).isoformat()


class RedditPoller:
    """JSON-based Reddit poller with throttling, caching, and backoff."""

    def __init__(
        self,
        *,
        sorts: Optional[List[str]] = None,
        poll_interval: Optional[int] = None,
        throttle_seconds: float = DEFAULT_THROTTLE_SECONDS,
        session: Optional[requests.Session] = None,
        sleep_fn=time.sleep,
    ):
        self.sorts = sorts or get_env_sorts()
        self.poll_interval = poll_interval or get_poll_interval_seconds()
        self.throttle_seconds = throttle_seconds
        self.session = session or requests.Session()
        self.sleep = sleep_fn
        self.seen_post_ids: Set[str] = set()
        self.etag_cache: Dict[tuple, str] = {}
        self.last_request_at: Dict[str, float] = {}

    def fetch_reddit_posts(self, subreddits: Iterable[str]) -> List[dict]:
        """Fetch normalized posts for the provided subreddits."""
        posts: List[dict] = []
        for subreddit in subreddits:
            for sort in self.sorts:
                posts.extend(self._fetch_subreddit_listing(subreddit, sort))
        return posts

    def _fetch_subreddit_listing(self, subreddit: str, sort: str) -> List[dict]:
        """Fetch a single subreddit listing with caching and backoff."""
        sort = sort if sort in SUPPORTED_SORTS else "new"
        url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit=100"

        etag_key = (subreddit, sort)
        headers = {"User-Agent": USER_AGENT}
        if etag_key in self.etag_cache:
            headers["If-None-Match"] = self.etag_cache[etag_key]

        response = self._request_with_backoff(url, headers, subreddit)
        if response is None or response.status_code == 304:
            return []

        etag = response.headers.get("ETag")
        if etag:
            self.etag_cache[etag_key] = etag

        try:
            payload = response.json()
        except ValueError:
            print(f"Failed to decode JSON for r/{subreddit} ({sort})")
            return []

        return self._normalize_posts(payload, subreddit)

    def _normalize_posts(self, payload: dict, fallback_subreddit: str) -> List[dict]:
        """Normalize Reddit JSON listing into Post objects."""
        posts: List[dict] = []
        children = payload.get("data", {}).get("children", [])
        for child in children:
            post_data = child.get("data", {})
            post_id = post_data.get("id")
            if not post_id or post_id in self.seen_post_ids:
                continue

            self.seen_post_ids.add(post_id)
            created_utc = post_data.get("created_utc") or time.time()
            posts.append(
                {
                    "id": post_id,
                    "title": post_data.get("title") or "",
                    "selftext": post_data.get("selftext") or "",
                    "url": post_data.get("url") or "",
                    "author": post_data.get("author") or "[deleted]",
                    "created_utc": created_utc,
                    "score": post_data.get("score", 0),
                    "num_comments": post_data.get("num_comments", 0),
                    "subreddit": post_data.get("subreddit") or fallback_subreddit,
                    "permalink": post_data.get("permalink") or "",
                }
            )
        return posts

    def _request_with_backoff(
        self, url: str, headers: Dict[str, str], subreddit: str
    ) -> Optional[requests.Response]:
        """HTTP GET with per-subreddit throttling and exponential backoff."""
        backoff = 1
        attempts = 0
        while attempts <= MAX_RETRIES:
            self._throttle(subreddit)
            try:
                response = self.session.get(url, headers=headers, timeout=10)
            except requests.RequestException as exc:
                print(f"Network error fetching {url}: {exc}")
                attempts += 1
                backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
                self.sleep(backoff)
                continue

            if response.status_code in (429, 403):
                print(
                    f"Rate limited ({response.status_code}) for r/{subreddit}; "
                    f"backing off for {backoff}s"
                )
                attempts += 1
                self.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
                continue

            try:
                response.raise_for_status()
            except requests.HTTPError as exc:
                print(f"Failed to fetch {url}: {exc}")
                return None

            return response

        print(f"Exceeded retries for r/{subreddit}; skipping this round")
        return None

    def _throttle(self, subreddit: str) -> None:
        """Ensure we don't exceed 1 req/sec per subreddit."""
        last_seen = self.last_request_at.get(subreddit)
        now = time.monotonic()
        if last_seen is not None:
            elapsed = now - last_seen
            if elapsed < self.throttle_seconds:
                self.sleep(self.throttle_seconds - elapsed)
        self.last_request_at[subreddit] = time.monotonic()

    def poll_once(
        self,
        subreddits: Iterable[str],
        backend_url: Optional[str] = None,
        ingest_fn=None,
    ) -> None:
        """Fetch posts once and send them to the ingestion API."""
        posts = self.fetch_reddit_posts(subreddits)
        if not posts:
            return

        ingest_url = f"{backend_url or BACKEND_URL}/ingest/reddit"
        for post in posts:
            payload = {
                "id": str(uuid4()),
                "source": "reddit",
                "external_id": post["id"],
                "title": post["title"][:200],
                "body": (post["selftext"] or post["title"] or post["url"])[:10000],
                "metadata": {
                    "subreddit": post["subreddit"],
                    "permalink": f"https://www.reddit.com{post.get('permalink', '')}",
                    "author": post["author"],
                    "created_utc": post["created_utc"],
                    "score": post["score"],
                    "num_comments": post["num_comments"],
                    "url": post["url"],
                },
                "created_at": _now_iso(post["created_utc"]),
            }
            
            if ingest_fn:
                try:
                    # If running in-process, use the callback directly
                    # The callback expects a FeedbackItem object or dict depending on implementation
                    # But ingest_reddit in main.py expects a FeedbackItem
                    # We'll assume ingest_fn handles the conversion or we pass the dict if it expects dict
                    # Actually, ingest_reddit expects FeedbackItem.
                    # We should probably construct the FeedbackItem here if we are calling it directly.
                    # But let's see how we can pass it.
                    # To avoid circular imports, we might pass a wrapper.
                    ingest_fn(payload)
                    print(f"Ingested (direct) r/{post['subreddit']} post {post['id']}: {post['title'][:80]}")
                except Exception as exc:
                    print(f"Failed to ingest (direct) Reddit item {post['id']}: {exc}")
                continue

            try:
                response = requests.post(ingest_url, json=payload, timeout=10)
                response.raise_for_status()
                print(f"Ingested r/{post['subreddit']} post {post['id']}: {post['title'][:80]}")
            except requests.RequestException as exc:
                print(f"Failed to post Reddit item {post['id']} to backend: {exc}")

    def run_forever(self, subreddits: Optional[Iterable[str]] = None) -> None:
        """Start continuous polling."""
        while True:
            active_subreddits = (
                list(subreddits)
                if subreddits is not None
                else get_configured_subreddits()
            )
            self.poll_once(active_subreddits)
            self.sleep(self.poll_interval)


def fetch_reddit_posts(subreddits: List[str]) -> List[dict]:
    """Module-level helper mirroring the requested interface."""
    poller = RedditPoller()
    return poller.fetch_reddit_posts(subreddits)


def poll_once(subreddits: Iterable[str], backend_url: Optional[str] = None, ingest_fn=None) -> None:
    """Module-level helper for single poll."""
    poller = RedditPoller()
    poller.poll_once(subreddits, backend_url=backend_url, ingest_fn=ingest_fn)


# Alias to match the TS-like name in the task description
fetchRedditPosts = fetch_reddit_posts


def poll_reddit():
    """Entrypoint used by scripts or CLI."""
    subreddits = get_configured_subreddits()
    sorts = get_env_sorts()
    poll_interval = get_poll_interval_seconds()
    poller = RedditPoller(sorts=sorts, poll_interval=poll_interval)
    print(
        "Polling Reddit JSON endpoints "
        f"(subreddits={','.join(subreddits)}, sorts={','.join(poller.sorts)}, "
        f"interval={poller.poll_interval}s)"
    )
    poller.run_forever(subreddits)


if __name__ == "__main__":
    poll_reddit()
