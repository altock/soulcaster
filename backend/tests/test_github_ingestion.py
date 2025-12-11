from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

import main as backend_main
from github_client import issue_to_feedback_item
from main import app
from models import FeedbackItem
from store import (
    get_all_feedback_items,
    get_unclustered_feedback,
    add_feedback_items_batch,
    get_feedback_by_external_ids_batch,
    remove_from_unclustered_batch,
    RedisStore,
)

client = TestClient(app)


def setup_function():
    # Reset in-memory sync metadata between tests
    backend_main.GITHUB_SYNC_STATE.clear()


def test_issue_to_feedback_item_shape(project_context):
    pid = project_context["project_id"]
    issue = {
        "id": 123,
        "number": 42,
        "title": "Sample issue",
        "body": "Issue body",
        "state": "open",
        "html_url": "https://github.com/org/repo/issues/42",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
        "labels": [{"name": "bug"}],
        "user": {"login": "octocat"},
        "assignees": [{"login": "helper"}],
        "milestone": {"title": "v1"},
    }

    item = issue_to_feedback_item(issue, "org/repo", pid)
    assert item.source == "github"
    assert item.repo == "org/repo"
    assert item.github_issue_number == 42
    assert item.github_issue_url.endswith("/42")
    assert item.metadata["labels"] == ["bug"]
    assert item.metadata["author"] == "octocat"
    assert item.status == "open"


