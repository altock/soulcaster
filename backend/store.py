"""Storage layer for FeedbackItems and IssueClusters.

Defaults to in-memory dicts, but will use Redis if configured (Upstash-friendly).
"""

import json
import os
import time
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import UUID

import requests

try:
    from .models import FeedbackItem, IssueCluster, AgentJob, Project, User
except ImportError:
    from models import FeedbackItem, IssueCluster, AgentJob, Project, User

try:
    import redis  # type: ignore
except ImportError:
    redis = None


def _dt_to_iso(dt: datetime) -> str:
    return dt.isoformat()


def _iso_to_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


# ---------- Redis (standard) client helpers ----------


def _redis_client_from_env():
    """Return a redis-py client if REDIS_URL/UPSTASH_REDIS_URL is set."""
    url = os.getenv("REDIS_URL") or os.getenv("UPSTASH_REDIS_URL")
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
        result = self._cmd("SMEMBERS", key)
        return result or []

    def srem(self, key: str, member: str):
        """Remove member from set."""
        return self._cmd("SREM", key, member)

    def delete(self, *keys: str):
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
    url = os.getenv("UPSTASH_REDIS_REST_URL")
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
    if url and token:
        return UpstashRESTClient(url, token)
    return None


# ---------- Store backends ----------


class InMemoryStore:
    def __init__(self):
        self.feedback_items: Dict[UUID, FeedbackItem] = {}
        self.issue_clusters: Dict[UUID, IssueCluster] = {}
        self.agent_jobs: Dict[UUID, AgentJob] = {}
        self.projects: Dict[UUID, Project] = {}
        self.users: Dict[UUID, User] = {}
        self.reddit_subreddits: Dict[UUID, List[str]] = {}
        self.external_index: Dict[Tuple[UUID, str, str], UUID] = {}
        self.unclustered_feedback_ids: set[UUID] = set()  # Phase 1: track unclustered items

    # Feedback
    def add_feedback_item(self, item: FeedbackItem) -> FeedbackItem:
        if item.project_id not in self.projects:
            raise KeyError("project not found")
        if item.external_id:
            key = (item.project_id, item.source, item.external_id)
            existing_id = self.external_index.get(key)
            if existing_id:
                return self.feedback_items[existing_id]
            self.external_index[key] = item.id
        self.feedback_items[item.id] = item
        # Add to unclustered set (Phase 1: ingestion moat)
        self.unclustered_feedback_ids.add(item.id)
        return item

    def get_feedback_item(self, item_id: UUID) -> Optional[FeedbackItem]:
        return self.feedback_items.get(item_id)

    def get_all_feedback_items(self) -> List[FeedbackItem]:
        return list(self.feedback_items.values())

    def get_unclustered_feedback(self) -> List[FeedbackItem]:
        """Get all feedback items that haven't been clustered yet."""
        return [self.feedback_items[item_id] for item_id in self.unclustered_feedback_ids if item_id in self.feedback_items]

    def remove_from_unclustered(self, feedback_id: UUID):
        """Remove item from unclustered set (called after clustering)."""
        self.unclustered_feedback_ids.discard(feedback_id)

    def clear_feedback_items(self):
        self.feedback_items.clear()
        self.external_index.clear()
        self.unclustered_feedback_ids.clear()

    # Clusters
    def add_cluster(self, cluster: IssueCluster) -> IssueCluster:
        self.issue_clusters[cluster.id] = cluster
        return cluster

    def get_cluster(self, cluster_id: str) -> Optional[IssueCluster]:
        return self.issue_clusters.get(cluster_id)

    def get_all_clusters(self) -> List[IssueCluster]:
        return list(self.issue_clusters.values())

    def update_cluster(self, cluster_id: str, **updates) -> IssueCluster:
        cluster = self.issue_clusters[cluster_id]
        updated_cluster = cluster.model_copy(update=updates)
        self.issue_clusters[cluster_id] = updated_cluster
        return updated_cluster

    def clear_clusters(self):
        self.issue_clusters.clear()

    # Config (Reddit)
    def set_reddit_subreddits(self, subreddits: List[str], project_id: UUID) -> List[str]:
        if project_id not in self.projects:
            raise KeyError("project not found")
        self.reddit_subreddits[project_id] = subreddits
        return subreddits

    def get_reddit_subreddits(self, project_id: UUID) -> Optional[List[str]]:
        return self.reddit_subreddits.get(project_id)

    def clear_config(self):
        self.reddit_subreddits = {}

    # Jobs
    def add_job(self, job: AgentJob) -> AgentJob:
        if job.project_id not in self.projects:
            raise KeyError("project not found")
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
        self.agent_jobs.clear()

    def get_feedback_by_external_id(self, project_id: UUID, source: str, external_id: str) -> Optional[FeedbackItem]:
        key = (project_id, source, external_id)
        item_id = self.external_index.get(key)
        if not item_id:
            return None
        return self.feedback_items.get(item_id)

    # Users / Projects
    def create_user_with_default_project(self, user: User, default_project: Project) -> Project:
        self.users[user.id] = user
        self.projects[default_project.id] = default_project
        return default_project

    def create_project(self, project: Project) -> Project:
        self.projects[project.id] = project
        return project

    def get_projects_for_user(self, user_id: UUID) -> List[Project]:
        return [p for p in self.projects.values() if p.user_id == user_id]

    def get_project(self, project_id: UUID) -> Optional[Project]:
        return self.projects.get(project_id)


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

    # Key helpers
    @staticmethod
    def _feedback_key(item_id: UUID) -> str:
        return f"feedback:{item_id}"

    @staticmethod
    def _feedback_created_key() -> str:
        return "feedback:created"

    @staticmethod
    def _feedback_source_key(source: str) -> str:
        return f"feedback:source:{source}"

    @staticmethod
    def _feedback_external_key(project_id: str, source: str, external_id: str) -> str:
        return f"feedback:external:{project_id}:{source}:{external_id}"

    @staticmethod
    def _feedback_unclustered_key() -> str:
        """Key for the set of feedback items that haven't been clustered yet."""
        return "feedback:unclustered"

    @staticmethod
    def _cluster_key(cluster_id: str) -> str:
        return f"cluster:{cluster_id}"

    @staticmethod
    def _cluster_items_key(cluster_id: str) -> str:
        return f"cluster:items:{cluster_id}"

    @staticmethod
    def _cluster_all_key() -> str:
        return "clusters:all"

    @staticmethod
    def _reddit_subreddits_key(project_id: UUID) -> str:
        return f"config:reddit:subreddits:{project_id}"

    @staticmethod
    def _job_key(job_id: UUID) -> str:
        return f"job:{job_id}"

    @staticmethod
    def _cluster_jobs_key(cluster_id: str) -> str:
        return f"cluster:jobs:{cluster_id}"

    @staticmethod
    def _user_key(user_id: UUID) -> str:
        return f"user:{user_id}"

    @staticmethod
    def _project_key(project_id: UUID) -> str:
        return f"project:{project_id}"

    @staticmethod
    def _user_projects_key(user_id: UUID) -> str:
        return f"user:projects:{user_id}"

    # Feedback
    def add_feedback_item(self, item: FeedbackItem) -> FeedbackItem:
        payload = item.model_dump()
        if isinstance(payload["created_at"], datetime):
            payload["created_at"] = _dt_to_iso(payload["created_at"])
        
        # Serialize metadata if present
        if isinstance(payload.get("metadata"), dict):
            payload["metadata"] = json.dumps(payload["metadata"])

        # Use HSET (Hash) instead of SET (JSON)
        # Convert all values to strings for HSET
        hash_payload = {k: str(v) for k, v in payload.items() if v is not None}
        
        key = self._feedback_key(item.id)
        self._hset(key, hash_payload)

        ts = item.created_at.timestamp() if isinstance(item.created_at, datetime) else time.time()
        self._zadd(self._feedback_created_key(), ts, str(item.id))
        self._zadd(self._feedback_source_key(item.source), ts, str(item.id))
        
        # Add to unclustered set (Phase 1: ingestion moat)
        self._sadd(self._feedback_unclustered_key(), str(item.id))
        
        if item.external_id:
            self._set(self._feedback_external_key(str(item.project_id), item.source, item.external_id), str(item.id))
        return item

    def get_feedback_item(self, item_id: UUID) -> Optional[FeedbackItem]:
        # Try HGETALL first (new format)
        key = self._feedback_key(item_id)
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

    def get_all_feedback_items(self) -> List[FeedbackItem]:
        ids = self._zrange(self._feedback_created_key(), 0, -1)
        items: List[FeedbackItem] = []
        for item_id in ids:
            try:
                # ids are stored as strings in redis, convert to UUID
                item = self.get_feedback_item(UUID(item_id))
                if item:
                    items.append(item)
            except ValueError:
                continue
        return items

    def get_unclustered_feedback(self) -> List[FeedbackItem]:
        """Get all feedback items that haven't been clustered yet."""
        unclustered_ids = self._smembers(self._feedback_unclustered_key())
        items: List[FeedbackItem] = []
        for item_id in unclustered_ids:
            try:
                item = self.get_feedback_item(UUID(item_id))
                if item:
                    items.append(item)
            except ValueError:
                continue
        return items

    def remove_from_unclustered(self, feedback_id: UUID):
        """Remove item from unclustered set (called after clustering)."""
        if self.mode == "redis":
            self.client.srem(self._feedback_unclustered_key(), str(feedback_id))
        else:
            # REST client now has srem method
            self.client.srem(self._feedback_unclustered_key(), str(feedback_id))

    def clear_feedback_items(self):
        # Remove keys matching feedback:* and related sorted sets
        feedback_keys = list(self._scan_iter("feedback:*"))
        if feedback_keys:
            self._delete(*feedback_keys)
        self._delete(self._feedback_created_key())
        self._delete(self._feedback_unclustered_key())  # Clear unclustered set
        # Source sets: optional to scan
        source_keys = list(self._scan_iter("feedback:source:*"))
        if source_keys:
            self._delete(*source_keys)
        external_keys = list(self._scan_iter("feedback:external:*"))
        if external_keys:
            self._delete(*external_keys)

    # Clusters
    def add_cluster(self, cluster: IssueCluster) -> IssueCluster:
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
        key = self._cluster_key(cluster.id)
        self._hset(key, hash_payload)
        
        self._sadd(self._cluster_all_key(), str(cluster.id))
        
        # store cluster items set
        items_key = self._cluster_items_key(cluster.id)
        if cluster.feedback_ids:
            for fid in cluster.feedback_ids:
                self._sadd(items_key, str(fid))
        return cluster

    def get_cluster(self, cluster_id: str) -> Optional[IssueCluster]:
        key = self._cluster_key(cluster_id)
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
            items_key = self._cluster_items_key(cluster_id)
            ids = self._smembers(items_key)
            data["feedback_ids"] = ids

        return IssueCluster(**data)

    def get_all_clusters(self) -> List[IssueCluster]:
        ids = self._smembers(self._cluster_all_key())
        clusters: List[IssueCluster] = []
        for cid in ids:
            # ids are stored as strings in redis (can be UUID or custom format)
            cluster = self.get_cluster(cid)
            if cluster:
                clusters.append(cluster)
        return clusters

    def update_cluster(self, cluster_id: str, **updates) -> IssueCluster:
        cluster = self.get_cluster(cluster_id)
        if not cluster:
            raise KeyError(f"Cluster {cluster_id} not found")
        updated = cluster.model_copy(update=updates)
        return self.add_cluster(updated)

    def clear_clusters(self):
        cluster_keys = list(self._scan_iter("cluster:*")) + [self._cluster_all_key()]
        if cluster_keys:
            self._delete(*cluster_keys)

    # Config (Reddit)
    def set_reddit_subreddits(self, subreddits: List[str], project_id: UUID) -> List[str]:
        payload = json.dumps(subreddits)
        self._set(self._reddit_subreddits_key(project_id), payload)
        return subreddits

    def get_reddit_subreddits(self, project_id: UUID) -> Optional[List[str]]:
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
        keys = list(self._scan_iter("config:reddit:subreddits:*"))
        if keys:
            self._delete(*keys)

    # Jobs
    def add_job(self, job: AgentJob) -> AgentJob:
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
        job_keys = list(self._scan_iter("job:*")) + list(self._scan_iter("cluster:jobs:*"))
        if job_keys:
            self._delete(*job_keys)

    def get_feedback_by_external_id(self, project_id: UUID, source: str, external_id: str) -> Optional[FeedbackItem]:
        if not external_id:
            return None
        key = self._feedback_external_key(str(project_id), source, external_id)
        existing_id = self._get(key)
        if not existing_id:
            return None
        try:
            return self.get_feedback_item(UUID(existing_id))
        except ValueError:
            return None

    # Users / Projects
    def create_user_with_default_project(self, user: User, default_project: Project) -> Project:
        payload = user.model_dump()
        if isinstance(payload.get("created_at"), datetime):
            payload["created_at"] = _dt_to_iso(payload["created_at"])

        hash_payload = {k: str(v) for k, v in payload.items() if v is not None}
        self._hset(self._user_key(user.id), hash_payload)

        return self.create_project(default_project)

    def create_project(self, project: Project) -> Project:
        payload = project.model_dump()
        if isinstance(payload.get("created_at"), datetime):
            payload["created_at"] = _dt_to_iso(payload["created_at"])

        hash_payload = {k: str(v) for k, v in payload.items() if v is not None}
        self._hset(self._project_key(project.id), hash_payload)
        self._sadd(self._user_projects_key(project.user_id), str(project.id))
        return project

    def get_projects_for_user(self, user_id: UUID) -> List[Project]:
        project_ids = self._smembers(self._user_projects_key(user_id))
        projects: List[Project] = []
        for pid in project_ids:
            try:
                project = self.get_project(UUID(pid))
            except ValueError:
                continue
            if project:
                projects.append(project)
        return projects

    def get_project(self, project_id: UUID) -> Optional[Project]:
        data = self._hgetall(self._project_key(project_id))
        if not data:
            return None

        if isinstance(data.get("created_at"), str):
            data["created_at"] = _iso_to_dt(data["created_at"])

        return Project(**data)

    # --- client wrappers ---
    def _set(self, key: str, value: str):
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


