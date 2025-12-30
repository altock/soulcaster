# Upstash Vector Optimization Implementation Checklist

## Phase 1: Query Batching (HIGH PRIORITY - 4 hours)

### [ ] 1. Verify SDK Version
- [ ] Check current upstash-vector version: `pip show upstash-vector`
- [ ] Minimum required: `0.6.0` (for `query_many()` support)
- [ ] If < 0.6.0: Update `backend/pyproject.toml`, run `uv sync`

**Command**:
```bash
cd /Users/sam/code/soulcaster/backend
pip show upstash-vector
```

### [ ] 2. Add `find_similar_batch()` Method
**File**: `/Users/sam/code/soulcaster/backend/vector_store.py`

- [ ] Copy code from Section 1 "Solution: Implement Query Batching" → Implementation Code
- [ ] Add method after `find_similar_in_cluster()` (around line 340)
- [ ] Verify imports are complete (List, Optional types)
- [ ] Add docstring with parameter descriptions

**Checklist**:
- [ ] Method signature matches spec
- [ ] Handles empty embeddings list
- [ ] Fallback for older SDK versions implemented
- [ ] Filtering by exclude_ids works per-query
- [ ] Returns List[List[SimilarFeedback]] correctly

### [ ] 3. Update Clustering Pipeline
**File**: `/Users/sam/code/soulcaster/backend/clustering_runner.py`

- [ ] Locate "Phase 1: Query vector DB" comment (around line 213)
- [ ] Replace sequential loop with batch call (see implementation code in Section 1)
- [ ] Add logging for batch operation:
  ```python
  logger.info(f"Batch querying {len(items)} embeddings...")
  ```
- [ ] Verify `existing_matches` dict is built correctly

**Changes**:
- [ ] Remove old loop (lines 215-223)
- [ ] Insert new batch code
- [ ] Verify indentation and variable names

### [ ] 4. Test Batch Implementation
**File**: Create `/Users/sam/code/soulcaster/backend/tests/test_vector_batch.py`

```python
import pytest
from vector_store import VectorStore

@pytest.mark.asyncio
async def test_find_similar_batch_vs_sequential():
    """Verify batch returns same results as sequential."""
    vs = VectorStore()

    # Test vectors (replace with real test data)
    embeddings = [
        [0.1] * 768,  # Dummy embedding
        [0.2] * 768,
        [0.3] * 768,
    ]

    # Sequential
    sequential = [
        vs.find_similar(emb, project_id="test", top_k=5)
        for emb in embeddings
    ]

    # Batch
    batch = vs.find_similar_batch(embeddings, project_id="test", top_k=5)

    # Verify
    assert len(batch) == len(sequential)
    for batch_res, seq_res in zip(batch, sequential):
        assert len(batch_res) == len(seq_res)
        if len(batch_res) > 0:
            assert batch_res[0].id == seq_res[0].id
```

- [ ] Create test file
- [ ] Run: `cd backend && uv run pytest tests/test_vector_batch.py -v`
- [ ] All tests pass ✅

### [ ] 5. Run Full Test Suite
```bash
cd /Users/sam/code/soulcaster/backend
uv run pytest tests/ -v --tb=short
```

- [ ] All existing tests pass ✅
- [ ] New test passes ✅
- [ ] No regressions in clustering tests

### [ ] 6. Benchmark Phase 1
**File**: Create `/Users/sam/code/soulcaster/backend/benchmark_vector.py`

```python
import time
from vector_store import get_vector_store
import numpy as np

def benchmark_batch_vs_sequential():
    vs = get_vector_store()

    # Generate test embeddings
    num_queries = 50
    embeddings = [
        np.random.randn(768).tolist()
        for _ in range(num_queries)
    ]

    # Sequential
    start = time.time()
    for emb in embeddings:
        vs.find_similar(emb, project_id="benchmark", top_k=10)
    sequential_time = time.time() - start

    # Batch
    start = time.time()
    vs.find_similar_batch(embeddings, project_id="benchmark", top_k=10)
    batch_time = time.time() - start

    print(f"Sequential (50 queries): {sequential_time:.2f}s")
    print(f"Batch (50 queries):      {batch_time:.2f}s")
    print(f"Speedup:                 {sequential_time/batch_time:.1f}x")

if __name__ == "__main__":
    benchmark_batch_vs_sequential()
```

