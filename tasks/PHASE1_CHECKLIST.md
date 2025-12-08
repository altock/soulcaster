# Phase 1: Stabilize Ingestion - Immediate Action Checklist

**Goal:** Guarantee every feedback item lands in `feedback:unclustered` with consistent shape.

**Worktree:** `system-readiness`  
**Estimated Time:** 3-5 days  
**Priority:** 🔥 CRITICAL (Your moat depends on this)

---

### Now / Next / Blocked
- **Now:** [x] backend: ensure add_feedback_item writes to feedback:unclustered + add get/remove helpers (done when unclustered test passes)
- **Next:** [ ] backend: normalize all ingest endpoints to FeedbackItem shape + consistent logging (done when endpoint tests green)
- **Blocked:** none noted (add owner/dependency if discovered)

---

## Day 1: Store Layer + Tests

### Morning (2-3 hours)
```bash
cd worktrees/system-readiness
git checkout -b phase1-ingestion-stability
```

- [ ] **Open: `backend/store.py`**
  - [ ] Find `add_feedback_item()` function
  - [ ] Verify it writes to these 4 Redis keys:
    ```python
    # 1. feedback:{uuid} → hash of full item
    # 2. feedback:created → sorted set (score=timestamp)
    # 3. feedback:source:{source} → set of IDs
    # 4. feedback:unclustered → set of IDs (NEW if missing)
    ```
  - [ ] Add missing key writes if needed
  - [ ] Add logging: `logger.info(f"Added feedback {item.id} to unclustered set")`

### Afternoon (3-4 hours)
- [ ] **Open: `backend/tests/test_ingestion.py`**
  - [ ] Add test:
    ```python
    def test_add_feedback_writes_to_unclustered():
        """Verify feedback lands in unclustered set"""
        item = create_test_feedback_item()
        store.add_feedback_item(item)
        
        # Check all 4 keys exist
        assert redis.exists(f"feedback:{item.id}")
        assert redis.zscore("feedback:created", item.id)
        assert redis.sismember(f"feedback:source:{item.source}", item.id)
        assert redis.sismember("feedback:unclustered", item.id)  # ← Key test
    ```
  - [ ] Run test: `pytest backend/tests/test_ingestion.py -v -k unclustered`
  - [ ] Make it pass (implement in store.py if needed)

- [ ] **Add helper functions to `backend/store.py`:**
  ```python
  def get_unclustered_feedback() -> List[FeedbackItem]:
      """Get all feedback items that haven't been clustered yet."""
      unclustered_ids = redis.smembers("feedback:unclustered")
      return [get_feedback_item(fid) for fid in unclustered_ids]
  
  def remove_from_unclustered(feedback_id: str):
      """Remove item from unclustered set (called after clustering)."""
      redis.srem("feedback:unclustered", feedback_id)
      logger.info(f"Removed {feedback_id} from unclustered set")
  ```

---

## Day 2: Normalize Ingest Endpoints

### Morning (3-4 hours)
- [ ] **Review all ingest endpoints in `backend/main.py`:**

  **Endpoint 1: `/ingest/reddit`**
  - [ ] Find the route handler
  - [ ] Verify it creates a `FeedbackItem` with:
    - `id` (UUID)
    - `source="reddit"`
    - `created_at` (timestamp)
    - `raw_text` (normalized from Reddit data)
    - `metadata` (original payload)
  - [ ] Verify it calls `store.add_feedback_item(item)`
  - [ ] Add logging: `logger.info(f"Ingested Reddit feedback: {item.id}")`

  **Endpoint 2: `/ingest/sentry`**
  - [ ] Same checks as Reddit
  - [ ] Ensure `source="sentry"`
  - [ ] Normalize Sentry exception data to `raw_text`

  **Endpoint 3: `/feedback` (manual POST)**
  - [ ] Same checks
  - [ ] Ensure `source="manual"`

  **Endpoint 4: `/ingest/github/sync/{name}`**
  - [ ] Same checks
  - [ ] Ensure `source="github"`
  - [ ] Normalize GitHub issue to `raw_text`

### Afternoon (2-3 hours)
- [ ] **Add tests for each endpoint:**
  ```python
  # backend/tests/test_ingestion.py
  
  def test_reddit_ingestion_creates_feedback():
      response = client.post("/ingest/reddit", json={...})
      assert response.status_code == 200
      # Verify feedback in Redis
  
  def test_sentry_ingestion_creates_feedback():
      # Similar
  
  def test_manual_ingestion_creates_feedback():
      # Similar
  
  def test_github_ingestion_creates_feedback():
      # Similar
  ```

- [ ] Run full test suite:
  ```bash
  cd backend
  pytest tests/test_ingestion.py -v
  ```

---

## Day 3: Data Shape Validation

### Morning (2-3 hours)
- [ ] **Open: `backend/models.py`**
  - [ ] Review `FeedbackItem` model:
    ```python
    class FeedbackItem(BaseModel):
        id: str
        source: Literal["reddit", "sentry", "manual", "github"]
        created_at: datetime
        raw_text: str  # Required! Normalized text
        metadata: dict  # Original payload
        embedding: Optional[List[float]] = None
        cluster_id: Optional[str] = None
    ```
  - [ ] Add validation:
    ```python
    @validator("raw_text")
    def raw_text_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("raw_text cannot be empty")
        return v
    ```