def get_feedback_item(item_id: UUID) -> Optional[FeedbackItem]:
    return _STORE.get_feedback_item(item_id)


def get_all_feedback_items() -> List[FeedbackItem]:
    return _STORE.get_all_feedback_items()


def get_feedback_by_external_id(project_id: UUID, source: str, external_id: str) -> Optional[FeedbackItem]:
    if not external_id:
        return None
    if hasattr(_STORE, "get_feedback_by_external_id"):
        return _STORE.get_feedback_by_external_id(project_id, source, external_id)
    # Fallback: linear scan (should rarely happen)
    for item in _STORE.get_all_feedback_items():
        if item.project_id == project_id and item.source == source and item.external_id == external_id:
            return item
    return None


def clear_feedback_items():
    _STORE.clear_feedback_items()


def add_cluster(cluster: IssueCluster) -> IssueCluster:
    return _STORE.add_cluster(cluster)


def get_cluster(cluster_id: str) -> Optional[IssueCluster]:
    return _STORE.get_cluster(cluster_id)


def get_all_clusters() -> List[IssueCluster]:
    return _STORE.get_all_clusters()


def update_cluster(cluster_id: str, **updates) -> IssueCluster:
    return _STORE.update_cluster(cluster_id, **updates)


def clear_clusters():
    _STORE.clear_clusters()