- [ ] Run: `cd backend && python benchmark_vector.py`
- [ ] Record results (should see 3-5x speedup)
- [ ] Document in PR

---

## Phase 2: Monitoring & Metrics (HIGH PRIORITY - 1 hour)

### [ ] 1. Add Latency Instrumentation
**File**: `/Users/sam/code/soulcaster/backend/vector_store.py`

- [ ] Add imports at top:
  ```python
  import time
  from functools import wraps
  ```

- [ ] Add metrics dict after imports:
  ```python
  _metrics = {
      "find_similar_calls": 0,
      "find_similar_total_ms": 0,
      "find_similar_batch_calls": 0,
      "find_similar_batch_total_ms": 0,
  }
  ```

- [ ] Add decorator function (see Section 5 code)

- [ ] Apply decorator to methods:
  ```python
  @_timed_operation("find_similar")
  def find_similar(self, ...):
      # existing code
  ```

- [ ] Add `get_vector_store_metrics()` function at module end

### [ ] 2. Create Health Endpoint
**File**: `/Users/sam/code/soulcaster/backend/main.py`

- [ ] Add import: `from vector_store import get_vector_store_metrics`
- [ ] Add endpoint (after existing routes):
  ```python
  @app.get("/health/vector-metrics")
  async def vector_metrics():
      return {
          "vector_store": get_vector_store_metrics(),
          "timestamp": datetime.now(timezone.utc).isoformat(),
      }
  ```

- [ ] Test: `curl http://localhost:8000/health/vector-metrics`

### [ ] 3. Verify Logging
- [ ] Start backend: `just dev-backend`
- [ ] Check logs for latency measurements
- [ ] Verify no errors in metrics collection

---

## Phase 3: Embedding Cache (MEDIUM PRIORITY - 2 hours)

### [ ] 1. Create Cache Module
**File**: Create `/Users/sam/code/soulcaster/backend/embedding_cache.py`

- [ ] Copy full implementation from Section 4, Layer 1
- [ ] Verify all methods present:
  - [ ] `__init__`
  - [ ] `get()`
  - [ ] `set()`
  - [ ] `_hash_text()`
  - [ ] `stats()`
- [ ] Check imports (hashlib, datetime, typing)

### [ ] 2. Integrate with Clustering
**File**: `/Users/sam/code/soulcaster/backend/clustering_runner.py`

- [ ] Add import: `from embedding_cache import get_embedding_cache`

- [ ] Update `_run_vector_clustering()`:
  ```python
  cache = get_embedding_cache()

  # Check cache for each text
  embeddings_list = []
  uncached_indices = []

  for i, text in enumerate(texts):
      cached = cache.get(text)
      if cached:
          embeddings_list.append(cached)
          logger.debug(f"Cache hit: {i}")
      else:
          embeddings_list.append(None)
          uncached_indices.append(i)

  # Generate only uncached embeddings
  if uncached_indices:
      uncached_texts = [texts[i] for i in uncached_indices]
      new_embeddings = clustering.embed_texts_gemini(uncached_texts)
      for j, idx in enumerate(uncached_indices):
          embedding = new_embeddings[j].tolist()
          embeddings_list[idx] = embedding
          cache.set(texts[idx], embedding)
  ```

### [ ] 3. Add Cache Metrics
**File**: `/Users/sam/code/soulcaster/backend/main.py`

- [ ] Update `/health/vector-metrics` endpoint:
  ```python
  @app.get("/health/vector-metrics")
  async def vector_metrics():
      from embedding_cache import get_embedding_cache
      return {
          "vector_store": get_vector_store_metrics(),
          "embedding_cache": get_embedding_cache().stats(),
          "timestamp": datetime.now(timezone.utc).isoformat(),
      }
  ```

### [ ] 4. Test Cache
**File**: Create `/Users/sam/code/soulcaster/backend/tests/test_embedding_cache.py`