def test_sync_github_repo_first_sync(project_context, monkeypatch):
    pid = project_context["project_id"]

    issue_open = {
        "id": 1,
        "number": 10,
        "title": "Open issue",
        "body": "Needs fixing",
        "state": "open",
        "html_url": "https://github.com/org/repo/issues/10",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
        "labels": [],
        "user": {"login": "alice"},
        "assignees": [],
    }
    issue_closed = issue_open | {
        "id": 2,
        "number": 11,
        "title": "Closed issue",
        "state": "closed",
        "html_url": "https://github.com/org/repo/issues/11",
    }

    monkeypatch.setattr(
        "main.fetch_repo_issues",
        lambda owner, repo, since=None, **kwargs: [issue_open, issue_closed],
    )

    resp = client.post(f"/ingest/github/sync/org/repo?project_id={pid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["new_issues"] == 2
    assert data["closed_issues"] == 1

    # Ensure feedback stored
    items = get_all_feedback_items()
    assert len(items) == 2

    # Closed issue should not remain in unclustered
    unclustered = get_unclustered_feedback(pid)
    assert len(unclustered) == 1
    assert unclustered[0].title == "Open issue"


def test_sync_github_repo_incremental(project_context, monkeypatch):
    pid = project_context["project_id"]
    calls = {"first_since": None, "second_since": None}

    issue_open = {
        "id": 3,
        "number": 12,
        "title": "First sync issue",
        "body": "First body",
        "state": "open",
        "html_url": "https://github.com/org/repo/issues/12",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
        "labels": [],
        "user": {"login": "alice"},
        "assignees": [],
    }

    def first_fetch(owner, repo, since=None, **kwargs):
        calls["first_since"] = since
        return [issue_open]

    def second_fetch(owner, repo, since=None, **kwargs):
        calls["second_since"] = since
        return []

    monkeypatch.setattr("main.fetch_repo_issues", first_fetch)
    first_resp = client.post(f"/ingest/github/sync/org/repo?project_id={pid}")
    assert first_resp.status_code == 200

    monkeypatch.setattr("main.fetch_repo_issues", second_fetch)
    second_resp = client.post(f"/ingest/github/sync/org/repo?project_id={pid}")
    assert second_resp.status_code == 200

    assert calls["first_since"] is None
    assert calls["second_since"] is not None


def test_sync_github_repo_dedup_and_update_counts(project_context, monkeypatch):
    pid = project_context["project_id"]
    issue_open = {
        "id": 99,
        "number": 25,
        "title": "Original title",
        "body": "Original body",
        "state": "open",
        "html_url": "https://github.com/org/repo/issues/25",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
        "labels": [],
        "user": {"login": "alice"},
        "assignees": [],
    }

    # First sync returns the open issue
    monkeypatch.setattr(
        "main.fetch_repo_issues", lambda owner, repo, since=None, **kwargs: [issue_open]
    )
    first_resp = client.post(f"/ingest/github/sync/org/repo?project_id={pid}")
    assert first_resp.status_code == 200
    first_data = first_resp.json()
    assert first_data["new_issues"] == 1
    assert first_data["updated_issues"] == 0

    # Second sync returns the same issue (simulating an update); should not duplicate
    updated_issue = issue_open | {"title": "Retitled", "updated_at": "2024-01-03T00:00:00Z"}
    monkeypatch.setattr(
        "main.fetch_repo_issues",
        lambda owner, repo, since=None, **kwargs: [updated_issue],
    )
    second_resp = client.post(f"/ingest/github/sync/org/repo?project_id={pid}")
    assert second_resp.status_code == 200
    second_data = second_resp.json()
    assert second_data["new_issues"] == 0
    assert second_data["updated_issues"] == 1

    # Still only one feedback item stored
    items = get_all_feedback_items(pid)
    assert len(items) == 1


class _FakeRedisPipeline:
    """
    Fake pipeline for _FakeRedis to support batched operations in tests.
    """

    def __init__(self, fake_redis):
        self._fake = fake_redis
        self._commands = []

    def hgetall(self, key):
        self._commands.append(("hgetall", key))
        return self

    def hset(self, key, mapping=None, **kwargs):
        self._commands.append(("hset", key, mapping or kwargs))
        return self

    def zadd(self, key, mapping):
        self._commands.append(("zadd", key, mapping))
        return self

    def sadd(self, key, member):
        self._commands.append(("sadd", key, member))
        return self

    def srem(self, key, member):
        self._commands.append(("srem", key, member))
        return self

    def set(self, key, value):
        self._commands.append(("set", key, value))
        return self

    def get(self, key):
        self._commands.append(("get", key))
        return self

    def execute(self):
        results = []
        for cmd, *args in self._commands:
            if cmd == "hgetall":
                results.append(self._fake.hgetall(args[0]))
            elif cmd == "hset":
                self._fake.hset(args[0], mapping=args[1])
                results.append(True)
            elif cmd == "zadd":
                self._fake.zadd(args[0], args[1])
                results.append(True)
            elif cmd == "sadd":
                self._fake.sadd(args[0], args[1])
                results.append(True)
            elif cmd == "srem":
                self._fake.srem(args[0], args[1])
                results.append(True)
            elif cmd == "set":
                self._fake.set(args[0], args[1])
                results.append(True)
            elif cmd == "get":
                results.append(self._fake.get(args[0]))
            else:
                raise NotImplementedError(f"_FakeRedisPipeline does not support command: {cmd}")
        return results


class _FakeRedis:
    """
    Minimal Redis-compatible stub for RedisStore tests (no external services).
    """

    def __init__(self):
        self._hashes = {}
        self._strings = {}
        self._sets = {}
        self._zsets = {}

    def pipeline(self):
        return _FakeRedisPipeline(self)

    # String ops
    def set(self, key, value):
        self._strings[key] = value

    def get(self, key):
        return self._strings.get(key)

    # Hash ops
    def hset(self, key, mapping=None, **kwargs):
        mapping = mapping or kwargs
        self._hashes.setdefault(key, {}).update(mapping)

    def hgetall(self, key):
        return self._hashes.get(key, {})

    # Set ops
    def sadd(self, key, member):
        self._sets.setdefault(key, set()).add(member)

    def smembers(self, key):
        return set(self._sets.get(key, set()))

    def srem(self, key, member):
        if key in self._sets:
            self._sets[key].discard(member)

    # Sorted set ops
    def zadd(self, key, mapping):
        self._zsets.setdefault(key, [])
        for member, score in mapping.items():
            self._zsets[key] = [(s, m) for (s, m) in self._zsets[key] if m != member]
            self._zsets[key].append((score, member))
        self._zsets[key].sort(key=lambda x: x[0])

    def zrange(self, key, start, stop, desc=False):
        items = self._zsets.get(key, [])
        if desc:
            items = list(reversed(items))
        members = [m for _, m in items]
        if stop == -1:
            return members[start:]
        return members[start : stop + 1]

    # Delete/scan helpers (minimal)
    def delete(self, *keys):
        for key in keys:
            self._strings.pop(key, None)
            self._hashes.pop(key, None)
            self._sets.pop(key, None)
            self._zsets.pop(key, None)

    def scan_iter(self, pattern):
        prefix = pattern.rstrip("*")
        for key in list(self._strings) + list(self._hashes) + list(self._sets) + list(self._zsets):
            if key.startswith(prefix):
                yield key


def test_redis_store_get_feedback_by_external_id(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr("store._redis_client_from_env", lambda: fake)
    monkeypatch.setattr("store._upstash_rest_client_from_env", lambda: None)
    redis_store = RedisStore()

    project_id = uuid4()
    item = FeedbackItem(
        id=uuid4(),
        project_id=project_id,
        source="github",
        external_id="ext-123",
        title="Redis item",
        body="",
        metadata={},
        created_at=datetime.now(timezone.utc),
    )

    redis_store.add_feedback_item(item)
    found = redis_store.get_feedback_by_external_id(project_id, "github", "ext-123")

    assert found is not None
    assert found.id == item.id
    assert found.external_id == "ext-123"


def test_redis_store_get_unclustered_feedback(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr("store._redis_client_from_env", lambda: fake)
    monkeypatch.setattr("store._upstash_rest_client_from_env", lambda: None)
    redis_store = RedisStore()

    project_id = uuid4()
    item = FeedbackItem(
        id=uuid4(),
        project_id=project_id,
        source="github",
        external_id="ext-999",
        title="Unclustered",
        body="",
        metadata={},
        created_at=datetime.now(timezone.utc),
    )

    redis_store.add_feedback_item(item)
    unclustered = redis_store.get_unclustered_feedback(str(project_id))

    assert len(unclustered) == 1
    assert unclustered[0].id == item.id


def test_auto_cluster_feedback_github_titles(project_context):
    pid = project_context["project_id"]
    item = FeedbackItem(
        id=uuid4(),
        project_id=pid,
        source="github",
        external_id="ext-777",
        title="Repo issue",
        body="",
        metadata={"repo": "org/repo"},
        created_at=datetime.now(timezone.utc),
    )

    cluster = backend_main._auto_cluster_feedback(item)
    assert cluster.title == "GitHub: org/repo"


def test_add_feedback_items_batch(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr("store._redis_client_from_env", lambda: fake)
    monkeypatch.setattr("store._upstash_rest_client_from_env", lambda: None)
    redis_store = RedisStore()

    project_id = uuid4()
    items = [
        FeedbackItem(
            id=uuid4(),
            project_id=project_id,
            source="github",
            external_id="ext-1",
            title="Item 1",
            body="",
            metadata={},
            created_at=datetime.now(timezone.utc),
        ),
        FeedbackItem(
            id=uuid4(),
            project_id=project_id,
            source="github",
            external_id="ext-2",
            title="Item 2",
            body="",
            metadata={},
            created_at=datetime.now(timezone.utc),
        ),
    ]

    redis_store.add_feedback_items_batch(items)
    unclustered = redis_store.get_unclustered_feedback(str(project_id))
    assert len(unclustered) == 2


def test_get_feedback_by_external_ids_batch(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr("store._redis_client_from_env", lambda: fake)
    monkeypatch.setattr("store._upstash_rest_client_from_env", lambda: None)
    redis_store = RedisStore()

    project_id = uuid4()
    item = FeedbackItem(
        id=uuid4(),
        project_id=project_id,
        source="github",
        external_id="ext-batch",
        title="Batch lookup",
        body="",
        metadata={},
        created_at=datetime.now(timezone.utc),
    )
    redis_store.add_feedback_item(item)

    found = redis_store.get_feedback_by_external_ids_batch(project_id, "github", ["ext-batch", "missing"])
    assert "ext-batch" in found
    assert found["ext-batch"].id == item.id
    assert "missing" not in found


def test_remove_from_unclustered_batch(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr("store._redis_client_from_env", lambda: fake)
    monkeypatch.setattr("store._upstash_rest_client_from_env", lambda: None)
    redis_store = RedisStore()

    project_id = uuid4()
    item1 = FeedbackItem(
        id=uuid4(),
        project_id=project_id,
        source="github",
        external_id="ext-remove-1",
        title="Remove 1",
        body="",
        metadata={},
        created_at=datetime.now(timezone.utc),
    )
    item2 = FeedbackItem(
        id=uuid4(),
        project_id=project_id,
        source="github",
        external_id="ext-remove-2",
        title="Remove 2",
        body="",
        metadata={},
        created_at=datetime.now(timezone.utc),
    )

    redis_store.add_feedback_items_batch([item1, item2])
    redis_store.remove_from_unclustered_batch([(item1.id, str(project_id)), (item2.id, str(project_id))])

    unclustered = redis_store.get_unclustered_feedback(str(project_id))
    assert len(unclustered) == 0


def test_sync_github_repo_uses_batch_operations(project_context, monkeypatch):
    pid = project_context["project_id"]
    backend_main.GITHUB_SYNC_STATE.clear()

    issue_open = {
        "id": 200,
        "number": 20,
        "title": "Batch issue",
        "body": "Body",
        "state": "open",
        "html_url": "https://github.com/org/repo/issues/20",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
        "labels": [],
        "user": {"login": "alice"},
        "assignees": [],
    }

    calls = {"lookup": 0, "add": 0, "remove": 0}

    monkeypatch.setattr(
        "main.fetch_repo_issues", lambda owner, repo, since=None, **kwargs: [issue_open]
    )

    orig_lookup = backend_main.get_feedback_by_external_ids_batch
    orig_add = backend_main.add_feedback_items_batch
    orig_remove = backend_main.remove_from_unclustered_batch

    def track_lookup(project_id, source, external_ids):
        calls["lookup"] += 1
        return orig_lookup(project_id, source, external_ids)

    def track_add(items):
        calls["add"] += 1
        return orig_add(items)

    def track_remove(pairs):
        calls["remove"] += 1
        return orig_remove(pairs)

    monkeypatch.setattr("main.get_feedback_by_external_ids_batch", track_lookup)
    monkeypatch.setattr("main.add_feedback_items_batch", track_add)
    monkeypatch.setattr("main.remove_from_unclustered_batch", track_remove)

    resp = client.post(f"/ingest/github/sync/org/repo?project_id={pid}")
    assert resp.status_code == 200
    assert calls["lookup"] == 1
    assert calls["add"] == 1
    # No closed issues in this case, so remove may be 0
    assert calls["remove"] in (0, 1)