def set_reddit_subreddits(subreddits: List[str]) -> List[str]:
    raise TypeError("set_reddit_subreddits requires project_id")


def get_reddit_subreddits() -> Optional[List[str]]:
    raise TypeError("get_reddit_subreddits requires project_id")


def clear_config():
    # Primarily for tests
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
    if hasattr(_STORE, "clear_jobs"):
        _STORE.clear_jobs()


def get_unclustered_feedback() -> List[FeedbackItem]:
    """Get all feedback items that haven't been clustered yet.
    
    Returns:
        List of FeedbackItem objects that are in the unclustered set.
    """
    return _STORE.get_unclustered_feedback()


def remove_from_unclustered(feedback_id: UUID):
    """Remove a feedback item from the unclustered set.
    
    This should be called after the item has been added to a cluster.
    
    Args:
        feedback_id: UUID of the feedback item to remove from unclustered set.
    """
    return _STORE.remove_from_unclustered(feedback_id)


# User / Project API
def create_user_with_default_project(user: User, project: Project) -> Project:
    return _STORE.create_user_with_default_project(user, project)


def create_project(project: Project) -> Project:
    return _STORE.create_project(project)


def get_projects_for_user(user_id: UUID) -> List[Project]:
    return _STORE.get_projects_for_user(user_id)


def get_project(project_id: UUID) -> Optional[Project]:
    return _STORE.get_project(project_id)


# Project-scoped config API
def set_reddit_subreddits_for_project(subreddits: List[str], project_id: UUID) -> List[str]:
    return _STORE.set_reddit_subreddits(subreddits, project_id)


def get_reddit_subreddits_for_project(project_id: UUID) -> Optional[List[str]]:
    return _STORE.get_reddit_subreddits(project_id)
