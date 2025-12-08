# Testing & Validation Plan

This document outlines a comprehensive testing strategy for the Soulcaster platform to ensure reliability, accuracy, and production readiness.

## Overview

**Goal:** Establish automated testing, validation scripts, and quality gates for all core features.

**Estimated Time:** 4-6 days  
**Priority:** 🔥 HIGH (Required before customer deployments)

---

### Current focus (Phase 1 ingestion)
- [x] backend/tests/test_ingestion.py: add unclustered write test (feedback lands in all 4 keys incl. feedback:unclustered)
- [x] backend/tests/test_store.py: add helpers coverage for get_unclustered_feedback/remove_from_unclustered
- [ ] backend/tests/test_ingestion.py: ensure all ingest endpoints emit normalized FeedbackItem shape

---

## Phase 1: Unit Test Coverage (Days 1-2)

### 1.1 Backend Tests

#### Store Layer
- [ ] **File:** `backend/tests/test_store.py`
- [ ] Test `add_feedback_item()` writes to all 4 Redis keys
- [ ] Test `get_feedback_item()` retrieves correct data
- [ ] Test `get_unclustered_feedback()` returns only unclustered items
- [ ] Test `remove_from_unclustered()` removes items
- [ ] Test deduplication logic
- [ ] Test Redis connection failures
- [ ] **Target:** >90% coverage on `backend/store.py`

#### Ingestion Endpoints
- [ ] **File:** `backend/tests/test_ingestion.py`
- [ ] Test Reddit ingestion with various payloads
- [ ] Test Sentry webhook handling
- [ ] Test manual feedback submission
- [ ] Test GitHub issue ingestion
- [ ] Test malformed payloads (400 errors)
- [ ] Test authentication (if implemented)
- [ ] **Target:** >85% coverage on ingestion routes

#### Clustering Logic
- [ ] **File:** `backend/tests/test_clustering.py`
- [ ] Test embedding generation
- [ ] Test similarity calculation
- [ ] Test cluster creation with various thresholds
- [ ] Test cluster merging logic
- [ ] Test noise detection (unclustered items)
- [ ] Test empty input handling
- [ ] **Target:** >80% coverage on clustering code

### 1.2 Dashboard Tests

#### API Routes
- [ ] **File:** `dashboard/__tests__/api/clusters.test.ts`
- [ ] Test `GET /api/clusters` returns clusters
- [ ] Test `POST /api/clusters/run` triggers clustering
- [ ] Test `GET /api/clusters/[id]` returns single cluster
- [ ] Test `POST /api/clusters/[id]/start_fix` triggers agent

#### Library Functions
- [ ] **File:** `dashboard/__tests__/lib/redis.test.ts`
- [ ] Test Redis connection handling
- [ ] Test data serialization/deserialization
- [ ] Test error handling

- [ ] **File:** `dashboard/__tests__/lib/vector.test.ts`
- [ ] Test embedding generation
- [ ] Test similarity search
- [ ] Test vector upsert/query

- [ ] **File:** `dashboard/__tests__/lib/clustering.test.ts`
- [ ] Test cluster algorithm
- [ ] Test noise handling

#### Component Tests
- [ ] **File:** `dashboard/__tests__/components/FeedbackCard.test.tsx`
- [ ] Test rendering with various props
- [ ] Test click handlers
- [ ] Test edge cases (empty data, long text)

### 1.3 Coverage Goals
- [ ] Run coverage report:
  ```bash
  # Backend
  pytest backend/tests --cov=backend --cov-report=html --cov-report=term
  
  # Dashboard
  npm run test --prefix dashboard -- --coverage
  ```
- [ ] **Backend Target:** >80% overall, >90% on critical paths
- [ ] **Dashboard Target:** >75% overall, >85% on lib/ functions

---

## Phase 2: Integration Tests (Day 3)

### 2.1 End-to-End Flows

#### Full Feedback Flow
- [ ] **File:** `backend/tests/test_e2e_feedback.py`
```python
async def test_full_feedback_flow():
    """Test: Ingest -> Store -> Cluster -> Agent -> PR"""
    # 1. Ingest feedback via API
    response = client.post("/feedback", json={...})
    feedback_id = response.json()["id"]
    
    # 2. Verify in Redis
    assert redis.exists(f"feedback:{feedback_id}")
    assert redis.sismember("feedback:unclustered", feedback_id)
    
    # 3. Run clustering
    response = client.post("/api/clusters/run")
    cluster_id = response.json()["clusters"][0]["id"]
    
    # 4. Verify cluster created
    assert redis.exists(f"cluster:{cluster_id}")
    
    # 5. Trigger coding agent
    response = client.post(f"/api/clusters/{cluster_id}/start_fix")
    job_id = response.json()["job_id"]
    
    # 6. Wait for completion (mock or real)
    # 7. Verify PR created
```