### Afternoon (3-4 hours)
- [ ] **Add integration test:**
  ```python
  # backend/tests/test_ingestion.py
  
  def test_all_sources_produce_consistent_shape():
      """Verify all ingest paths create identical FeedbackItem structure"""
      
      # Ingest from each source
      reddit_resp = client.post("/ingest/reddit", json={...})
      sentry_resp = client.post("/ingest/sentry", json={...})
      manual_resp = client.post("/feedback", json={...})
      github_resp = client.post("/ingest/github/sync/test-repo")
      
      # Fetch items back
      reddit_item = store.get_feedback_item(reddit_resp.json()["id"])
      sentry_item = store.get_feedback_item(sentry_resp.json()["id"])
      manual_item = store.get_feedback_item(manual_resp.json()["id"])
      github_item = store.get_feedback_item(github_resp.json()["id"])
      
      # All should have same fields
      for item in [reddit_item, sentry_item, manual_item, github_item]:
          assert item.id
          assert item.source in ["reddit", "sentry", "manual", "github"]
          assert item.created_at
          assert item.raw_text
          assert isinstance(item.metadata, dict)
  ```

- [ ] Run test and fix any issues

---

## Day 4-5: Documentation + PR

### Tasks
- [ ] **Update `documentation/db_design.md`:**
  - [ ] Document `feedback:unclustered` key pattern
  - [ ] Add example data flow diagram
  - [ ] Document helper functions

- [ ] **Add logging to all ingest paths:**
  ```python
  logger.info(f"Ingested {source} feedback: {feedback_id}", extra={
      "feedback_id": feedback_id,
      "source": source,
      "unclustered_count": redis.scard("feedback:unclustered")
  })
  ```

- [ ] **Run full backend test suite:**
  ```bash
  cd backend
  pytest tests -v --cov=backend --cov-report=term-missing
  ```
  - [ ] Aim for >80% coverage on store.py and ingestion

- [ ] **Manual smoke test:**
  ```bash
  # Start backend
  cd backend
  uvicorn main:app --reload --port 8002
  
  # In another terminal, test each endpoint:
  curl -X POST http://localhost:8002/ingest/reddit -H "Content-Type: application/json" -d '{...}'
  curl -X POST http://localhost:8002/ingest/sentry -H "Content-Type: application/json" -d '{...}'
  curl -X POST http://localhost:8002/feedback -H "Content-Type: application/json" -d '{...}'
  
  # Check Redis:
  redis-cli
  > SMEMBERS feedback:unclustered
  > HGETALL feedback:{some-id}
  ```

- [ ] **Commit and PR:**
  ```bash
  cd worktrees/system-readiness
  git add backend/
  git commit -m "feat: stabilize ingestion with feedback:unclustered set
  
  - Add feedback:unclustered Redis key to track unprocessed items
  - Normalize all ingest endpoints to consistent FeedbackItem shape
  - Add helper functions: get_unclustered_feedback, remove_from_unclustered
  - Add comprehensive tests for all ingest paths
  - Update db_design.md with new key patterns
  
  Refs: tasks/IMPLEMENTATION_ROADMAP.md Phase 1"
  
  git push origin phase1-ingestion-stability
  # Create PR on GitHub
  ```

---

## Acceptance Criteria (Phase 1 Complete)

Before moving to Phase 2, verify:

- ✅ **All ingest endpoints write to `feedback:unclustered`**
  - Test: Ingest from each source, check Redis
  
- ✅ **All sources produce identical `FeedbackItem` shape**
  - Test: `test_all_sources_produce_consistent_shape` passes
  
- ✅ **Helper functions exist:**
  - `get_unclustered_feedback()`
  - `remove_from_unclustered(feedback_id)`
  
- ✅ **Tests cover happy path + edge cases**
  - Run: `pytest backend/tests/test_ingestion.py -v`
  - Coverage: >80% on relevant files
  
- ✅ **Documentation updated**
  - `documentation/db_design.md` reflects new patterns
  
- ✅ **Logging in place**
  - All ingest endpoints log feedback_id and source

---

## Common Issues & Solutions

### Issue: "Nothing in feedback:unclustered after ingestion"
**Solution:** Check if `add_feedback_item()` in store.py actually writes to the set. Add logging.

### Issue: "Tests fail with Redis connection error"
**Solution:** Ensure test fixture mocks Redis or uses fakeredis:
```python
# backend/tests/conftest.py
import fakeredis
@pytest.fixture
def redis_client():
    return fakeredis.FakeRedis()
```

### Issue: "Different sources have different field names"
**Solution:** Add normalization layer in each endpoint before creating `FeedbackItem`:
```python
# Normalize Reddit
raw_text = reddit_data.get("selftext") or reddit_data.get("title")

# Normalize Sentry
raw_text = f"{sentry_data['exception']['type']}: {sentry_data['exception']['value']}"

# Normalize GitHub
raw_text = f"{issue['title']}\n\n{issue['body']}"
```

---

## After Phase 1: Next Steps

Once Phase 1 is complete and merged to main:

1. **Move to Phase 2** (Reddit poller standardization)
   ```bash
   cd worktrees/system-readiness
   git checkout main
   git pull origin main
   git checkout -b phase2-reddit-poller
   ```

2. **Keep main branch stable**
   - Only merge tested, reviewed code
   - Main should always be deployable

3. **Parallel work**
   - Continue customer-facing work in `worktrees/onboarding-flow`
   - Billing prep work in `worktrees/billing-integration`

---

**Ready to start? Run:**
```bash
cd worktrees/system-readiness
git checkout -b phase1-ingestion-stability
code backend/store.py  # Open in editor and begin!
```


