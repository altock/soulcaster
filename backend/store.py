"""Storage layer for FeedbackItems and IssueClusters.

Defaults to in-memory dicts, but will use Redis if configured (Upstash-friendly).
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union
from uuid import UUID

# Project ID can be UUID or CUID string from the dashboard
ProjectId = Union[UUID, str]

import requests

from models import FeedbackItem, IssueCluster, AgentJob, Project, User, ClusterJob, CodingPlan

try:
    import redis  # type: ignore
except ImportError:
    redis = None

logger = logging.getLogger(__name__)


def _dt_to_iso(dt: datetime) -> str:
    return dt.isoformat()


def _iso_to_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _strip_quotes(value: Optional[str]) -> Optional[str]:
    """Strip surrounding quotes from environment variable values."""
    if value is None:
        return None
    # Strip single or double quotes from both ends
    return value.strip('"').strip("'")


# ---------- Redis (standard) client helpers ----------


def _redis_client_from_env():
    """Return a redis-py client if REDIS_URL/UPSTASH_REDIS_URL is set."""
    url = _strip_quotes(os.getenv("REDIS_URL") or os.getenv("UPSTASH_REDIS_URL"))
    if not url or not redis:
        return None
    return redis.from_url(url, decode_responses=True)


# ---------- Upstash REST client (fallback when redis-py URL not provided) ----------


class UpstashRESTClient:
    """Minimal Upstash REST wrapper for the commands we need."""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.session = requests.Session()

    def _cmd(self, *args: str):
        resp = self.session.post(
            self.base_url,
            headers={"Authorization": f"Bearer {self.token}"},
            json=list(args),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("result")

    def pipeline_exec(self, commands: List[List[str]]) -> List[Any]:
        """
        Execute multiple Redis commands in a single HTTP request using Upstash pipelining.
        
        Parameters:
            commands: List of commands, each command is a list of strings
                      e.g. [["HGETALL", "key1"], ["HGETALL", "key2"]]
        
        Returns:
            List of results, one per command. Each result contains {"result": ...} or {"error": ...}
        """
        if not commands:
            return []
        resp = self.session.post(
            f"{self.base_url}/pipeline",
            headers={"Authorization": f"Bearer {self.token}"},
            json=commands,
            timeout=30,  # Longer timeout for batch operations
        )
        resp.raise_for_status()
        results = resp.json()
        # Results are in format [{"result": ...}, {"result": ...}, ...]
        return [r.get("result") for r in results]

    def hgetall_batch(self, keys: List[str]) -> List[Dict[str, str]]:
        """
        Batch fetch multiple hashes in a single pipeline request.
        
        Parameters:
            keys: List of Redis hash keys to fetch
        
        Returns:
            List of dicts, one per key. Empty dict if key doesn't exist or has invalid data.
        """
        if not keys:
            return []
        commands = [["HGETALL", key] for key in keys]
        results = self.pipeline_exec(commands)
        parsed = []
        for result in results:
            if not result:
                parsed.append({})
            elif len(result) % 2 != 0:
                # Invalid response: odd number of elements, skip this entry
                logger.warning("HGETALL returned odd number of elements, skipping")
                parsed.append({})
            else:
                # Convert list to dict: ["field1", "value1", ...] -> {"field1": "value1", ...}
                parsed.append(dict(zip(result[0::2], result[1::2])))
        return parsed

    def set(self, key: str, value: str):
        """
        Set a string value for a Redis key using the Upstash REST client.
        
        Parameters:
            key (str): Redis key to set.
            value (str): String value to store at the key.
        
        Returns:
            The raw Redis reply from the SET command (for example, "OK").
        """
        return self._cmd("SET", key, value)

    def set_with_opts(self, key: str, value: str, *options: str):
        """
        Execute SET with additional options (e.g., NX/EX) supported by Upstash REST.
        """
        return self._cmd("SET", key, value, *options)

    def get(self, key: str) -> Optional[str]:
        """
        Fetch the string value stored at a Redis key via the REST client.
        
        Parameters:
            key (str): Redis key to fetch.
        
        Returns:
            Optional[str]: The string value for the key, or `None` if the key does not exist.
        """
        return self._cmd("GET", key)

    def hset(self, key: str, mapping: Dict[str, Any]):
        # Upstash REST HSET supports: ["HSET", key, field1, value1, field2, value2, ...]
        args = ["HSET", key]
        for field, value in mapping.items():
            args.extend([field, str(value)])
        return self._cmd(*args)

    def hgetall(self, key: str) -> Dict[str, str]:
        # Upstash REST HGETALL returns ["field1", "value1", ...]
        result = self._cmd("HGETALL", key)
        if not result:
            return {}
        # Convert list to dict
        return dict(zip(result[0::2], result[1::2]))

    def zadd(self, key: str, score: float, member: str):
        return self._cmd("ZADD", key, str(score), member)

    def zrange(self, key: str, start: int, stop: int, rev: bool = False) -> List[str]:
        args = ["ZRANGE", key, str(start), str(stop)]
        if rev:
            args.append("REV")
        result = self._cmd(*args)
        return result or []

    def rpush(self, key: str, *values: str) -> int:
        """
        Append one or more values to the end of a Redis list.

        Returns:
            int: The length of the list after the push.
        """
        if not values:
            return 0
        return int(self._cmd("RPUSH", key, *values) or 0)

    def lrange(self, key: str, start: int, stop: int) -> List[str]:
        """
        Return a range of elements from a Redis list.
        """
        result = self._cmd("LRANGE", key, str(start), str(stop))
        return result or []

    def llen(self, key: str) -> int:
        """
        Return the length of a Redis list.
        """
        return int(self._cmd("LLEN", key) or 0)

    def expire(self, key: str, seconds: int) -> int:
        """
        Set an expire (TTL) on a key.
        """
        return int(self._cmd("EXPIRE", key, str(int(seconds))) or 0)

    def sadd(self, key: str, member: str):
        return self._cmd("SADD", key, member)

    def smembers(self, key: str) -> List[str]:
        """
        Retrieve all members of the Redis set stored at the given key.
        
        Returns:
            List[str]: Members of the set as strings; empty list if the key does not exist or the set is empty.
        """
        result = self._cmd("SMEMBERS", key)
        return result or []

    def srem(self, key: str, member: str):
        """
        Remove a member from the Redis set stored at `key`.
        
        Parameters:
            key (str): Redis key of the set.
            member (str): Member value to remove from the set.
        
        Returns:
            int: The number of members that were removed (0 if the member was not present).
        """
        return self._cmd("SREM", key, member)

    def delete(self, *keys: str):
        """
        Delete one or more Redis keys via the Upstash REST client.
        
        Parameters:
            keys (str): One or more Redis keys to delete.
        
        Returns:
            number_deleted (int): The number of keys that were removed.
        """
        if not keys:
            return 0
        return self._cmd("DEL", *keys)

    def scan_iter(self, pattern: str, count: int = 100) -> Iterable[str]:
        cursor = "0"
        while True:
            result = self._cmd("SCAN", cursor, "MATCH", pattern, "COUNT", str(count))
            cursor = result[0]
            for key in result[1]:
                yield key
            if cursor == "0":
                break


def _upstash_rest_client_from_env():
    url = _strip_quotes(os.getenv("UPSTASH_REDIS_REST_URL"))
    token = _strip_quotes(os.getenv("UPSTASH_REDIS_REST_TOKEN"))
    if url and token:
        return UpstashRESTClient(url, token)
    return None


# ---------- Store backends ----------


class InMemoryStore:
    def __init__(self):
        """
        Create an in-memory storage backend for feedback, clusters, jobs, projects, users, and related indices.
        
        Attributes:
            feedback_items: dict mapping feedback UUID -> FeedbackItem.
            issue_clusters: dict mapping cluster ID (str) -> IssueCluster.
            agent_jobs: dict mapping job UUID -> AgentJob.
            projects: dict mapping project ID (str) -> Project.
            users: dict mapping user ID (str) -> User.
            reddit_subreddits: dict mapping project ID (str) -> list of subreddit names.
            external_index: dict mapping (project_id, source, external_id) -> feedback UUID for deduplication/lookup.
            unclustered_feedback_ids: dict mapping project ID (str) -> set of feedback UUIDs not assigned to any cluster.
            cluster_jobs: dict mapping cluster job ID (str) -> ClusterJob.
            cluster_job_index: dict mapping project ID (str) -> list of cluster job IDs (recent ordering).
            cluster_locks: dict mapping project ID (str) -> lock owner/job ID (str) for in-memory lock tracking.
        """
        self.feedback_items: Dict[UUID, FeedbackItem] = {}
        self.issue_clusters: Dict[str, IssueCluster] = {}
        self.coding_plans: Dict[str, CodingPlan] = {}  # cluster_id -> CodingPlan
        self.agent_jobs: Dict[UUID, AgentJob] = {}
        self.job_logs: Dict[UUID, List[str]] = {}
        self.projects: Dict[str, Project] = {}
        self.users: Dict[str, User] = {}
        self.reddit_subreddits: Dict[str, List[str]] = {}
        self.datadog_webhook_secrets: Dict[str, str] = {}
        self.datadog_monitors: Dict[str, List[str]] = {}
        self.external_index: Dict[Tuple[str, str, str], UUID] = {}
        # Track unclustered feedback per project (project_id -> set(feedback_ids))
        self.unclustered_feedback_ids: Dict[str, set[UUID]] = {}
        # Cluster jobs and locks (in-memory)
        self.cluster_jobs: Dict[str, ClusterJob] = {}
        self.cluster_job_index: Dict[str, List[str]] = {}
        self.cluster_locks: Dict[str, str] = {}
        # Generic key-value config storage
        self.config: Dict[str, str] = {}

    # Feedback
    def add_feedback_item(self, item: FeedbackItem) -> FeedbackItem:
        """
        Add a FeedbackItem to the store, index it by external_id if present, and mark it as unclustered.
        
        Parameters:
            item (FeedbackItem): Feedback item to store.
        
        Returns:
            FeedbackItem: The stored feedback item; if an item with the same (project_id, source, external_id) already exists, returns that existing item.
        """
        # Allow either UUID or string identifiers; skip strict project existence check in-memory
        project_key = str(item.project_id)
        if item.external_id:
            key = (project_key, item.source, item.external_id)
            existing_id = self.external_index.get(key)
            if existing_id:
                return self.feedback_items[existing_id]
            self.external_index[key] = item.id
        self.feedback_items[item.id] = item
        # Add to unclustered set (Phase 1: ingestion moat)
        self.unclustered_feedback_ids.setdefault(project_key, set()).add(item.id)
        return item

    def get_feedback_item(self, project_id: str, item_id: UUID) -> Optional[FeedbackItem]:
        """
        Retrieve a feedback item by its UUID within a project scope.
        
        Returns:
            `FeedbackItem` if an item with the given `item_id` exists and belongs to the project, `None` otherwise.
        """
        item = self.feedback_items.get(item_id)
        if item and str(item.project_id) == str(project_id):
            return item
        return None

    def get_all_feedback_items(self, project_id: Optional[str] = None) -> List[FeedbackItem]:
        """
        Get all stored feedback items.
        
        Returns:
            list[FeedbackItem]: All FeedbackItem instances currently held in the store.
        """
        if project_id is None:
            return list(self.feedback_items.values())
        return [
            item for item in self.feedback_items.values() if str(item.project_id) == str(project_id)
        ]

    def get_unclustered_feedback(self, project_id: str) -> List[FeedbackItem]:
        """
        Return feedback items for a project that have not been assigned to any cluster.
        
        Returns:
            List[FeedbackItem]: FeedbackItem objects from the project's unclustered set (existing items only).
        """
        key = str(project_id)
        project_unclustered = self.unclustered_feedback_ids.get(key, set())
        return [
            self.feedback_items[item_id]
            for item_id in project_unclustered
            if item_id in self.feedback_items
        ]

    def remove_from_unclustered(self, feedback_id: UUID, project_id: str):
        """
        Remove a feedback item's ID from the project's unclustered set.
        
        Parameters:
            feedback_id (UUID): ID of the feedback item to remove.
            project_id (UUID): ID of the project whose unclustered set will be modified.
        
        Behavior:
            Performs a no-op if the project does not exist or the feedback ID is not present in the set.
        """
        key = str(project_id)
        if key in self.unclustered_feedback_ids:
            self.unclustered_feedback_ids[key].discard(feedback_id)

    def update_feedback_item(self, project_id: str, item_id: UUID, **updates) -> FeedbackItem:
        """
        Update mutable fields of a feedback item and return the updated object.
        """
        existing = self.feedback_items.get(item_id)
        if not existing:
            raise KeyError("feedback not found")
        # Verify project scoping: ensure the item belongs to the given project
        if str(existing.project_id) != str(project_id):
            raise KeyError(f"Feedback {item_id} not found for project {project_id}")
        updated = existing.model_copy(update=updates)
        self.feedback_items[item_id] = updated
        return updated

    def get_feedback_by_external_id(self, project_id: str, source: str, external_id: str) -> Optional[FeedbackItem]:
        """
        Lookup a feedback item by project, source, and external_id (in-memory).
        """
        key = (str(project_id), source, external_id)
        feedback_id = self.external_index.get(key)
        if feedback_id:
            return self.feedback_items.get(feedback_id)
        # Fallback scan
        for item in self.feedback_items.values():
            if str(item.project_id) == str(project_id) and item.source == source and item.external_id == external_id:
                return item
        return None

    def clear_feedback_items(self, project_id: Optional[str] = None):
        """
        Remove stored feedback-related data. If project_id is provided, clear only that project's
        feedback; otherwise clear all feedback (backwards-compatible for tests/cleanup).
        
        This clears feedback_items, the external_id index, and the set tracking unclustered feedback IDs.
        """
        if project_id:
            # Drop feedback for the given project_id
            ids_to_delete = [fid for fid, item in self.feedback_items.items() if str(item.project_id) == str(project_id)]
            for fid in ids_to_delete:
                self.feedback_items.pop(fid, None)
            # Rebuild external index and unclustered sets to avoid stale entries
            self.external_index = {
                k: v for k, v in self.external_index.items() if str(k[0]) != str(project_id)
            }
            self.unclustered_feedback_ids.pop(project_id, None)
        else:
            self.feedback_items.clear()
            self.external_index.clear()
            self.unclustered_feedback_ids.clear()

    def delete_feedback_item(self, project_id: str, item_id: UUID) -> bool:
        """
        Delete a feedback item and remove it from all indexes.

        Parameters:
            project_id (str): ID of the project the item belongs to.
            item_id (UUID): ID of the feedback item to delete.

        Returns:
            bool: True if item was deleted, False if not found.
        """
        item = self.feedback_items.get(item_id)
        if not item or str(item.project_id) != str(project_id):
            return False

        # Remove from main store
        del self.feedback_items[item_id]

        # Remove from external index
        if item.external_id:
            key = (str(project_id), item.source, item.external_id)
            self.external_index.pop(key, None)

        # Remove from unclustered set
        self.remove_from_unclustered(item_id, project_id)

        return True

    # Clusters
    def add_cluster(self, cluster: IssueCluster) -> IssueCluster:
        """
        Store the provided IssueCluster in the backend store.
        
        Parameters:
        	cluster (IssueCluster): IssueCluster to persist; it will be stored keyed by its `id`.
        
        Returns:
        	IssueCluster: The stored cluster instance.
        """
        self.issue_clusters[cluster.id] = cluster
        return cluster

    def get_cluster(self, project_id: Optional[str], cluster_id: str) -> Optional[IssueCluster]:
        """
        In-memory cluster lookup with optional project scoping.
        Accepts project_id=None for backwards-compat calls.
        """
        cluster = self.issue_clusters.get(cluster_id)
        if not cluster:
            return None
        if project_id is None:
            return cluster
        return cluster if str(cluster.project_id) == str(project_id) else None

    def get_all_clusters(self, project_id: Optional[str] = None) -> List[IssueCluster]:
        """
        In-memory cluster listing with optional project scoping.
        """
        if project_id is None:
            return list(self.issue_clusters.values())
        return [c for c in self.issue_clusters.values() if str(c.project_id) == str(project_id)]

    def update_cluster(self, project_id: Optional[str], cluster_id: str, **updates) -> IssueCluster:
        cluster = self.issue_clusters[cluster_id]
        if project_id is not None and str(cluster.project_id) != str(project_id):
            raise KeyError(f"Cluster {cluster_id} not found for project {project_id}")
        updated_cluster = cluster.model_copy(update=updates)
        self.issue_clusters[cluster_id] = updated_cluster
        return updated_cluster

    def clear_clusters(self, project_id: Optional[str] = None):
        """
        Remove stored issue clusters. If project_id is provided, remove clusters for that project;
        otherwise remove all clusters (backwards-compatible for tests/cleanup).
        """
        if project_id:
            ids_to_delete = [
                cid for cid, cluster in self.issue_clusters.items() if str(cluster.project_id) == str(project_id)
            ]
            for cid in ids_to_delete:
                self.issue_clusters.pop(cid, None)
        else:
            self.issue_clusters.clear()


    # Coding Plans
    def add_coding_plan(self, plan: CodingPlan) -> CodingPlan:
        """
        Store a CodingPlan in the in-memory store.
        """
        self.coding_plans[plan.cluster_id] = plan
        return plan

    def get_coding_plan(self, cluster_id: str) -> Optional[CodingPlan]:
        """
        Retrieve a CodingPlan by cluster_id.
        """
        return self.coding_plans.get(cluster_id)

    # Config (Reddit)
    def set_reddit_subreddits(self, subreddits: List[str], project_id: ProjectId) -> List[str]:
        """
        Set the list of Reddit subreddits for a project.
        
        Parameters:
            subreddits (List[str]): Ordered list of subreddit names to associate with the project.
            project_id (UUID): Identifier of the project to update.
        
        Returns:
            List[str]: The same list of subreddits that was stored.
        
        Raises:
            KeyError: If no project exists with the given `project_id`.
        """
        pid_str = str(project_id)
        if pid_str not in self.projects:
            raise KeyError("project not found")
        self.reddit_subreddits[pid_str] = subreddits
        return subreddits

    def get_reddit_subreddits(self, project_id: ProjectId) -> Optional[List[str]]:
        """
        Retrieve the configured Reddit subreddit names for a project.
        
        Returns:
            List[str]: The subreddit names for the project, or `None` if no configuration exists.
        """
        return self.reddit_subreddits.get(str(project_id))

    def clear_config(self):
        """
        Remove all stored integration configuration for all projects.

        This clears any per-project subreddit lists and integration settings so subsequent lookups return no configuration.
        """
        self.reddit_subreddits = {}
        # Also clear Sentry config
        if hasattr(self, "sentry_config"):
            self.sentry_config = {}
        if hasattr(self, "splunk_config"):
            self.splunk_config = {}
        if hasattr(self, "datadog_config"):
            self.datadog_config = {}
        if hasattr(self, "posthog_config"):
            self.posthog_config = {}
        self.datadog_webhook_secrets = {}
        self.datadog_monitors = {}

    # Config (Sentry)
    def set_sentry_config(self, project_id: ProjectId, key: str, value: Any) -> None:
        """
        Set a Sentry configuration value for a project.

        Parameters:
            project_id (ProjectId): Project identifier.
            key (str): Config key (e.g., "webhook_secret", "environments", "levels").
            value (Any): Config value to store.
        """
        pid_str = str(project_id)
        if not hasattr(self, "sentry_config"):
            self.sentry_config = {}
        if pid_str not in self.sentry_config:
            self.sentry_config[pid_str] = {}
        self.sentry_config[pid_str][key] = value

    def get_sentry_config(self, project_id: ProjectId, key: str) -> Optional[Any]:
        """
        Get a Sentry configuration value for a project.

        Parameters:
            project_id (ProjectId): Project identifier.
            key (str): Config key to retrieve.

        Returns:
            Optional[Any]: Config value if it exists, None otherwise.
        """
        if not hasattr(self, "sentry_config"):
            self.sentry_config = {}
        pid_str = str(project_id)
        project_config = self.sentry_config.get(pid_str, {})
        return project_config.get(key)

    def set_splunk_config(self, project_id: ProjectId, key: str, value: Any) -> None:
        """
        Set a Splunk configuration value for a project.

        Parameters:
            project_id (ProjectId): Project identifier.
            key (str): Config key (e.g., "webhook_token", "allowed_searches", "enabled").
            value (Any): Config value to store.
        """
        pid_str = str(project_id)
        if not hasattr(self, "splunk_config"):
            self.splunk_config = {}
        if pid_str not in self.splunk_config:
            self.splunk_config[pid_str] = {}
        self.splunk_config[pid_str][key] = value

    def get_splunk_config(self, project_id: ProjectId, key: str) -> Optional[Any]:
        """
        Get a Splunk configuration value for a project.

        Parameters:
            project_id (ProjectId): Project identifier.
            key (str): Config key to retrieve.

        Returns:
            Optional[Any]: Config value if it exists, None otherwise.
        """
        if not hasattr(self, "splunk_config"):
            self.splunk_config = {}
        pid_str = str(project_id)
        project_config = self.splunk_config.get(pid_str, {})
        return project_config.get(key)

    def set_datadog_config(self, project_id: ProjectId, key: str, value: Any) -> None:
        """
        Set a Datadog configuration value for a project.

        Parameters:
            project_id (ProjectId): Project identifier.
            key (str): Config key (e.g., "webhook_secret", "monitors", "enabled").
            value (Any): Config value to store.
        """
        pid_str = str(project_id)
        if not hasattr(self, "datadog_config"):
            self.datadog_config = {}
        if pid_str not in self.datadog_config:
            self.datadog_config[pid_str] = {}
        self.datadog_config[pid_str][key] = value

    def get_datadog_config(self, project_id: ProjectId, key: str) -> Optional[Any]:
        """
        Get a Datadog configuration value for a project.

        Parameters:
            project_id (ProjectId): Project identifier.
            key (str): Config key to retrieve.

        Returns:
            Optional[Any]: Config value if it exists, None otherwise.
        """
        if not hasattr(self, "datadog_config"):
            self.datadog_config = {}
        pid_str = str(project_id)
        project_config = self.datadog_config.get(pid_str, {})
        return project_config.get(key)

    def set_posthog_config(self, project_id: ProjectId, key: str, value: Any) -> None:
        """
        Set a PostHog configuration value for a project.

        Parameters:
            project_id (ProjectId): Project identifier.
            key (str): Config key (e.g., "event_types", "enabled").
            value (Any): Config value to store.
        """
        pid_str = str(project_id)
        if not hasattr(self, "posthog_config"):
            self.posthog_config = {}
        if pid_str not in self.posthog_config:
            self.posthog_config[pid_str] = {}
        self.posthog_config[pid_str][key] = value

    def get_posthog_config(self, project_id: ProjectId, key: str) -> Optional[Any]:
        """
        Get a PostHog configuration value for a project.

        Parameters:
            project_id (ProjectId): Project identifier.
            key (str): Config key to retrieve.

        Returns:
            Optional[Any]: Config value if it exists, None otherwise.
        """
        if not hasattr(self, "posthog_config"):
            self.posthog_config = {}
        pid_str = str(project_id)
        project_config = self.posthog_config.get(pid_str, {})
        return project_config.get(key)

        self.datadog_webhook_secrets = {}
        self.datadog_monitors = {}

    # Config (Datadog)
    def set_datadog_webhook_secret(self, secret: str, project_id: ProjectId) -> str:
        """
        Set the Datadog webhook secret for a specific project.

        Parameters:
            secret (str): Webhook secret to use for signature verification.
            project_id (UUID): Identifier of the project to associate the secret with.

        Returns:
            str: The secret that was stored.
        """
        pid_str = str(project_id)
        if pid_str not in self.projects:
            raise KeyError("project not found")
        self.datadog_webhook_secrets[pid_str] = secret
        return secret

    def get_datadog_webhook_secret(self, project_id: ProjectId) -> Optional[str]:
        """
        Retrieve the configured Datadog webhook secret for a project.

        Returns:
            str: The webhook secret for the project, or None if no secret is configured.
        """
        return self.datadog_webhook_secrets.get(str(project_id))

    def set_datadog_monitors(self, monitors: List[str], project_id: ProjectId) -> List[str]:
        """
        Set the list of Datadog monitor IDs to track for a project.

        Parameters:
            monitors (List[str]): List of monitor IDs or ["*"] for all monitors.
            project_id (UUID): Identifier of the project to associate the monitors with.

        Returns:
            List[str]: The list of monitor IDs that was stored.
        """
        pid_str = str(project_id)
        if pid_str not in self.projects:
            raise KeyError("project not found")
        self.datadog_monitors[pid_str] = monitors
        return monitors

    def get_datadog_monitors(self, project_id: ProjectId) -> Optional[List[str]]:
        """
        Retrieve the configured Datadog monitor IDs for a project.

        Returns:
            List[str]: The monitor IDs for the project, or None if no configuration exists.
        """
        return self.datadog_monitors.get(str(project_id))

    # Jobs
    def add_job(self, job: AgentJob) -> AgentJob:
        """
        Add an AgentJob to the store for its associated project.
        
        Parameters:
            job (AgentJob): Job to store; its project_id must reference an existing project.
        
        Returns:
            AgentJob: The stored job object.
        
        Raises:
            KeyError: If the job's project_id does not exist.
        """
        # Do not enforce project existence for in-memory tests; allow ad-hoc jobs
        self.agent_jobs[job.id] = job
        return job

    def get_job(self, job_id: UUID) -> Optional[AgentJob]:
        return self.agent_jobs.get(job_id)

    def update_job(self, job_id: UUID, **updates) -> AgentJob:
        job = self.agent_jobs[job_id]
        updated_job = job.model_copy(update=updates)
        self.agent_jobs[job_id] = updated_job
        return updated_job

    def append_job_log(self, job_id: UUID, message: str) -> None:
        self.job_logs.setdefault(job_id, []).append(message)

    def get_job_logs(self, job_id: UUID, cursor: int = 0, limit: int = 200) -> tuple[list[str], int, bool]:
        lines = self.job_logs.get(job_id, [])
        if cursor < 0:
            cursor = 0
        if limit <= 0:
            return ([], cursor, False)
        end = min(len(lines), cursor + limit)
        chunk = lines[cursor:end]
        next_cursor = end
        has_more = next_cursor < len(lines)
        return (chunk, next_cursor, has_more)

    def get_jobs_by_cluster(self, cluster_id: str) -> List[AgentJob]:
        return [
            job for job in self.agent_jobs.values() if job.cluster_id == cluster_id
        ]

    def get_all_jobs(self) -> List[AgentJob]:
        return list(self.agent_jobs.values())

    def clear_jobs(self):
        """
        Clear all AgentJob entries from this store.
        
        This removes every AgentJob from the in-memory job mapping.
        """
        self.agent_jobs.clear()
        self.job_logs.clear()

    # Cluster Jobs (clustering runner)
    def add_cluster_job(self, job: ClusterJob) -> ClusterJob:
        """
        Store a ClusterJob in the in-memory cluster job store and mark it as the most recent entry for its project.
        
        Parameters:
            job (ClusterJob): Cluster job to add or update in the store.
        
        Returns:
            ClusterJob: The stored ClusterJob.
        """
        job_id = str(job.id)
        pid = str(job.project_id)
        self.cluster_jobs[job_id] = job
        self.cluster_job_index.setdefault(pid, [])
        # maintain most recent first
        self.cluster_job_index[pid] = [job_id] + [
            jid for jid in self.cluster_job_index[pid] if jid != job_id
        ]
        return job

    def get_cluster_job(self, project_id: str, job_id: str) -> Optional[ClusterJob]:
        """
        Retrieve the cluster job with the given ID if it belongs to the specified project.
        
        Parameters:
            project_id (str): Project identifier to scope the lookup.
            job_id (str): Cluster job identifier.
        
        Returns:
            ClusterJob or None: The matching ClusterJob when it exists and is scoped to `project_id`, otherwise `None`.
        """
        job = self.cluster_jobs.get(job_id)
        if job and str(job.project_id) == str(project_id):
            return job
        return None

    def list_cluster_jobs(self, project_id: str, limit: int = 20) -> List[ClusterJob]:
        """
        Return recent cluster jobs for a specific project.
        
        Parameters:
        	project_id (str): Project identifier to scope the cluster jobs.
        	limit (int): Maximum number of cluster jobs to return.
        
        Returns:
        	list[ClusterJob]: Up to `limit` ClusterJob objects for the project in the store's recorded order.
        """
        ids = self.cluster_job_index.get(str(project_id), [])
        return [self.cluster_jobs[jid] for jid in ids[:limit] if jid in self.cluster_jobs]

    def update_cluster_job(self, project_id: str, job_id: str, **updates) -> ClusterJob:
        """
        Update fields of an existing ClusterJob and persist the updated job.
        
        Parameters:
            project_id (str): Identifier of the project that owns the cluster job.
            job_id (str): Identifier of the cluster job to update.
            **updates: Fields to merge into the existing ClusterJob; keys should match ClusterJob model attributes.
        
        Returns:
            ClusterJob: The persisted ClusterJob after applying the updates.
        
        Raises:
            KeyError: If no ClusterJob with the given job_id exists for the specified project_id.
        """
        existing = self.get_cluster_job(project_id, job_id)
        if not existing:
            raise KeyError(f"ClusterJob {job_id} not found for project {project_id}")
        updated = existing.model_copy(update=updates)
        return self.add_cluster_job(updated)

    def acquire_cluster_lock(self, project_id: str, job_id: str, ttl_seconds: int = 600) -> bool:
        """
        Acquire a non-expiring lock for a cluster job within a project.
        
        Attempts to acquire a lock scoped to the given project; if no lock is held, records this job_id as the lock holder and returns success. The in-memory implementation does not enforce TTL — the `ttl_seconds` parameter is accepted for API compatibility but is ignored; the lock remains until released via `release_cluster_lock`.
        
        Parameters:
            project_id (str): The project identifier to lock.
            job_id (str): The cluster job identifier attempting to hold the lock.
            ttl_seconds (int): Requested lock time-to-live in seconds (ignored by the in-memory store).
        
        Returns:
            bool: `true` if the lock was acquired, `false` otherwise.
        """
        key = str(project_id)
        holder = self.cluster_locks.get(key)
        if holder:
            return False
        self.cluster_locks[key] = job_id
        return True

    def release_cluster_lock(self, project_id: str, job_id: str):
        """
        Release the cluster lock for a project if it is currently held by the given job.
        
        Parameters:
            project_id (str): ID of the project whose lock should be released.
            job_id (str): ID of the job expected to own the lock; the lock is removed only if this matches the current owner.
        """
        key = str(project_id)
        if self.cluster_locks.get(key) == job_id:
            self.cluster_locks.pop(key, None)

    # Users / Projects
    def create_user_with_default_project(self, user: User, default_project: Project) -> Project:
        """
        Create a user record and its default project in the in-memory store.
        
        Returns:
            The stored default project.
        """
        self.users[str(user.id)] = user
        self.projects[str(default_project.id)] = default_project
        return default_project

    def create_project(self, project: Project) -> Project:
        """
        Store the given Project in the in-memory store and return it.
        
        Parameters:
            project (Project): Project to add; stored under project.id.
        
        Returns:
            Project: The stored project instance.
        """
        self.projects[str(project.id)] = project
        return project

    def get_projects_for_user(self, user_id: UUID | str) -> List[Project]:
        """
        Retrieve all projects owned by the given user.
        
        Parameters:
            user_id (UUID): ID of the user whose projects to retrieve.
        
        Returns:
            List[Project]: Projects belonging to the specified user (empty list if none).
        """
        uid = str(user_id)
        return [p for p in self.projects.values() if str(p.user_id) == uid]

    def get_project(self, project_id: UUID | str) -> Optional[Project]:
        """
        Retrieve a project by its identifier.

        Returns:
            Project or None: The Project with the given `project_id` if it exists, otherwise `None`.
        """
        return self.projects.get(str(project_id))

    # Generic key-value config methods
    def get(self, key: str) -> Optional[str]:
        """
        Retrieve a configuration value by key.

        Args:
            key: Configuration key.

        Returns:
            str or None: The value if it exists, otherwise None.
        """
        return self.config.get(key)

    def set(self, key: str, value: str) -> None:
        """
        Set a configuration value.

        Args:
            key: Configuration key.
            value: Configuration value to store.
        """
        self.config[key] = value


class RedisStore:
    """Redis-backed implementation (works with Upstash REST or redis-py)."""

    def __init__(self):
        client = _redis_client_from_env()
        self.mode = "redis" if client else "rest"
        if client:
            self.client = client
        else:
            rest_client = _upstash_rest_client_from_env()
            if not rest_client:
                raise RuntimeError("RedisStore requires REDIS_URL/UPSTASH_REDIS_URL or UPSTASH_REDIS_REST_URL/_TOKEN")
            self.client = rest_client

    # Key helpers - MUST match dashboard/lib/redis.ts patterns!
    @staticmethod
    def _feedback_key(project_id: str, item_id: Union[UUID, str]) -> str:
        """Match dashboard: feedback:${projectId}:${id}"""
        return f"feedback:{project_id}:{item_id}"

    @staticmethod
    def _feedback_created_key(project_id: str) -> str:
        """Match dashboard: feedback:created:${projectId}"""
        return f"feedback:created:{project_id}"

    @staticmethod
    def _feedback_source_key(project_id: str, source: str) -> str:
        """Match dashboard: feedback:source:${projectId}:${source}"""
        return f"feedback:source:{project_id}:{source}"

    @staticmethod
    def _feedback_external_key(project_id: str, source: str, external_id: str) -> str:
        """
        Constructs the Redis key used to map an external feedback identifier to a feedback item.
        
        Parameters:
            project_id (str): UUID or identifier of the project.
            source (str): Source system name (e.g., "github", "zendesk").
            external_id (str): The external system's identifier for the feedback item.
        
        Returns:
            str: Redis key in the form "feedback:external:{project_id}:{source}:{external_id}".
        """
        return f"feedback:external:{project_id}:{source}:{external_id}"

    @staticmethod
    def _feedback_unclustered_key(project_id: str) -> str:
        """Match dashboard: feedback:unclustered:${projectId}"""
        return f"feedback:unclustered:{project_id}"

    @staticmethod
    def _cluster_key(project_id: str, cluster_id: str) -> str:
        """Match dashboard: cluster:${projectId}:${id}"""
        return f"cluster:{project_id}:{cluster_id}"

    @staticmethod
    def _cluster_items_key(project_id: str, cluster_id: str) -> str:
        """Match dashboard: cluster:${projectId}:${clusterId}:items"""
        return f"cluster:{project_id}:{cluster_id}:items"

    @staticmethod
    def _cluster_all_key(project_id: str) -> str:
        """
        Builds the Redis key for a project's set of all clusters.
        
        Returns:
            str: Redis key in the format "clusters:<project_id>:all".
        """
        return f"clusters:{project_id}:all"

    @staticmethod
    def _cluster_job_key(project_id: str, job_id: str) -> str:
        """
        Builds the Redis key used to store a cluster job's metadata.
        
        Parameters:
            project_id (str): Project identifier to scope the cluster job.
            job_id (str): Cluster job identifier.
        
        Returns:
            key (str): Redis key in the form "cluster_job:<project_id>:<job_id>".
        """
        return f"cluster_job:{project_id}:{job_id}"

    @staticmethod
    def _cluster_jobs_recent_key(project_id: str) -> str:
        """
        Return the Redis key for the sorted set of recent clustering jobs for a project.
        
        Parameters:
            project_id (str): Project identifier.
        
        Returns:
            key (str): Redis key in the form "cluster_jobs:<project_id>:recent".
        """
        return f"cluster_jobs:{project_id}:recent"

    @staticmethod
    def _coding_plan_key(cluster_id: str) -> str:
        """Match dashboard: coding_plan:{clusterId}"""
        return f"coding_plan:{cluster_id}"

    def add_coding_plan(self, plan: CodingPlan) -> CodingPlan:
        """
        Store a CodingPlan in Redis.
        """
        key = self._coding_plan_key(plan.cluster_id)
        self.client.set(key, plan.model_dump_json())
        return plan

    def get_coding_plan(self, cluster_id: str) -> Optional[CodingPlan]:
        """
        Retrieve a CodingPlan from Redis.
        """
        key = self._coding_plan_key(cluster_id)
        data = self.client.get(key)
        if not data:
            return None
        return CodingPlan.model_validate_json(data)

    @staticmethod
    def _cluster_lock_key(project_id: str) -> str:
        """
        Builds the Redis key used for per-project cluster locking.
        
        Returns:
            key (str): Redis key string for the cluster lock for the given project.
        """
        return f"cluster:lock:{project_id}"

    @staticmethod
    def _reddit_subreddits_key(project_id: UUID) -> str:
        """
        Constructs the Redis key used to store a project's Reddit subreddit list.

        Returns:
            str: Redis key in the form "config:reddit:subreddits:{project_id}".
        """
        return f"config:reddit:subreddits:{project_id}"

    @staticmethod
    def _datadog_webhook_secret_key(project_id: UUID) -> str:
        """
        Constructs the Redis key used to store a project's Datadog webhook secret.

        Returns:
            str: Redis key in the form "config:datadog:{project_id}:webhook_secret".
        """
        return f"config:datadog:{project_id}:webhook_secret"

    @staticmethod
    def _datadog_monitors_key(project_id: UUID) -> str:
        """
        Constructs the Redis key used to store a project's Datadog monitor IDs.

        Returns:
            str: Redis key in the form "config:datadog:{project_id}:monitors".
        """
        return f"config:datadog:{project_id}:monitors"

    @staticmethod
    def _job_key(job_id: UUID) -> str:
        """
        Builds the Redis key for a job identifier.
        
        Returns:
            The Redis key string in the form "job:<job_id>".
        """
        return f"job:{job_id}"

    @staticmethod
    def _job_logs_key(job_id: UUID) -> str:
        return f"job:{job_id}:logs"

    @staticmethod
    def _cluster_jobs_key(cluster_id: str) -> str:
        """
        Constructs the Redis key used to store job IDs for a specific cluster.
        
        Parameters:
            cluster_id (str): Identifier of the cluster.
        
        Returns:
            str: Redis key in the form "cluster:jobs:{cluster_id}".
        """
        return f"cluster:jobs:{cluster_id}"

    @staticmethod
    def _user_key(user_id: UUID) -> str:
        """
        Constructs the Redis key for a user.
        
        Returns:
            str: Redis key in the form "user:{user_id}".
        """
        return f"user:{user_id}"

    @staticmethod
    def _project_key(project_id: UUID) -> str:
        """
        Constructs the Redis key used to store or reference a project by its UUID.
        
        Returns:
            str: Redis key in the form "project:{project_id}".
        """
        return f"project:{project_id}"

    @staticmethod
    def _user_projects_key(user_id: UUID) -> str:
        """
        Constructs the Redis key used to store project IDs associated with a user.
        
        Parameters:
            user_id (UUID): The user's UUID.
        
        Returns:
            str: Redis key in the form "user:projects:{user_id}".
        """
        return f"user:projects:{user_id}"

    # Feedback
    def add_feedback_item(self, item: FeedbackItem) -> FeedbackItem:
        """
        Add a FeedbackItem to the store and update all relevant indexes and mappings.
        
        Persists the feedback item, indexes it by creation time and source, adds it to the project's unclustered set, and records an external_id mapping when present. Metadata and datetimes are converted to storable formats.
        
        Parameters:
            item (FeedbackItem): Feedback item to persist.
        
        Returns:
            FeedbackItem: The same feedback item that was added.
        """
        payload = item.model_dump()
        if isinstance(payload["created_at"], datetime):
            payload["created_at"] = _dt_to_iso(payload["created_at"])
        
        # Serialize metadata if present
        if isinstance(payload.get("metadata"), dict):
            payload["metadata"] = json.dumps(payload["metadata"])

        # Use HSET (Hash) instead of SET (JSON)
        # Convert all values to strings for HSET
        hash_payload = {k: str(v) for k, v in payload.items() if v is not None}
        
        project_id = str(item.project_id)
        key = self._feedback_key(project_id, item.id)
        self._hset(key, hash_payload)

        ts = item.created_at.timestamp() if isinstance(item.created_at, datetime) else time.time()
        self._zadd(self._feedback_created_key(project_id), ts, str(item.id))
        self._zadd(self._feedback_source_key(project_id, item.source), ts, str(item.id))
        
        # Add to unclustered set (Phase 1: ingestion moat)
        self._sadd(self._feedback_unclustered_key(str(item.project_id)), str(item.id))
        
        if item.external_id:
            self._set(self._feedback_external_key(str(item.project_id), item.source, item.external_id), str(item.id))
        return item

    def get_feedback_item(self, project_id: str, item_id: UUID) -> Optional[FeedbackItem]:
        # Try HGETALL first (new format)
        """
        Retrieve a FeedbackItem by its UUID within a project.
        
        If a stored hash is present, parse and convert fields into the FeedbackItem model (converts ISO datetimes and parses JSON metadata). If legacy JSON is present, attempt to decode it into the model. Returns None when no record exists or when stored data cannot be decoded into a valid FeedbackItem.
        
        Returns:
            FeedbackItem or None: `FeedbackItem` if found and successfully parsed, `None` otherwise.
        """
        key = self._feedback_key(project_id, item_id)
        data = self._hgetall(key)
        
        if not data:
            # Fallback for old data or if HGETALL failed silently?
            # Actually, if key exists as string, HGETALL might error or return empty.
            # But let's assume we migrated or only care about new data for now.
            # If empty, try GET (legacy JSON string)
            raw = self._get(key)
            if raw:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    return None
            else:
                return None

        # Parse fields
        if isinstance(data.get("created_at"), str):
            data["created_at"] = _iso_to_dt(data["created_at"])
        
        # Parse metadata from JSON string if it's a string
        if isinstance(data.get("metadata"), str):
            try:
                data["metadata"] = json.loads(data["metadata"])
            except json.JSONDecodeError:
                data["metadata"] = {}

        return FeedbackItem(**data)

    def get_all_feedback_items(self, project_id: Optional[str] = None) -> List[FeedbackItem]:
        """
        Retrieve all stored FeedbackItem objects for a project ordered by their creation time.
        
        Uses batched fetching for better performance when using Upstash REST.
        Skips entries whose stored IDs are not valid UUIDs or whose referenced items cannot be loaded.
        
        Returns:
            List[FeedbackItem]: Feedback items present in storage, ordered by creation timestamp.
        """
        if project_id is None:
            # Compatibility: return all items when project scope not provided
            return self._get_all_feedback_items_global()

        ids = self._zrange(self._feedback_created_key(project_id), 0, -1)
        if not ids:
            return []
        
        # OPTIMIZATION: Batch fetch all feedback items in one request
        keys = [self._feedback_key(project_id, item_id) for item_id in ids]
        batch_results = self._hgetall_batch(keys)
        
        items: List[FeedbackItem] = []
        for i, data in enumerate(batch_results):
            if not data:
                continue
            try:
                # Create a copy to avoid modifying the original
                parsed = dict(data)
                
                # Parse fields
                if isinstance(parsed.get("created_at"), str):
                    parsed["created_at"] = _iso_to_dt(parsed["created_at"])
                
                # Parse metadata from JSON string if it's a string
                if isinstance(parsed.get("metadata"), str):
                    try:
                        parsed["metadata"] = json.loads(parsed["metadata"])
                    except json.JSONDecodeError:
                        parsed["metadata"] = {}
                
                items.append(FeedbackItem(**parsed))
            except (ValueError, TypeError) as e:
                logger.debug("Failed to parse FeedbackItem at index %d: %s", i, e)
                continue
        return items

    def get_unclustered_feedback(self, project_id: str) -> List[FeedbackItem]:
        """
        Return all feedback items for a project that have not yet been assigned to a cluster.
        
        Uses batched fetching for better performance when using Upstash REST.
        Invalid or missing feedback IDs encountered in the store are ignored and not included in the result.
        
        Returns:
        	List[FeedbackItem]: List of unclustered FeedbackItem objects for the specified project.
        """
        unclustered_key = self._feedback_unclustered_key(project_id)
        unclustered_ids = self._smembers(unclustered_key)
        if not unclustered_ids:
            return []
        
        # OPTIMIZATION: Batch fetch all feedback items in one request
        keys = [self._feedback_key(project_id, item_id) for item_id in unclustered_ids]
        batch_results = self._hgetall_batch(keys)
        
        items: List[FeedbackItem] = []
        for data in batch_results:
            if not data:
                continue
            try:
                # Create a copy to avoid modifying the original
                parsed = dict(data)
                
                # Parse fields
                if isinstance(parsed.get("created_at"), str):
                    parsed["created_at"] = _iso_to_dt(parsed["created_at"])
                
                # Parse metadata from JSON string if it's a string
                if isinstance(parsed.get("metadata"), str):
                    try:
                        parsed["metadata"] = json.loads(parsed["metadata"])
                    except json.JSONDecodeError:
                        parsed["metadata"] = {}
                
                items.append(FeedbackItem(**parsed))
            except (ValueError, TypeError) as e:
                logger.debug("Failed to parse unclustered FeedbackItem: %s", e)
                continue
        return items

    def _get_all_feedback_items_global(self) -> List[FeedbackItem]:
        """
        Compatibility helper: return all feedback items across projects (legacy behavior).
        """
        items: List[FeedbackItem] = []
        # Scan keys matching feedback:*:* (project-scoped) and feedback:* (legacy)
        keys = list(self._scan_iter("feedback:*"))
        for key in keys:
            data = self._hgetall(key)
            if not data:
                continue
            if isinstance(data.get("created_at"), str):
                try:
                    data["created_at"] = _iso_to_dt(data["created_at"])
                except ValueError:
                    logger.debug("Failed to parse created_at for key %s", key)
            if isinstance(data.get("metadata"), str):
                try:
                    data["metadata"] = json.loads(data["metadata"])
                except json.JSONDecodeError:
                    logger.debug("Failed to parse metadata JSON for key %s", key)
                    data["metadata"] = {}
            try:
                items.append(FeedbackItem(**data))
            except (ValueError, TypeError) as e:
                logger.debug("Failed to parse FeedbackItem from key %s: %s", key, e)
                continue
        return items

    def remove_from_unclustered(self, feedback_id: UUID, project_id: str):
        """Remove item from unclustered set (called after clustering)."""
        if self.mode == "redis":
            self.client.srem(
                self._feedback_unclustered_key(project_id), str(feedback_id)
            )
        else:
            # REST client now has srem method
            self.client.srem(
                self._feedback_unclustered_key(project_id), str(feedback_id)
            )

    def remove_from_unclustered_batch(self, pairs: List[Tuple[UUID, str]]):
        """
        Batch remove items from unclustered sets. Expects list of (feedback_id, project_id).
        """
        if not pairs:
            return

        if self.mode == "redis":
            pipe = self.client.pipeline()
            for fid, project_id in pairs:
                pipe.srem(self._feedback_unclustered_key(str(project_id)), str(fid))
            pipe.execute()
        else:
            commands = [
                ["SREM", self._feedback_unclustered_key(str(project_id)), str(fid)]
                for fid, project_id in pairs
            ]
            if commands:
                self.client.pipeline_exec(commands)

    def update_feedback_item(self, project_id: str, item_id: UUID, **updates) -> FeedbackItem:
        """
        Update mutable fields of a feedback item in Redis and return the updated object.
        """
        existing = self.get_feedback_item(project_id, item_id)
        if not existing:
            raise KeyError("feedback not found")
        # Verify project scoping: ensure the item belongs to the given project
        if str(existing.project_id) != str(project_id):
            raise KeyError(f"Feedback {item_id} not found for project {project_id}")

        # Merge updates
        updated = existing.model_copy(update=updates)
        payload = updated.model_dump()
        if isinstance(payload.get("created_at"), datetime):
            payload["created_at"] = _dt_to_iso(payload["created_at"])
        if isinstance(payload.get("metadata"), dict):
            payload["metadata"] = json.dumps(payload["metadata"])

        hash_payload = {k: str(v) for k, v in payload.items() if v is not None}
        key = self._feedback_key(project_id, item_id)
        self._hset(key, hash_payload)
        return updated

    def delete_feedback_item(self, project_id: str, item_id: UUID) -> bool:
        """
        Delete a feedback item and remove it from all indexes.

        Parameters:
            project_id: Project ID that owns the feedback item.
            item_id: UUID of the feedback item to delete.

        Returns:
            bool: True if item was deleted, False if not found.
        """
        existing = self.get_feedback_item(project_id, item_id)
        if not existing:
            return False

        # Delete main feedback hash
        key = self._feedback_key(project_id, item_id)
        self._delete(key)

        # Remove from created sorted set
        if self.mode == "redis":
            self.client.zrem(self._feedback_created_key(project_id), str(item_id))
        else:
            self.client.zrem(self._feedback_created_key(project_id), str(item_id))

        # Remove from source sorted set
        if self.mode == "redis":
            self.client.zrem(self._feedback_source_key(project_id, existing.source), str(item_id))
        else:
            self.client.zrem(self._feedback_source_key(project_id, existing.source), str(item_id))

        # Remove from unclustered set
        self.remove_from_unclustered(item_id, project_id)

        # Delete external ID mapping if present
        if existing.external_id:
            ext_key = self._feedback_external_key(project_id, existing.source, existing.external_id)
            self._delete(ext_key)

        return True

    def delete_feedback_items_batch(self, items: List[Tuple[str, UUID, FeedbackItem]]) -> int:
        """
        Batch delete feedback items and their indexes.

        Parameters:
            items: List of (project_id, item_id, FeedbackItem) tuples.

        Returns:
            int: Number of items deleted.
        """
        if not items:
            return 0

        deleted = 0
        if self.mode == "redis":
            pipe = self.client.pipeline()
            for project_id, item_id, item in items:
                # Delete main hash
                pipe.delete(self._feedback_key(project_id, item_id))
                # Remove from sorted sets
                pipe.zrem(self._feedback_created_key(project_id), str(item_id))
                pipe.zrem(self._feedback_source_key(project_id, item.source), str(item_id))
                # Remove from unclustered set
                pipe.srem(self._feedback_unclustered_key(project_id), str(item_id))
                # Delete external ID mapping
                if item.external_id:
                    pipe.delete(self._feedback_external_key(project_id, item.source, item.external_id))
                deleted += 1
            pipe.execute()
        else:
            # REST mode - build commands list
            commands = []
            for project_id, item_id, item in items:
                commands.append(["DEL", self._feedback_key(project_id, item_id)])
                commands.append(["ZREM", self._feedback_created_key(project_id), str(item_id)])
                commands.append(["ZREM", self._feedback_source_key(project_id, item.source), str(item_id)])
                commands.append(["SREM", self._feedback_unclustered_key(project_id), str(item_id)])
                if item.external_id:
                    commands.append(["DEL", self._feedback_external_key(project_id, item.source, item.external_id)])
                deleted += 1
            if commands:
                self.client.pipeline_exec(commands)

        return deleted

    def clear_feedback_items(self, project_id: Optional[str] = None):
        # Remove keys matching feedback:* and related sorted sets
        """
        Delete stored feedback data for a project (or all projects if project_id is None).
        
        Removes keys for individual feedback items, per-source indexes, external-id mappings, the unclustered set, and the feedback created-time index.
        """
        if project_id:
            pattern = f"feedback:{project_id}:*"
        else:
            pattern = "feedback:*"
        feedback_keys = list(self._scan_iter(pattern))
        if feedback_keys:
            self._delete(*feedback_keys)
        # Legacy global key cleanup
        self._delete("feedback:unclustered")
        # Source sets
        source_keys = list(self._scan_iter("feedback:source:*"))
        if source_keys:
            self._delete(*source_keys)
        # Created sets
        created_keys = list(self._scan_iter("feedback:created:*"))
        if created_keys:
            self._delete(*created_keys)
        external_keys = list(self._scan_iter("feedback:external:*"))
        if external_keys:
            self._delete(*external_keys)

    # Clusters
    def add_cluster(self, cluster: IssueCluster) -> IssueCluster:
        project_id = str(cluster.project_id)
        payload = cluster.model_dump()
        for field in ("created_at", "updated_at"):
            if isinstance(payload.get(field), datetime):
                payload[field] = _dt_to_iso(payload[field])
        
        # Serialize centroid if present
        if isinstance(payload.get("centroid"), list):
            payload["centroid"] = json.dumps(payload["centroid"])
        
        # Serialize sources if present
        if isinstance(payload.get("sources"), list):
            payload["sources"] = json.dumps(payload["sources"])
            
        # Exclude feedback_ids from Hash (stored in set)
        if "feedback_ids" in payload:
            del payload["feedback_ids"]

        # Use HSET (Hash)
        hash_payload = {k: str(v) for k, v in payload.items() if v is not None}
        key = self._cluster_key(project_id, cluster.id)
        self._hset(key, hash_payload)
        
        # Use ZSET with created_at timestamp as score for sorted retrieval
        score = cluster.created_at.timestamp() if cluster.created_at else 0.0
        self._zadd(self._cluster_all_key(project_id), score, str(cluster.id))
        
        # store cluster items set
        items_key = self._cluster_items_key(project_id, cluster.id)
        if cluster.feedback_ids:
            for fid in cluster.feedback_ids:
                self._sadd(items_key, str(fid))
        return cluster

    def get_cluster(self, project_id: str, cluster_id: str) -> Optional[IssueCluster]:
        key = self._cluster_key(project_id, cluster_id)
        # Try HGETALL first
        data = self._hgetall(key)
        
        if not data:
            # Fallback to GET (legacy)
            raw = self._get(key)
            if raw:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    return None
            else:
                return None
        
        # Parse fields
        for field in ("created_at", "updated_at"):
            if isinstance(data.get(field), str):
                data[field] = _iso_to_dt(data[field])

        # Parse centroid
        if isinstance(data.get("centroid"), str):
            try:
                data["centroid"] = json.loads(data["centroid"])
            except json.JSONDecodeError:
                data["centroid"] = []

        # Parse sources (stored as string representation of list)
        if isinstance(data.get("sources"), str):
            try:
                data["sources"] = json.loads(data["sources"])
            except json.JSONDecodeError:
                data["sources"] = []
        
        # Fetch feedback_ids from set if not present (Hash doesn't have it, JSON does)
        if "feedback_ids" not in data or not data["feedback_ids"]:
            items_key = self._cluster_items_key(project_id, cluster_id)
            ids = self._smembers(items_key)
            data["feedback_ids"] = ids

        return IssueCluster(**data)

    def get_all_clusters(self, project_id: Optional[str] = None) -> List[IssueCluster]:
        if project_id is None:
            # Compatibility: return all clusters across projects
            clusters: List[IssueCluster] = []
            # Scan for all project cluster index keys: clusters:*:all
            for key in self._scan_iter("clusters:*:all"):
                # Extract project_id from key pattern clusters:<project_id>:all
                parts = key.split(":")
                if len(parts) >= 2:
                    pid = parts[1]
                    # Get cluster IDs for this project (sorted by created_at desc)
                    cluster_ids = self._zrange(self._cluster_all_key(pid), 0, -1, rev=True)
                    # Load each cluster
                    for cid in cluster_ids:
                        cluster = self.get_cluster(pid, cid)
                        if cluster:
                            clusters.append(cluster)
            return clusters

        # Use ZRANGE with rev=True to get clusters sorted by created_at descending
        ids = self._zrange(self._cluster_all_key(project_id), 0, -1, rev=True)
        clusters: List[IssueCluster] = []
        for cid in ids:
            cluster = self.get_cluster(project_id, cid)
            if cluster:
                clusters.append(cluster)
        return clusters

    def update_cluster(self, project_id: str, cluster_id: str, **updates) -> IssueCluster:
        cluster = self.get_cluster(project_id, cluster_id)
        if not cluster:
            raise KeyError(f"Cluster {cluster_id} not found")
        updated = cluster.model_copy(update=updates)
        return self.add_cluster(updated)

    def clear_clusters(self, project_id: Optional[str] = None):
        """
        Remove cluster records. If project_id is provided, remove that project's clusters;
        otherwise remove all clusters (backwards-compatible for tests/cleanup).
        """
        if project_id:
            cluster_keys = list(self._scan_iter(f"cluster:{project_id}:*")) + [self._cluster_all_key(project_id)]
        else:
            cluster_keys = list(self._scan_iter("cluster:*"))
        if cluster_keys:
            self._delete(*cluster_keys)

    # Config (Reddit)
    def set_reddit_subreddits(self, subreddits: List[str], project_id: UUID) -> List[str]:
        """
        Store the given subreddit names as the Reddit configuration for the specified project.
        
        Parameters:
            subreddits (List[str]): List of subreddit names to associate with the project.
            project_id (UUID): Identifier of the project to set the subreddit configuration for.
        
        Returns:
            List[str]: The same list of subreddit names that was stored.
        """
        payload = json.dumps(subreddits)
        self._set(self._reddit_subreddits_key(project_id), payload)
        return subreddits

    def get_reddit_subreddits(self, project_id: UUID) -> Optional[List[str]]:
        """
        Retrieve the list of configured Reddit subreddits for a project.
        
        Parameters:
            project_id (UUID): Identifier of the project whose subreddit list to fetch.
        
        Returns:
            List[str]: The subreddit names for the project, or `None` if no valid configuration exists.
        """
        raw = self._get(self._reddit_subreddits_key(project_id))
        if not raw:
            return None
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(s) for s in data]
        except json.JSONDecodeError:
            return None
        return None

    def clear_config(self):
        # Remove all subreddit config entries across projects
        """
        Remove all per-project integration configuration entries from the store.

        This deletes every key matching the integration config patterns so no project-specific configuration entries remain.
        """
        keys = list(self._scan_iter("config:reddit:subreddits:*"))
        # Also clear Sentry config
        sentry_keys = list(self._scan_iter("config:sentry:*"))
        splunk_keys = list(self._scan_iter("config:splunk:*"))
        datadog_keys = list(self._scan_iter("config:datadog:*"))
        posthog_keys = list(self._scan_iter("config:posthog:*"))
        all_keys = keys + sentry_keys + splunk_keys + datadog_keys + posthog_keys
        if all_keys:
            self._delete(*all_keys)

    # Config (Sentry)
    @staticmethod
    def _sentry_config_key(project_id: ProjectId, key: str) -> str:
        """
        Construct Redis key for Sentry configuration.

        Returns:
            str: Redis key in the form "config:sentry:{project_id}:{key}".
        """
        return f"config:sentry:{project_id}:{key}"

    def set_sentry_config(self, project_id: ProjectId, key: str, value: Any) -> None:
        """
        Set a Sentry configuration value for a project.

        Parameters:
            project_id (ProjectId): Project identifier.
            key (str): Config key (e.g., "webhook_secret", "environments", "levels").
            value (Any): Config value to store (will be JSON-encoded).
        """
        redis_key = self._sentry_config_key(project_id, key)
        payload = json.dumps(value)
        self._set(redis_key, payload)

    def get_sentry_config(self, project_id: ProjectId, key: str) -> Optional[Any]:
        """
        Get a Sentry configuration value for a project.

        Parameters:
            project_id (ProjectId): Project identifier.
            key (str): Config key to retrieve.

        Returns:
            Optional[Any]: Config value if it exists, None otherwise.
        """
        redis_key = self._sentry_config_key(project_id, key)
        raw = self._get(redis_key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    # Config (Splunk)
    @staticmethod
    def _splunk_config_key(project_id: ProjectId, key: str) -> str:
        """
        Construct Redis key for Splunk configuration.

        Returns:
            str: Redis key in the form "config:splunk:{project_id}:{key}".
        """
        return f"config:splunk:{project_id}:{key}"

    def set_splunk_config(self, project_id: ProjectId, key: str, value: Any) -> None:
        """
        Set a Splunk configuration value for a project.

        Parameters:
            project_id (ProjectId): Project identifier.
            key (str): Config key (e.g., "webhook_token", "allowed_searches", "enabled").
            value (Any): Config value to store (will be JSON-encoded).
        """
        redis_key = self._splunk_config_key(project_id, key)
        payload = json.dumps(value)
        self._set(redis_key, payload)

    def get_splunk_config(self, project_id: ProjectId, key: str) -> Optional[Any]:
        """
        Get a Splunk configuration value for a project.

        Parameters:
            project_id (ProjectId): Project identifier.
            key (str): Config key to retrieve.

        Returns:
            Optional[Any]: Config value if it exists, None otherwise.
        """
        redis_key = self._splunk_config_key(project_id, key)
        raw = self._get(redis_key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    # Config (Datadog)
    @staticmethod
    def _datadog_config_key(project_id: ProjectId, key: str) -> str:
        """
        Construct Redis key for Datadog configuration.

        Returns:
            str: Redis key in the form "config:datadog:{project_id}:{key}".
        """
        return f"config:datadog:{project_id}:{key}"

    def set_datadog_config(self, project_id: ProjectId, key: str, value: Any) -> None:
        """
        Set a Datadog configuration value for a project.

        Parameters:
            project_id (ProjectId): Project identifier.
            key (str): Config key (e.g., "webhook_secret", "monitors", "enabled").
            value (Any): Config value to store (will be JSON-encoded).
        """
        redis_key = self._datadog_config_key(project_id, key)
        payload = json.dumps(value)
        self._set(redis_key, payload)

    def get_datadog_config(self, project_id: ProjectId, key: str) -> Optional[Any]:
        """
        Get a Datadog configuration value for a project.

        Parameters:
            project_id (ProjectId): Project identifier.
            key (str): Config key to retrieve.

        Returns:
            Optional[Any]: Config value if it exists, None otherwise.
        """
        redis_key = self._datadog_config_key(project_id, key)
        raw = self._get(redis_key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    # Config (PostHog)
    @staticmethod
    def _posthog_config_key(project_id: ProjectId, key: str) -> str:
        """
        Construct Redis key for PostHog configuration.

        Returns:
            str: Redis key in the form "config:posthog:{project_id}:{key}".
        """
        return f"config:posthog:{project_id}:{key}"

    def set_posthog_config(self, project_id: ProjectId, key: str, value: Any) -> None:
        """
        Set a PostHog configuration value for a project.

        Parameters:
            project_id (ProjectId): Project identifier.
            key (str): Config key (e.g., "event_types", "enabled").
            value (Any): Config value to store (will be JSON-encoded).
        """
        redis_key = self._posthog_config_key(project_id, key)
        payload = json.dumps(value)
        self._set(redis_key, payload)

    def get_posthog_config(self, project_id: ProjectId, key: str) -> Optional[Any]:
        """
        Get a PostHog configuration value for a project.

        Parameters:
            project_id (ProjectId): Project identifier.
            key (str): Config key to retrieve.

        Returns:
            Optional[Any]: Config value if it exists, None otherwise.
        """
        redis_key = self._posthog_config_key(project_id, key)
        raw = self._get(redis_key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    # Config (Datadog)
    def set_datadog_webhook_secret(self, secret: str, project_id: UUID) -> str:
        """
        Set the Datadog webhook secret for a specific project.

        Parameters:
            secret (str): Webhook secret to use for signature verification.
            project_id (UUID): Identifier of the project to associate the secret with.

        Returns:
            str: The secret that was stored.
        """
        self._set(self._datadog_webhook_secret_key(project_id), secret)
        return secret

    def get_datadog_webhook_secret(self, project_id: UUID) -> Optional[str]:
        """
        Retrieve the configured Datadog webhook secret for a project.

        Returns:
            str: The webhook secret for the project, or None if no secret is configured.
        """
        return self._get(self._datadog_webhook_secret_key(project_id))

    def set_datadog_monitors(self, monitors: List[str], project_id: UUID) -> List[str]:
        """
        Set the list of Datadog monitor IDs to track for a project.

        Parameters:
            monitors (List[str]): List of monitor IDs or ["*"] for all monitors.
            project_id (UUID): Identifier of the project to associate the monitors with.

        Returns:
            List[str]: The list of monitor IDs that was stored.
        """
        payload = json.dumps(monitors)
        self._set(self._datadog_monitors_key(project_id), payload)
        return monitors

    def get_datadog_monitors(self, project_id: UUID) -> Optional[List[str]]:
        """
        Retrieve the configured Datadog monitor IDs for a project.

        Returns:
            List[str]: The monitor IDs for the project, or None if no configuration exists.
        """
        raw = self._get(self._datadog_monitors_key(project_id))
        if not raw:
            return None
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(m) for m in data]
        except json.JSONDecodeError:
            return None
        return None

    # Jobs
    def add_job(self, job: AgentJob) -> AgentJob:
        """
        Persist the given AgentJob in the store and index it for cluster-based retrieval.
        
        Parameters:
            job (AgentJob): The job to persist.
        
        Returns:
            AgentJob: The same job instance that was stored.
        """
        payload = job.model_dump()
        for field in ("created_at", "updated_at"):
            if isinstance(payload.get(field), datetime):
                payload[field] = _dt_to_iso(payload[field])

        # Use HSET
        hash_payload = {k: str(v) for k, v in payload.items() if v is not None}
        key = self._job_key(job.id)
        self._hset(key, hash_payload)

        # Add to cluster index (sorted by created_at)
        ts = job.created_at.timestamp()
        self._zadd(self._cluster_jobs_key(job.cluster_id), ts, str(job.id))
        return job

    def get_job(self, job_id: UUID) -> Optional[AgentJob]:
        key = self._job_key(job_id)
        data = self._hgetall(key)
        if not data:
            return None

        for field in ("created_at", "updated_at"):
            if isinstance(data.get(field), str):
                data[field] = _iso_to_dt(data[field])

        return AgentJob(**data)

    def update_job(self, job_id: UUID, **updates) -> AgentJob:
        key = self._job_key(job_id)
        existing = self._hgetall(key)
        if not existing:
            raise KeyError(f"Job {job_id} not found")
        # Only update provided fields (avoid re-writing + re-indexing on every log line).
        payload = {}
        for k, v in updates.items():
            if isinstance(v, datetime):
                payload[k] = _dt_to_iso(v)
            elif v is None:
                continue
            else:
                payload[k] = str(v)
        if payload:
            self._hset(key, payload)
        return self.get_job(job_id)  # type: ignore[return-value]

    def append_job_log(self, job_id: UUID, message: str) -> None:
        key = self._job_logs_key(job_id)
        # Store chunks (may contain multiple lines).
        self.client.rpush(key, message)
        ttl_seconds = int(os.getenv("JOB_LOG_TTL_SECONDS", "604800"))  # 7 days
        try:
            if ttl_seconds > 0:
                self.client.expire(key, ttl_seconds)
        except Exception as exc:
            # Best-effort TTL: not all clients/backends support expire the same way.
            logger.debug("Failed to set TTL on %s: %s", key, exc)

    def get_job_logs(self, job_id: UUID, cursor: int = 0, limit: int = 200) -> tuple[list[str], int, bool]:
        key = self._job_logs_key(job_id)
        if cursor < 0:
            cursor = 0
        limit = max(1, min(int(limit), 1000))
        stop = cursor + limit - 1
        items = self.client.lrange(key, cursor, stop)
        next_cursor = cursor + len(items)
        total = self.client.llen(key)
        has_more = next_cursor < total
        return (items, next_cursor, has_more)

    def get_jobs_by_cluster(self, cluster_id: str) -> List[AgentJob]:
        key = self._cluster_jobs_key(cluster_id)
        ids = self._zrange(key, 0, -1, rev=True)  # Newest first
        jobs: List[AgentJob] = []
        for jid in ids:
            try:
                job = self.get_job(UUID(jid))
                if job:
                    jobs.append(job)
            except ValueError:
                continue
        return jobs

    def get_all_jobs(self) -> List[AgentJob]:
        # Scan for all job keys
        job_keys = list(self._scan_iter("job:*"))
        jobs: List[AgentJob] = []
        for key in job_keys:
            try:
                # key format is job:uuid
                jid = key.split(":")[-1]
                job = self.get_job(UUID(jid))
                if job:
                    jobs.append(job)
            except ValueError:
                continue
        # Sort by created_at desc
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        return jobs

    def clear_jobs(self):
        """
        Remove all stored AgentJob entries and their cluster indexes from the backend.
        
        This deletes keys matching `job:*` (individual job hashes) and `cluster:jobs:*` (cluster-specific job sorted sets) from the configured store.
        """
        job_keys = (
            list(self._scan_iter("job:*"))
            + list(self._scan_iter("cluster:jobs:*"))
            + list(self._scan_iter("job:*:logs"))
        )
        if job_keys:
            self._delete(*job_keys)

    # Cluster Jobs (clustering runner)
    def add_cluster_job(self, job: ClusterJob) -> ClusterJob:
        """
        Store a ClusterJob and index it for recent retrieval.
        
        Parameters:
            job (ClusterJob): Cluster job to persist.
        
        Returns:
            ClusterJob: The stored cluster job (same instance).
        """
        payload = job.model_dump()
        for field in ("created_at", "started_at", "finished_at"):
            if isinstance(payload.get(field), datetime):
                payload[field] = _dt_to_iso(payload[field])
        if isinstance(payload.get("stats"), dict):
            payload["stats"] = json.dumps(payload["stats"])
        key = self._cluster_job_key(str(job.project_id), job.id)
        hash_payload = {k: str(v) for k, v in payload.items() if v is not None}
        self._hset(key, hash_payload)
        ts = job.created_at.timestamp()
        self._zadd(self._cluster_jobs_recent_key(str(job.project_id)), ts, job.id)
        return job

    def get_cluster_job(self, project_id: str, job_id: str) -> Optional[ClusterJob]:
        """
        Load a ClusterJob for the given project and job IDs.
        
        If present, ISO-formatted timestamp strings for `created_at`, `started_at`, and `finished_at` are converted to datetime objects and the `stats` field is JSON-decoded into a dict. Returns `None` when the job does not exist or has no stored data.
        
        Returns:
            ClusterJob | None: The reconstructed ClusterJob for the given project and job ID, or `None` if not found.
        """
        key = self._cluster_job_key(project_id, job_id)
        data = self._hgetall(key)
        if not data:
            return None
        for field in ("created_at", "started_at", "finished_at"):
            if isinstance(data.get(field), str):
                data[field] = _iso_to_dt(data[field])
        # Parse stats JSON string into dict when stored as text
        if isinstance(data.get("stats"), str):
            try:
                data["stats"] = json.loads(data["stats"])
            except json.JSONDecodeError:
                data["stats"] = {}
        return ClusterJob(**data)

    def list_cluster_jobs(self, project_id: str, limit: int = 20) -> List[ClusterJob]:
        """
        Retrieve recent cluster jobs for a project in newest-first order.
        
        Parameters:
            project_id (str): Project identifier to list cluster jobs for.
            limit (int): Maximum number of jobs to return; defaults to 20.
        
        Returns:
            List[ClusterJob]: List of ClusterJob objects ordered from newest to oldest; may contain fewer than `limit` if not enough jobs exist.
        """
        ids = self._zrange(self._cluster_jobs_recent_key(project_id), -limit, -1, rev=True)
        jobs: List[ClusterJob] = []
        for jid in ids:
            job = self.get_cluster_job(project_id, jid)
            if job:
                jobs.append(job)
        return jobs

    def update_cluster_job(self, project_id: str, job_id: str, **updates) -> ClusterJob:
        """
        Update fields of an existing ClusterJob and persist the updated job.
        
        Parameters:
            project_id (str): Identifier of the project that owns the cluster job.
            job_id (str): Identifier of the cluster job to update.
            **updates: Fields to merge into the existing ClusterJob; keys should match ClusterJob model attributes.
        
        Returns:
            ClusterJob: The persisted ClusterJob after applying the updates.
        
        Raises:
            KeyError: If no ClusterJob with the given job_id exists for the specified project_id.
        """
        existing = self.get_cluster_job(project_id, job_id)
        if not existing:
            raise KeyError(f"ClusterJob {job_id} not found for project {project_id}")
        updated = existing.model_copy(update=updates)
        return self.add_cluster_job(updated)

    def acquire_cluster_lock(self, project_id: str, job_id: str, ttl_seconds: int = 600) -> bool:
        """
        Acquire a per-project cluster lock by atomically setting a lock key with the caller job as owner.
        
        Parameters:
            project_id (str): Project identifier used to scope the lock.
            job_id (str): Identifier stored as the lock owner when acquisition succeeds.
            ttl_seconds (int): Time-to-live for the lock in seconds (defaults to 600).
        
        Returns:
            `True` if the lock was acquired and the job_id was stored as owner, `False` otherwise.
        """
        key = self._cluster_lock_key(project_id)
        if self.mode == "redis":
            return bool(self.client.set(key, job_id, nx=True, ex=ttl_seconds))
        try:
            result = self.client.set_with_opts(key, job_id, "NX", "EX", str(ttl_seconds))
        except Exception as exc:
            logger.warning(
                "Failed to acquire cluster lock for project %s: %s", project_id, exc
            )
            return False
        return bool(result)

    def release_cluster_lock(self, project_id: str, job_id: str):
        """
        Release the clustering lock for a project if owned by the given cluster job.
        
        If the stored lock for the project is held by `job_id`, the lock is removed.
        If reading the lock state fails, the lock is removed as a best-effort fallback.
        
        Parameters:
            project_id (str): Identifier of the project whose cluster lock should be released.
            job_id (str): Identifier of the cluster job expected to own the lock.
        """
        key = self._cluster_lock_key(project_id)
        if self.mode == "redis":
            lua_script = """
            if redis.call('get', KEYS[1]) == ARGV[1] then
                return redis.call('del', KEYS[1])
            else
                return 0
            end
            """
            try:
                self.client.eval(lua_script, 1, key, job_id)
            except Exception as exc:
                logger.warning(
                    "Failed to release cluster lock for project %s: %s", project_id, exc
                )
            return

        current = self._get(key)
        if current == job_id:
            self._delete(key)

    def get_feedback_by_external_id(self, project_id: UUID, source: str, external_id: str) -> Optional[FeedbackItem]:
        """
        Resolve a feedback item by its external identifier within a project.
        
        Parameters:
            project_id (UUID): Project that owns the external identifier.
            source (str): External source name (e.g., "github", "zendesk").
            external_id (str): External identifier provided by the source.
        
        Returns:
            FeedbackItem or None: `FeedbackItem` if a mapping exists and resolves to an existing item, `None` otherwise.
        """
        if not external_id:
            return None
        key = self._feedback_external_key(str(project_id), source, external_id)
        existing_id = self._get(key)
        if not existing_id:
            return None
        try:
            return self.get_feedback_item(str(project_id), UUID(existing_id))
        except ValueError:
            return None

    def get_feedback_by_external_ids_batch(
        self, project_id: UUID, source: str, external_ids: List[str]
    ) -> Dict[str, FeedbackItem]:
        """
        Batch resolve feedback items by their external identifiers within a project.

        Uses pipelined GET + HGETALL to minimize network requests (critical for Upstash REST).
        Returns a mapping of external_id -> FeedbackItem for all found items.
        """
        if not external_ids:
            return {}

        project_id_str = str(project_id)
        deduped_external_ids = list(dict.fromkeys([eid for eid in external_ids if eid]))
        if not deduped_external_ids:
            return {}

        # Step 1: batch GET external_id -> feedback_id mappings
        ext_key_pairs = [
            (eid, self._feedback_external_key(project_id_str, source, eid))
            for eid in deduped_external_ids
        ]

        existing_ids: Dict[str, str] = {}
        if self.mode == "redis":
            pipe = self.client.pipeline()
            for _, key in ext_key_pairs:
                pipe.get(key)
            results = pipe.execute()
        else:
            commands = [["GET", key] for _, key in ext_key_pairs]
            results = self.client.pipeline_exec(commands)

        for (ext_id, _), value in zip(ext_key_pairs, results):
            if value:
                existing_ids[ext_id] = value

        if not existing_ids:
            return {}

        # Step 2: batch HGETALL feedback hashes for found IDs
        fetch_pairs = []
        for ext_id, fid in existing_ids.items():
            try:
                feedback_uuid = UUID(fid)
            except ValueError:
                continue
            fetch_pairs.append((ext_id, self._feedback_key(project_id_str, feedback_uuid)))

        if not fetch_pairs:
            return {}

        keys_to_fetch = [key for _, key in fetch_pairs]
        batch_results = self._hgetall_batch(keys_to_fetch)

        resolved: Dict[str, FeedbackItem] = {}
        for (ext_id, _), data in zip(fetch_pairs, batch_results):
            if not data:
                continue
            parsed = dict(data)
            if isinstance(parsed.get("created_at"), str):
                parsed["created_at"] = _iso_to_dt(parsed["created_at"])
            if isinstance(parsed.get("metadata"), str):
                try:
                    parsed["metadata"] = json.loads(parsed["metadata"])
                except json.JSONDecodeError:
                    parsed["metadata"] = {}
            try:
                resolved[ext_id] = FeedbackItem(**parsed)
            except (ValueError, TypeError):
                continue

        return resolved

    # Users / Projects
    def create_user_with_default_project(self, user: User, default_project: Project) -> Project:
        """
        Create a user record in storage and create the user's default project.
        
        Parameters:
        	user (User): The user to persist.
        	default_project (Project): The initial project to create for the user.
        
        Returns:
        	Project: The created default project.
        """
        payload = user.model_dump()
        if isinstance(payload.get("created_at"), datetime):
            payload["created_at"] = _dt_to_iso(payload["created_at"])

        hash_payload = {k: str(v) for k, v in payload.items() if v is not None}
        self._hset(self._user_key(user.id), hash_payload)

        return self.create_project(default_project)

    def create_project(self, project: Project) -> Project:
        """
        Store the given Project and associate it with its owner.
        
        Parameters:
            project (Project): Project to persist.
        
        Returns:
            Project: The same Project instance that was stored.
        """
        payload = project.model_dump()
        if isinstance(payload.get("created_at"), datetime):
            payload["created_at"] = _dt_to_iso(payload["created_at"])

        hash_payload = {k: str(v) for k, v in payload.items() if v is not None}
        self._hset(self._project_key(project.id), hash_payload)
        self._sadd(self._user_projects_key(project.user_id), str(project.id))
        return project

    def get_projects_for_user(self, user_id: UUID) -> List[Project]:
        """
        Return the list of projects associated with a user.
        
        Parameters:
            user_id (UUID): The user's unique identifier.
        
        Returns:
            List[Project]: Projects linked to the given user; invalid or unparsable project IDs are ignored and an empty list is returned if none are found.
        """
        project_ids = self._smembers(self._user_projects_key(user_id))
        projects: List[Project] = []
        for pid in project_ids:
            try:
                project = self.get_project(pid)
            except ValueError:
                continue
            if project:
                projects.append(project)
        return projects

    def get_project(self, project_id: UUID) -> Optional[Project]:
        """
        Retrieve the stored project for a given project UUID.
        
        Parameters:
            project_id (UUID): The UUID of the project to fetch.
        
        Returns:
            Project | None: The Project matching `project_id`, or `None` if no project exists. If the stored `created_at` is an ISO string, it is converted to a `datetime` on return.
        """
        data = self._hgetall(self._project_key(project_id))
        if not data:
            return None

        if isinstance(data.get("created_at"), str):
            data["created_at"] = _iso_to_dt(data["created_at"])

        return Project(**data)

    # --- client wrappers ---
    def _set(self, key: str, value: str):
        """
        Store a raw string value under the given key in the configured backend client.
        
        Parameters:
            key (str): Redis-style key to set.
            value (str): Raw string value to store.
        """
        if self.mode == "redis":
            self.client.set(key, value)
        else:
            self.client.set(key, value)

    def _get(self, key: str) -> Optional[str]:
        return self.client.get(key)

    def _zadd(self, key: str, score: float, member: str):
        if self.mode == "redis":
            self.client.zadd(key, {member: score})
        else:
            self.client.zadd(key, score, member)

    def _zrange(self, key: str, start: int, stop: int, rev: bool = False) -> List[str]:
        if self.mode == "redis":
            return self.client.zrange(key, start, stop, desc=rev)
        return self.client.zrange(key, start, stop, rev=rev)

    def _sadd(self, key: str, member: str):
        if self.mode == "redis":
            self.client.sadd(key, member)
        else:
            self.client.sadd(key, member)

    def _smembers(self, key: str) -> List[str]:
        if self.mode == "redis":
            return list(self.client.smembers(key))
        return self.client.smembers(key)

    def _delete(self, *keys: str):
        if not keys:
            return
        if self.mode == "redis":
            self.client.delete(*keys)
        else:
            self.client.delete(*keys)

    def _scan_iter(self, pattern: str) -> Iterable[str]:
        if self.mode == "redis":
            yield from self.client.scan_iter(pattern)
        else:
            yield from self.client.scan_iter(pattern)

    def _hset(self, key: str, mapping: Dict[str, Any]):
        if self.mode == "redis":
            self.client.hset(key, mapping=mapping)
        else:
            self.client.hset(key, mapping)

    def _hgetall(self, key: str) -> Dict[str, str]:
        if self.mode == "redis":
            return self.client.hgetall(key)
        else:
            return self.client.hgetall(key)

    def _hgetall_batch(self, keys: List[str]) -> List[Dict[str, str]]:
        """
        Batch fetch multiple hashes in a single request for better performance.
        
        Parameters:
            keys: List of Redis hash keys to fetch
        
        Returns:
            List of dicts, one per key. Empty dict if key doesn't exist.
        """
        if not keys:
            return []
        if self.mode == "redis":
            # Use redis-py pipeline for batch fetching
            pipe = self.client.pipeline()
            for key in keys:
                pipe.hgetall(key)
            return pipe.execute()
        else:
            # Use REST client's batch method
            return self.client.hgetall_batch(keys)

    def add_feedback_items_batch(self, items: List[FeedbackItem]) -> List[FeedbackItem]:
        """
        Batch add FeedbackItems using pipeline to reduce network overhead (especially Upstash REST).
        """
        if not items:
            return []

        if self.mode == "redis":
            pipe = self.client.pipeline()
            for item in items:
                payload = item.model_dump()
                if isinstance(payload.get("created_at"), datetime):
                    payload["created_at"] = _dt_to_iso(payload["created_at"])
                if isinstance(payload.get("metadata"), dict):
                    payload["metadata"] = json.dumps(payload["metadata"])

                hash_payload = {k: str(v) for k, v in payload.items() if v is not None}
                project_id = str(item.project_id)
                key = self._feedback_key(project_id, item.id)
                ts = item.created_at.timestamp() if isinstance(item.created_at, datetime) else time.time()

                pipe.hset(key, mapping=hash_payload)
                pipe.zadd(self._feedback_created_key(project_id), {str(item.id): ts})
                pipe.zadd(self._feedback_source_key(project_id, item.source), {str(item.id): ts})
                pipe.sadd(self._feedback_unclustered_key(project_id), str(item.id))
                if item.external_id:
                    pipe.set(
                        self._feedback_external_key(project_id, item.source, item.external_id),
                        str(item.id),
                    )
            pipe.execute()
        else:
            commands: List[List[str]] = []
            for item in items:
                payload = item.model_dump()
                if isinstance(payload.get("created_at"), datetime):
                    payload["created_at"] = _dt_to_iso(payload["created_at"])
                if isinstance(payload.get("metadata"), dict):
                    payload["metadata"] = json.dumps(payload["metadata"])

                hash_payload = {k: str(v) for k, v in payload.items() if v is not None}
                project_id = str(item.project_id)
                key = self._feedback_key(project_id, item.id)
                ts = item.created_at.timestamp() if isinstance(item.created_at, datetime) else time.time()

                hset_cmd = ["HSET", key]
                for field, value in hash_payload.items():
                    hset_cmd.extend([field, value])
                commands.append(hset_cmd)

                commands.append(["ZADD", self._feedback_created_key(project_id), str(ts), str(item.id)])
                commands.append(["ZADD", self._feedback_source_key(project_id, item.source), str(ts), str(item.id)])
                commands.append(["SADD", self._feedback_unclustered_key(project_id), str(item.id)])
                if item.external_id:
                    commands.append(
                        ["SET", self._feedback_external_key(project_id, item.source, item.external_id), str(item.id)]
                    )

            self.client.pipeline_exec(commands)

        return items


# ---------- Store selector ----------


def _select_store():
    try:
        if os.getenv("REDIS_URL") or os.getenv("UPSTASH_REDIS_URL") or os.getenv("UPSTASH_REDIS_REST_URL"):
            return RedisStore()
    except Exception as exc:  # fall back silently for local dev if misconfigured
        print(f"RedisStore unavailable, falling back to in-memory. Reason: {exc}")
    return InMemoryStore()


_STORE = _select_store()


# Public API (delegates to current store)
def add_feedback_item(item: FeedbackItem) -> FeedbackItem:
    return _STORE.add_feedback_item(item)


def add_feedback_items_batch(items: List[FeedbackItem]) -> List[FeedbackItem]:
    """
    Batch add feedback items. Falls back to individual adds when batch not supported.
    """
    if hasattr(_STORE, "add_feedback_items_batch"):
        return _STORE.add_feedback_items_batch(items)
    return [add_feedback_item(item) for item in items]


def get_feedback_item(project_id: str, item_id: UUID) -> Optional[FeedbackItem]:
    return _STORE.get_feedback_item(project_id, item_id)


def get_all_feedback_items(project_id: Optional[str] = None) -> List[FeedbackItem]:
    """
    Retrieve stored feedback items. When project_id is None, returns all items (legacy/compat).
    
    Returns:
        A list of FeedbackItem objects, one entry per stored feedback item.
    """
    return _STORE.get_all_feedback_items(project_id)


def update_feedback_item(project_id: str, item_id: UUID, **updates) -> FeedbackItem:
    return _STORE.update_feedback_item(project_id, item_id, **updates)


def get_feedback_by_external_id(project_id: str, source: str, external_id: str) -> Optional[FeedbackItem]:
    """
    Lookup a feedback item for a given project by its source and external identifier.
    
    Parameters:
        project_id (str): ID of the project that owns the feedback item.
        source (str): Source system or provider name associated with the external identifier.
        external_id (str): External identifier assigned by the source; if empty, the lookup returns `None`.
    
    Returns:
        FeedbackItem | None: The matching `FeedbackItem` if found, `None` otherwise.
    """
    if not external_id:
        return None
    if hasattr(_STORE, "get_feedback_by_external_id"):
        return _STORE.get_feedback_by_external_id(project_id, source, external_id)
    # Fallback: linear scan (should rarely happen)
    for item in _STORE.get_all_feedback_items(project_id):
        if item.project_id == project_id and item.source == source and item.external_id == external_id:
            return item
    return None


def get_feedback_by_external_ids_batch(
    project_id: str, source: str, external_ids: List[str]
) -> Dict[str, FeedbackItem]:
    """
    Batch lookup by external IDs. Falls back to individual lookups when batch not supported.
    """
    if hasattr(_STORE, "get_feedback_by_external_ids_batch"):
        return _STORE.get_feedback_by_external_ids_batch(project_id, source, external_ids)

    results: Dict[str, FeedbackItem] = {}
    for ext_id in external_ids:
        existing = get_feedback_by_external_id(project_id, source, ext_id)
        if existing:
            results[ext_id] = existing
    return results


def clear_feedback_items(project_id: Optional[str] = None):
    _STORE.clear_feedback_items(project_id)


def add_cluster(cluster: IssueCluster) -> IssueCluster:
    return _STORE.add_cluster(cluster)


def get_cluster(project_id: str, cluster_id: str) -> Optional[IssueCluster]:
    """
    Retrieve a cluster by project and cluster ID.
    """
    return _STORE.get_cluster(project_id, cluster_id)


def get_cluster_by_id(cluster_id: str) -> Optional[IssueCluster]:
    """
    Legacy: retrieve a cluster by ID only (scans all projects).
    
    Note: This only works with stores that support project_id=None (currently InMemoryStore).
    For RedisStore, use get_cluster(project_id, cluster_id) instead.
    """
    # Only works with stores that accept Optional project_id
    if hasattr(_STORE, "get_cluster"):
        # Try to call with None project_id for backwards compatibility
        # This will work for InMemoryStore but not RedisStore
        try:
            return _STORE.get_cluster(None, cluster_id)  # type: ignore[arg-type]
        except (TypeError, AttributeError):
            # RedisStore requires project_id, so this will fail
            raise ValueError(
                f"get_cluster_by_id requires project_id with {type(_STORE).__name__}. "
                f"Use get_cluster(project_id, cluster_id) instead."
            )
    return None


def get_all_clusters(project_id: Optional[str] = None) -> List[IssueCluster]:
    """
    Compatibility wrapper: when project_id is None, return all clusters (legacy behavior).
    """
    return _STORE.get_all_clusters(project_id)


def update_cluster(project_id: str, cluster_id: str, **updates) -> IssueCluster:
    return _STORE.update_cluster(project_id, cluster_id, **updates)


def clear_clusters(project_id: Optional[str] = None):
    _STORE.clear_clusters(project_id)


def set_reddit_subreddits(subreddits: List[str]) -> List[str]:
    """
    Placeholder that enforces using a project-scoped API when setting subreddit configuration.
    
    Raises:
        TypeError: always raised to indicate a required `project_id` parameter.
    """
    raise TypeError("set_reddit_subreddits requires project_id")


def get_reddit_subreddits() -> Optional[List[str]]:
    """
    Raise an error because a project identifier is required to retrieve subreddit configuration.
    
    Raises:
        TypeError: Always raised indicating that `project_id` is required.
    """
    raise TypeError("get_reddit_subreddits requires project_id")


def clear_config():
    # Primarily for tests
    """
    Clear all per-project Reddit subreddit configuration from the active storage backend.
    
    This delegates to the selected store's `clear_config` method when available; if the active store does not implement `clear_config`, this function is a no-op.
    """
    if hasattr(_STORE, "clear_config"):
        _STORE.clear_config()


def add_job(job: AgentJob) -> AgentJob:
    return _STORE.add_job(job)


def get_job(job_id: UUID) -> Optional[AgentJob]:
    return _STORE.get_job(job_id)


def update_job(job_id: UUID, **updates) -> AgentJob:
    return _STORE.update_job(job_id, **updates)


def get_jobs_by_cluster(cluster_id: str) -> List[AgentJob]:
    return _STORE.get_jobs_by_cluster(cluster_id)


def get_all_jobs() -> List[AgentJob]:
    return _STORE.get_all_jobs()

def append_job_log(job_id: UUID, message: str) -> None:
    if hasattr(_STORE, "append_job_log"):
        _STORE.append_job_log(job_id, message)

def get_job_logs(job_id: UUID, cursor: int = 0, limit: int = 200) -> tuple[list[str], int, bool]:
    if hasattr(_STORE, "get_job_logs"):
        return _STORE.get_job_logs(job_id, cursor=cursor, limit=limit)
    return ([], cursor, False)


def clear_jobs():
    """
    Delete all AgentJob records and their related indexes from the active storage backend.
    
    If the currently selected store does not implement a `clear_jobs` operation, no action is taken.
    """
    if hasattr(_STORE, "clear_jobs"):
        _STORE.clear_jobs()


# Cluster job API
def add_cluster_job(job: ClusterJob) -> ClusterJob:
    """
    Store a ClusterJob and index it for project-scoped retrieval and locking.
    
    Parameters:
        job (ClusterJob): ClusterJob to persist; its project_id determines the project namespace used for indexing.
    
    Returns:
        ClusterJob: The stored ClusterJob.
    """
    return _STORE.add_cluster_job(job)


def get_cluster_job(project_id: str, job_id: str) -> Optional[ClusterJob]:
    """
    Retrieve a cluster job for the specified project and job identifiers.
    
    @returns The ClusterJob matching the provided `project_id` and `job_id`, or `None` if no matching job exists.
    """
    return _STORE.get_cluster_job(project_id, job_id)


def list_cluster_jobs(project_id: str, limit: int = 20) -> List[ClusterJob]:
    """
    Retrieves recent cluster jobs for a project.
    
    Parameters:
        project_id (str): ID of the project whose cluster jobs to list.
        limit (int): Maximum number of cluster jobs to return (default 20).
    
    Returns:
        List[ClusterJob]: Cluster jobs ordered by recency (most recent first), up to `limit`.
    """
    return _STORE.list_cluster_jobs(project_id, limit)


def update_cluster_job(project_id: str, job_id: str, **updates) -> ClusterJob:
    """
    Update fields of an existing cluster job and return the updated ClusterJob.
    
    Parameters:
        project_id (str): ID of the project that owns the cluster job.
        job_id (str): ID of the cluster job to update.
        **updates: Field names and values to apply to the ClusterJob (only provided keys will be changed).
    
    Returns:
        ClusterJob: The updated ClusterJob instance.
    """
    return _STORE.update_cluster_job(project_id, job_id, **updates)


def acquire_cluster_lock(project_id: str, job_id: str, ttl_seconds: int = 600) -> bool:
    """
    Attempt to acquire a lock for a cluster job in the selected storage backend.
    
    If the active store implements `acquire_cluster_lock`, delegates to it; if not, succeeds by default.
    
    Parameters:
        project_id (str): Project identifier that scopes the lock.
        job_id (str): Cluster job identifier that will own the lock.
        ttl_seconds (int): Lock time-to-live in seconds.
    
    Returns:
        `true` if the lock was acquired, `false` otherwise.
    """
    if hasattr(_STORE, "acquire_cluster_lock"):
        return _STORE.acquire_cluster_lock(project_id, job_id, ttl_seconds)
    return True


def release_cluster_lock(project_id: str, job_id: str):
    """
    Release the cluster lock for a clustering job in the given project.
    
    Parameters:
        project_id (str): Identifier of the project that owns the lock.
        job_id (str): Identifier of the cluster job that should release the lock.
    """
    if hasattr(_STORE, "release_cluster_lock"):
        _STORE.release_cluster_lock(project_id, job_id)


def get_unclustered_feedback(project_id: str) -> List[FeedbackItem]:
    """
    Retrieve feedback items that are currently unclustered for the given project.
    
    Parameters:
        project_id (str): ID of the project whose unclustered feedback should be returned.
    
    Returns:
        List[FeedbackItem]: Feedback items contained in the project's unclustered set.
    """
    items = _STORE.get_unclustered_feedback(project_id)
    # If store returns a list (even empty), respect it; only fallback when store returns None.
    if items is not None:
        return items
    # Fallback: derive unclustered as all non-closed feedback for the project (legacy/compat)
    return [item for item in get_all_feedback_items(project_id) if item.status != "closed"]


def remove_from_unclustered(feedback_id: UUID, project_id: str):
    """
    Remove a feedback item from the project's unclustered set.
    
    Parameters:
    	feedback_id (UUID): ID of the feedback item to remove.
    	project_id (str): ID of the project that owns the unclustered set.
    """
    return _STORE.remove_from_unclustered(feedback_id, project_id)


def remove_from_unclustered_batch(pairs: List[Tuple[UUID, str]]):
    """
    Batch remove feedback items from unclustered sets. Falls back to individual calls.
    """
    if hasattr(_STORE, "remove_from_unclustered_batch"):
        return _STORE.remove_from_unclustered_batch(pairs)
    for fid, project_id in pairs:
        remove_from_unclustered(fid, project_id)


def delete_feedback_items_batch(items: List[Tuple[str, UUID, FeedbackItem]]) -> int:
    """
    Batch delete feedback items and their indexes.

    Parameters:
        items: List of (project_id, item_id, FeedbackItem) tuples.

    Returns:
        int: Number of items deleted.
    """
    if hasattr(_STORE, "delete_feedback_items_batch"):
        return _STORE.delete_feedback_items_batch(items)
    # Fallback to individual deletes
    deleted = 0
    for project_id, item_id, _ in items:
        if _STORE.delete_feedback_item(project_id, item_id):
            deleted += 1
    return deleted


# User / Project API
def create_user_with_default_project(user: User, project: Project) -> Project:
    """
    Create the user record and create a default project associated with that user.
    
    Parameters:
        user (User): User model to persist.
        project (Project): Project model to persist as the user's default project.
    
    Returns:
        Project: The persisted default project, potentially updated with store-assigned fields.
    """
    return _STORE.create_user_with_default_project(user, project)


def create_project(project: Project) -> Project:
    """
    Create and persist a new project.
    
    Parameters:
        project (Project): Project data to store; returned value may include generated fields such as an assigned `id`.
    
    Returns:
        Project: The stored Project, including any server- or store-generated fields.
    """
    return _STORE.create_project(project)


def get_projects_for_user(user_id: UUID) -> List[Project]:
    """
    Retrieve projects associated with the specified user.
    
    Parameters:
        user_id (UUID): Identifier of the user whose projects should be returned.
    
    Returns:
        projects (List[Project]): List of Project objects belonging to the given user.
    """
    return _STORE.get_projects_for_user(user_id)


def get_project(project_id: UUID) -> Optional[Project]:
    """
    Retrieve the project with the given ID.
    
    Returns:
        Project if a project with `project_id` exists, `None` otherwise.
    """
    return _STORE.get_project(project_id)


# Project-scoped config API
def set_reddit_subreddits_for_project(subreddits: List[str], project_id: ProjectId) -> List[str]:
    """
    Set the subreddit list for a specific project.
    
    Parameters:
        subreddits (List[str]): List of subreddit names to store for the project.
        project_id (UUID): Identifier of the project to associate the subreddit list with.
    
    Returns:
        stored_subreddits (List[str]): The list of subreddit names that were stored for the project.
    """
    return _STORE.set_reddit_subreddits(subreddits, project_id)


def get_reddit_subreddits_for_project(project_id: ProjectId) -> Optional[List[str]]:
    """
    Retrieve the configured Reddit subreddit names for a specific project.

    Parameters:
        project_id (UUID): The project identifier to lookup subreddit configuration for.

    Returns:
        A list of subreddit names for the given project, or `None` if no subreddit configuration exists.
    """
    return _STORE.get_reddit_subreddits(project_id)


# Sentry Config API
def set_sentry_config(project_id: ProjectId, key: str, value: Any) -> None:
    """
    Set a Sentry configuration value for a project.

    Parameters:
        project_id (ProjectId): Project identifier.
        key (str): Config key (e.g., "webhook_secret", "environments", "levels").
        value (Any): Config value to store.
    """
    return _STORE.set_sentry_config(project_id, key, value)


def get_sentry_config(project_id: ProjectId, key: str) -> Optional[Any]:
    """
    Get a Sentry configuration value for a project.

    Parameters:
        project_id (ProjectId): Project identifier.
        key (str): Config key to retrieve.

    Returns:
        Optional[Any]: Config value if it exists, None otherwise.
    """
    return _STORE.get_sentry_config(project_id, key)


def set_splunk_config(project_id: ProjectId, key: str, value: Any) -> None:
    """
    Set a Splunk configuration value for a project.

    Parameters:
        project_id (ProjectId): Project identifier.
        key (str): Config key (e.g., "webhook_token", "allowed_searches", "enabled").
        value (Any): Config value to store.
    """
    return _STORE.set_splunk_config(project_id, key, value)


def get_splunk_config(project_id: ProjectId, key: str) -> Optional[Any]:
    """
    Get a Splunk configuration value for a project.

    Parameters:
        project_id (ProjectId): Project identifier.
        key (str): Config key to retrieve.

    Returns:
        Optional[Any]: Config value if it exists, None otherwise.
    """
    return _STORE.get_splunk_config(project_id, key)


def set_datadog_config(project_id: ProjectId, key: str, value: Any) -> None:
    """
    Set a Datadog configuration value for a project.

    Parameters:
        project_id (ProjectId): Project identifier.
        key (str): Config key (e.g., "webhook_secret", "monitors", "enabled").
        value (Any): Config value to store.
    """
    return _STORE.set_datadog_config(project_id, key, value)


def get_datadog_config(project_id: ProjectId, key: str) -> Optional[Any]:
    """
    Get a Datadog configuration value for a project.

    Parameters:
        project_id (ProjectId): Project identifier.
        key (str): Config key to retrieve.

    Returns:
        Optional[Any]: Config value if it exists, None otherwise.
    """
    return _STORE.get_datadog_config(project_id, key)


def set_posthog_config(project_id: ProjectId, key: str, value: Any) -> None:
    """
    Set a PostHog configuration value for a project.

    Parameters:
        project_id (ProjectId): Project identifier.
        key (str): Config key (e.g., "event_types", "enabled").
        value (Any): Config value to store.
    """
    return _STORE.set_posthog_config(project_id, key, value)


def get_posthog_config(project_id: ProjectId, key: str) -> Optional[Any]:
    """
    Get a PostHog configuration value for a project.

    Parameters:
        project_id (ProjectId): Project identifier.
        key (str): Config key to retrieve.

    Returns:
        Optional[Any]: Config value if it exists, None otherwise.
    """
    return _STORE.get_posthog_config(project_id, key)


def set_datadog_webhook_secret_for_project(secret: str, project_id: ProjectId) -> str:
    """
    Set the Datadog webhook secret for a specific project.

    Parameters:
        secret (str): Webhook secret to use for signature verification.
        project_id (UUID): Identifier of the project to associate the secret with.

    Returns:
        str: The secret that was stored.
    """
    return _STORE.set_datadog_webhook_secret(secret, project_id)


def get_datadog_webhook_secret_for_project(project_id: ProjectId) -> Optional[str]:
    """
    Retrieve the configured Datadog webhook secret for a project.

    Parameters:
        project_id (UUID): The project identifier to lookup webhook secret for.

    Returns:
        str: The webhook secret for the project, or None if no secret is configured.
    """
    return _STORE.get_datadog_webhook_secret(project_id)


def set_datadog_monitors_for_project(monitors: List[str], project_id: ProjectId) -> List[str]:
    """
    Set the list of Datadog monitor IDs to track for a project.

    Parameters:
        monitors (List[str]): List of monitor IDs or ["*"] for all monitors.
        project_id (UUID): Identifier of the project to associate the monitors with.

    Returns:
        List[str]: The list of monitor IDs that was stored.
    """
    return _STORE.set_datadog_monitors(monitors, project_id)


def get_datadog_monitors_for_project(project_id: ProjectId) -> Optional[List[str]]:
    """
    Retrieve the configured Datadog monitor IDs for a project.

    Parameters:
        project_id (UUID): The project identifier to lookup monitors for.

    Returns:
        List[str]: The monitor IDs for the project, or None if no configuration exists.
    """
    return _STORE.get_datadog_monitors(project_id)

# Coding Plan API
def add_coding_plan(plan: CodingPlan) -> CodingPlan:
    """
    Store a CodingPlan in the backend.
    """
    return _STORE.add_coding_plan(plan)

def get_coding_plan(cluster_id: str) -> Optional[CodingPlan]:
    """
    Retrieve a CodingPlan by cluster_id.
    """
    return _STORE.get_coding_plan(cluster_id)

def clear_coding_plans():
    """
    Remove all stored CodingPlan entries from the backend.
    """
    if isinstance(_STORE, InMemoryStore):
        _STORE.coding_plans.clear()
    elif isinstance(_STORE, RedisStore):
        keys = list(_STORE._scan_iter("coding_plan:*"))
        if keys:
            _STORE._delete(*keys)