```python
from embedding_cache import EmbeddingCache

def test_cache_set_get():
    cache = EmbeddingCache(max_size=10)

    text = "Test embedding"
    embedding = [0.1, 0.2, 0.3]

    cache.set(text, embedding)
    assert cache.get(text) == embedding

def test_cache_expiry():
    from datetime import timedelta
    cache = EmbeddingCache(ttl_hours=0.001)  # Very short TTL for testing

    text = "Test"
    cache.set(text, [0.1])

    assert cache.get(text) is not None
    # Wait for TTL...
    # assert cache.get(text) is None  # (implement if needed)
```

- [ ] Run: `cd backend && uv run pytest tests/test_embedding_cache.py -v`

### [ ] 5. Benchmark Cache
**File**: Update `/Users/sam/code/soulcaster/backend/benchmark_vector.py`

```python
def benchmark_embedding_cache():
    from embedding_cache import get_embedding_cache
    from clustering import embed_texts_gemini

    cache = get_embedding_cache()

    # Test: 100 texts, 30% are duplicates
    texts = ["Error type A"] * 30 + ["Error type B"] * 20 + [f"Unique {i}" for i in range(50)]

    # Without cache
    start = time.time()
    embed_texts_gemini(texts)
    without_cache_time = time.time() - start

    # With cache (second run)
    cache.cache.clear()  # Clear for fair test
    start = time.time()
    for text in texts:
        cached = cache.get(text)
        if not cached:
            embedding = embed_texts_gemini([text])[0]
            cache.set(text, embedding.tolist())
    with_cache_time = time.time() - start

    print(f"Without cache: {without_cache_time:.2f}s")
    print(f"With cache:    {with_cache_time:.2f}s")
    print(f"Speedup:       {without_cache_time/with_cache_time:.1f}x")
```

---

## Validation & Testing (All Phases)

### [ ] 1. Unit Tests
```bash
cd /Users/sam/code/soulcaster/backend
uv run pytest tests/test_vector_batch.py tests/test_embedding_cache.py -v
```

- [ ] All new tests pass ✅

### [ ] 2. Integration Tests
```bash
uv run pytest tests/test_clustering_runner.py -v
```

- [ ] All clustering tests pass ✅
- [ ] No regressions in existing behavior ✅

### [ ] 3. E2E Test (Manual)
```bash
# Terminal 1
just dev-backend

# Terminal 2
curl -X POST http://localhost:8000/ingest/manual \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "test-project",
    "title": "Connection error",
    "body": "Failed to connect to server",
    "source": "manual"
  }'

# Repeat 50 times (simulate batch ingestion)

# Check metrics
curl http://localhost:8000/health/vector-metrics | jq .
```

- [ ] Clustering completes successfully ✅
- [ ] Metrics show batched queries ✅
- [ ] Cache hit rate visible in metrics ✅

### [ ] 4. Performance Validation

Compare before/after:

```bash
# Before optimization
time just test-backend

# After optimization
time just test-backend
```

Document results:
- [ ] Test suite runtime: ____ → ____ seconds
- [ ] Vector query latency: ____ → ____ ms
- [ ] Clustering job duration: ____ → ____ seconds
- [ ] Gemini API calls: ____ → ____ (cache effect)

---

## Code Review Checklist

### [ ] Code Quality
- [ ] No breaking changes to existing APIs
- [ ] Proper error handling (try/except where needed)
- [ ] Type hints on all new functions
- [ ] Docstrings on all new methods
- [ ] No unused imports
- [ ] Consistent with existing code style

### [ ] Documentation
- [ ] Updated CLAUDE.md if architecture changed
- [ ] Added inline comments for complex logic
- [ ] Docstrings match implementation
- [ ] Examples in docstrings work

### [ ] Testing
- [ ] Unit tests for new methods
- [ ] Edge cases covered (empty lists, timeouts, etc.)
- [ ] Integration tests pass
- [ ] No test regressions
- [ ] Performance benchmarks documented

---

## Git Commit Strategy