#### Multi-Source Ingestion
- [ ] **File:** `backend/tests/test_e2e_multi_source.py`
```python
def test_multiple_sources_cluster_together():
    """Test: Reddit + GitHub + Manual all cluster correctly"""
    # Ingest similar issues from different sources
    # Run clustering
    # Verify they end up in same cluster
```

### 2.2 Dashboard Integration Tests

#### Full UI Flow
- [ ] **File:** `dashboard/__tests__/integration/full_flow.test.ts`
```typescript
describe('Full user flow', () => {
  it('should ingest, cluster, and trigger agent', async () => {
    // 1. Submit manual feedback via UI
    // 2. Wait for it to appear in unclustered
    // 3. Click "Run Clustering"
    // 4. Verify cluster appears
    // 5. Click "Fix This"
    // 6. Verify job status updates
  });
});
```

---

## Phase 3: Load & Performance Tests (Day 4)

### 3.1 Ingestion Load Testing

#### High Volume Ingestion
- [ ] **File:** `backend/tests/test_load_ingestion.py`
```python
def test_ingest_1000_items_under_60_seconds():
    """Ensure ingestion scales"""
    start = time.time()
    for i in range(1000):
        client.post("/feedback", json={...})
    duration = time.time() - start
    assert duration < 60
```

#### Concurrent Requests
- [ ] Test with 10 concurrent clients
- [ ] Test with 50 concurrent clients
- [ ] Measure: throughput, latency, error rate

### 3.2 Clustering Performance

#### Large Dataset Clustering
- [ ] **File:** `backend/tests/test_load_clustering.py`
```python
def test_cluster_1000_items_under_5_minutes():
    """Ensure clustering scales"""
    # Create 1000 feedback items
    # Run clustering
    # Measure time and memory
```

#### Embedding Generation
- [ ] Test embedding generation for 100 items
- [ ] Measure API rate limits
- [ ] Test caching effectiveness

### 3.3 Redis Performance

#### Connection Pool
- [ ] Test connection pool under load
- [ ] Test Redis failover (if HA setup)
- [ ] Measure read/write latency

---

## Phase 4: Validation Scripts (Day 5)

### 4.1 Data Validation

#### Feedback Item Validation
- [ ] **File:** `scripts/validate_feedback_data.py`
```python
def validate_all_feedback_items():
    """Ensure all feedback items have correct shape"""
    # Scan all feedback:* keys
    # Validate required fields
    # Check for orphaned keys
    # Report anomalies
```

#### Cluster Validation
- [ ] **File:** `scripts/validate_clusters.py`
```python
def validate_all_clusters():
    """Ensure cluster integrity"""
    # Check all cluster:* keys
    # Verify all members exist
    # Check embeddings are valid
    # Verify no feedback is in multiple clusters
```

### 4.2 System Health Checks

#### Health Check Script
- [ ] **File:** `scripts/health_check.sh`
```bash
#!/bin/bash
# Check all services are healthy

echo "Checking backend..."
curl -f http://localhost:8000/health || exit 1

echo "Checking dashboard..."
curl -f http://localhost:3000/api/health || exit 1

echo "Checking Redis..."
redis-cli ping || exit 1

echo "✅ All systems healthy"
```

#### Database Integrity
- [ ] **File:** `scripts/check_redis_integrity.py`
```python
def check_redis_integrity():
    """Verify Redis data consistency"""
    # Check for orphaned feedback items
    # Check for broken references
    # Check for expired keys that should be cleaned
    # Report issues
```

---

## Phase 5: Quality Gates & CI (Day 6)

### 5.1 Pre-Commit Hooks

#### Setup Pre-Commit
- [ ] Install pre-commit: `pip install pre-commit`
- [ ] Create `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: v3.0.0
    hooks:
      - id: prettier
        types_or: [javascript, typescript, tsx, json, yaml]
```
- [ ] Run `pre-commit install`

### 5.2 GitHub Actions CI

