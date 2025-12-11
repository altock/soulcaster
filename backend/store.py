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

from models import FeedbackItem, IssueCluster, AgentJob, Project, User

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
        return self._cmd("SET", key, value)

    def get(self, key: str) -> Optional[str]:
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
        Initialize an in-memory storage backend holding feedback, clusters, jobs, projects, users, configs, and lookup indices.
        
        Attributes:
            feedback_items: Mapping from feedback ID to FeedbackItem.
            issue_clusters: Mapping from cluster ID to IssueCluster.
            agent_jobs: Mapping from job ID to AgentJob.
            projects: Mapping from project ID to Project.
            users: Mapping from user ID to User.
            reddit_subreddits: Per-project subreddit list mapping (project ID -> list of subreddit names).
            external_index: Mapping from (project_id, source, external_id) to feedback ID for deduplication/lookup.
            unclustered_feedback_ids: Per-project set of feedback IDs that have not been assigned to any cluster.
        """
        self.feedback_items: Dict[UUID, FeedbackItem] = {}
        self.issue_clusters: Dict[str, IssueCluster] = {}
        self.agent_jobs: Dict[UUID, AgentJob] = {}
        self.projects: Dict[str, Project] = {}
        self.users: Dict[str, User] = {}
        self.reddit_subreddits: Dict[str, List[str]] = {}
        self.external_index: Dict[Tuple[str, str, str], UUID] = {}
        # Track unclustered feedback per project (project_id -> set(feedback_ids))
        self.unclustered_feedback_ids: Dict[str, set[UUID]] = {}

    # Feedback
    def add_feedback_item(self, item: FeedbackItem) -> FeedbackItem:
        """
        Add a FeedbackItem to the store, indexing by external_id and marking it as unclustered.
        
        Parameters:
            item (FeedbackItem): The feedback item to add; must reference an existing project.
        
        Returns:
            FeedbackItem: The stored feedback item (the newly added item or an existing item when an external_id duplicate is detected).
        
        Raises:
            KeyError: If the item's project_id does not exist in the store.
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
        Remove all stored Reddit subreddit configurations for all projects.
        
        This clears any per-project subreddit lists so subsequent lookups return no configuration.
        """
        self.reddit_subreddits = {}

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

    def get_jobs_by_cluster(self, cluster_id: str) -> List[AgentJob]:
        return [
            job for job in self.agent_jobs.values() if job.cluster_id == cluster_id
        ]

    def get_all_jobs(self) -> List[AgentJob]:
        return list(self.agent_jobs.values())

    def clear_jobs(self):
        """
        Clear all AgentJob entries from the store.
        """
        self.agent_jobs.clear()

    # Users / Projects
    def create_user_with_default_project(self, user: User, default_project: Project) -> Project:
        """
        Create a user record and its default project in the in-memory store.
        
        Parameters:
            user (User): The user to create or store.
            default_project (Project): The user's default project to create or store.
        
        Returns:
            Project: The stored default project.
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
        """Match dashboard: clusters:${projectId}:all"""
        return f"clusters:{project_id}:all"

    @staticmethod
    def _reddit_subreddits_key(project_id: UUID) -> str:
        """
        Constructs the Redis key used to store a project's Reddit subreddit list.
        
        Returns:
            str: Redis key in the form "config:reddit:subreddits:{project_id}".
        """
        return f"config:reddit:subreddits:{project_id}"

    @staticmethod
    def _job_key(job_id: UUID) -> str:
        """
        Builds the Redis key for a job identifier.
        
        Returns:
            The Redis key string in the form "job:<job_id>".
        """
        return f"job:{job_id}"

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
            
        # Exclude feedback_ids from Hash (stored in set)
        if "feedback_ids" in payload:
            del payload["feedback_ids"]

        # Use HSET (Hash)
        hash_payload = {k: str(v) for k, v in payload.items() if v is not None}
        key = self._cluster_key(project_id, cluster.id)
        self._hset(key, hash_payload)
        
        self._sadd(self._cluster_all_key(project_id), str(cluster.id))
        
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
                    # Get cluster IDs for this project
                    cluster_ids = self._smembers(self._cluster_all_key(pid))
                    # Load each cluster
                    for cid in cluster_ids:
                        cluster = self.get_cluster(pid, cid)
                        if cluster:
                            clusters.append(cluster)
            return clusters

        ids = self._smembers(self._cluster_all_key(project_id))
        clusters: List[IssueCluster] = []
        for cid in ids:
            # ids are stored as strings in redis (can be UUID or custom format)
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
        Remove all per-project Reddit subreddit configuration entries from the store.
        
        This deletes every key matching the `config:reddit:subreddits:*` pattern so no project-specific subreddit lists remain.
        """
        keys = list(self._scan_iter("config:reddit:subreddits:*"))
        if keys:
            self._delete(*keys)

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
        job = self.get_job(job_id)
        if not job:
            raise KeyError(f"Job {job_id} not found")
        updated = job.model_copy(update=updates)
        return self.add_job(updated)

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
        job_keys = list(self._scan_iter("job:*")) + list(self._scan_iter("cluster:jobs:*"))
        if job_keys:
            self._delete(*job_keys)

    def get_feedback_by_external_id(self, project_id: UUID, source: str, external_id: str) -> Optional[FeedbackItem]:
        """
        Resolve a feedback item by its external identifier within a project.
        
        Parameters:
            project_id (UUID): Project that owns the external identifier.
            source (str): External source name (e.g., "github", "zendesk").
            external_id (str): External identifier provided by the source.
        
        Returns:
            FeedbackItem or None: The corresponding FeedbackItem if a mapping exists and points to a valid UUID, `None` if no mapping exists, `external_id` is empty, or the stored id is invalid.
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


def clear_jobs():
    """
    Remove all agent job records and their indexes from the active storage backend.
    
    If the configured store exposes a `clear_jobs` operation, this function invokes it; otherwise it does nothing.
    """
    if hasattr(_STORE, "clear_jobs"):
        _STORE.clear_jobs()


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