### Phase 1 Commits
```bash
git add backend/vector_store.py
git commit -m "feat: Add batch query support to VectorStore

- Implement find_similar_batch() method using query_many()
- Falls back to sequential queries for SDK < 0.6.0
- Reduces N queries to 1 request (50-80% latency reduction)"

git add backend/clustering_runner.py
git commit -m "refactor: Use batch queries in clustering pipeline

- Replace sequential find_similar() loop with find_similar_batch()
- Significantly improves clustering throughput
- All tests passing"

git add backend/tests/test_vector_batch.py
git commit -m "test: Add batch query validation tests"

git add backend/benchmark_vector.py
git commit -m "perf: Add vector query benchmark script"
```

### Phase 2 Commits
```bash
git add backend/vector_store.py
git commit -m "feat: Add latency instrumentation to VectorStore

- Add @_timed_operation decorator for all query methods
- Collect metrics in module-level _metrics dict
- Expose via get_vector_store_metrics()"

git add backend/main.py
git commit -m "feat: Add /health/vector-metrics endpoint"

git add UPSTASH_VECTOR_OPTIMIZATION_GUIDE.md
git commit -m "docs: Add Upstash Vector optimization guide"
```

### Phase 3 Commits
```bash
git add backend/embedding_cache.py
git commit -m "feat: Add in-memory embedding cache

- LRU cache for Gemini embeddings (10K max, 24h TTL)
- Reduces API calls by 20-30% for duplicate titles
- Simple TTL-based eviction"

git add backend/clustering_runner.py
git commit -m "feat: Integrate embedding cache in clustering

- Check cache before generating embeddings
- Only call Gemini API for cache misses
- 20-30% reduction in embedding API calls"

git add backend/tests/test_embedding_cache.py
git commit -m "test: Add embedding cache unit tests"
```

---

## Rollback Plan

If issues occur:

### [ ] Quick Rollback (5 min)
```bash
git revert <commit-hash>  # Revert latest change
git push origin main
```

### [ ] Known Issues & Fixes

| Issue | Symptom | Fix |
|-------|---------|-----|
| QueryMany not supported | `AttributeError: 'Index' object has no attribute 'query_many'` | Update upstash-vector >= 0.6.0 |
| Batch size too large | `RequestException: Payload too large` | Reduce batch size to 25-30 |
| Cache memory leak | Memory usage grows unbounded | Reduce cache max_size or TTL |
| Missing metric keys | KeyError in get_vector_store_metrics() | Ensure _metrics dict initialized |

---

## Success Criteria

### Phase 1 Success
- [ ] Query batching implemented ✅
- [ ] find_similar_batch() passes tests ✅
- [ ] Latency reduced by 40%+ ✅
- [ ] No clustering test regressions ✅

### Phase 2 Success
- [ ] Metrics collecting properly ✅
- [ ] Health endpoint responds ✅
- [ ] Latency measurements accurate ✅

### Phase 3 Success
- [ ] Embedding cache working ✅
- [ ] Cache hit rate > 30% ✅
- [ ] Gemini API calls reduced ✅

### Overall Success
- [ ] 40-60% clustering latency improvement ✅
- [ ] 20-30% Gemini API call reduction ✅
- [ ] Production monitoring in place ✅
- [ ] Documentation updated ✅

---

## Notes & Decisions

### Decisions Made
- **Query Batching**: Priority 1 (high ROI, easy implementation)
- **Embedding Cache**: Priority 2 (good ROI, medium complexity)
- **Query Result Cache**: Deferred (complex, low ROI for this workload)
- **Eventual Consistency Wait**: Not added (code already handles it)

### Open Questions
- [ ] What's the max batch size for query_many()? (Test: start with 50, reduce if needed)
- [ ] Are there Upstash quota limits that affect batching? (Monitor in Phase 2)
- [ ] Should cache be shared across projects? (Recommend: yes, embeddings are universal)

### Follow-up Work
- [ ] Add distributed cache (Redis) for multi-process deployments
- [ ] Implement cache warming (pre-load common error titles)
- [ ] Add cache invalidation on Gemini model updates
- [ ] Benchmark with real production data (50K+ feedback items)