#### Backend CI
- [ ] **File:** `.github/workflows/backend-ci.yml`
```yaml
name: Backend CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r backend/requirements.txt
      - name: Run tests
        run: pytest backend/tests --cov=backend --cov-fail-under=80
      - name: Run linters
        run: |
          black --check backend
          flake8 backend
```

#### Dashboard CI
- [ ] **File:** `.github/workflows/dashboard-ci.yml`
```yaml
name: Dashboard CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Node
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      - name: Install dependencies
        run: npm ci --prefix dashboard
      - name: Run tests
        run: npm run test --prefix dashboard -- --coverage
      - name: Run linters
        run: npm run lint --prefix dashboard
```

### 5.3 Quality Gates

#### PR Requirements
- [ ] All tests must pass
- [ ] Coverage must not decrease
- [ ] Linters must pass
- [ ] At least 1 approval required
- [ ] No merge conflicts

#### Branch Protection
- [ ] Enable on `main` branch
- [ ] Require status checks
- [ ] Require up-to-date branches
- [ ] Require linear history

---

## Phase 6: Acceptance Testing (Day 6-7)

### 6.1 Manual Test Scenarios

#### Scenario 1: First-Time User
- [ ] Sign up / OAuth
- [ ] Add first feedback source
- [ ] See feedback appear
- [ ] Run clustering
- [ ] View clusters
- [ ] Trigger fix
- [ ] See PR created

#### Scenario 2: Power User
- [ ] Configure multiple sources (Reddit, GitHub, manual)
- [ ] Ingest 100+ items
- [ ] Run clustering with custom thresholds
- [ ] Merge/split clusters manually
- [ ] Trigger multiple fixes in parallel
- [ ] Track job status

#### Scenario 3: Error Handling
- [ ] Submit invalid feedback (expect validation error)
- [ ] Configure invalid Reddit credentials (expect helpful error)
- [ ] Trigger fix without GitHub token (expect error message)
- [ ] Simulate Redis downtime (expect graceful degradation)

### 6.2 Acceptance Criteria

Before marking system as "production ready":

- ✅ **All unit tests pass** (>80% coverage)
- ✅ **All integration tests pass**
- ✅ **Load tests pass** (1000 items < 60s ingest, < 5m cluster)
- ✅ **CI pipeline green**
- ✅ **Manual test scenarios complete**
- ✅ **No critical bugs open**
- ✅ **Documentation complete** (README, API docs, setup guide)
- ✅ **Health check endpoints working**
- ✅ **Monitoring/logging in place**

---

## Running All Tests

### Quick Test Run
```bash
# Backend only
cd backend && pytest tests -v

# Dashboard only
cd dashboard && npm run test

# All tests
./scripts/run_all_tests.sh
```

### Full Test Suite with Coverage
```bash
# Create test report script
cat > scripts/run_all_tests.sh << 'EOF'
#!/bin/bash
set -e

echo "🧪 Running Soulcaster Test Suite..."
echo ""

echo "📦 Backend Tests..."
cd backend
pytest tests -v --cov=backend --cov-report=html --cov-report=term
cd ..

echo ""
echo "🎨 Dashboard Tests..."
cd dashboard
npm run test -- --coverage
cd ..

echo ""
echo "✅ All tests complete!"
echo "📊 Coverage reports:"
echo "   Backend:   backend/htmlcov/index.html"
echo "   Dashboard: dashboard/coverage/index.html"
EOF

chmod +x scripts/run_all_tests.sh
./scripts/run_all_tests.sh
```

---

## Monitoring & Alerting

### Key Metrics to Track

1. **Ingestion**
   - Items/minute ingested
   - Ingestion errors
   - Source health (Reddit API, GitHub API)

2. **Clustering**
   - Clustering runtime
   - Number of clusters created
   - Unclustered item count
   - Embedding API errors

3. **Coding Agent**
   - Jobs triggered
   - Jobs succeeded/failed
   - Time to first PR
   - PR merge rate

### Logging
- [ ] Add structured logging (JSON format)
- [ ] Log all API requests
- [ ] Log clustering runs
- [ ] Log agent triggers
- [ ] Add correlation IDs for tracing

---

## Next Steps After Testing Complete

1. **Performance Optimization**
   - Profile slow paths
   - Add caching where needed
   - Optimize Redis queries

2. **Security Audit**
   - Review authentication/authorization
   - Check for injection vulnerabilities
   - Validate input sanitization

3. **Customer Beta**
   - Deploy to staging
   - Onboard 2-3 beta customers
   - Gather feedback
   - Iterate
