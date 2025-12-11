# Implementation Roadmap - Ingestion Moat First

This roadmap prioritizes stabilizing your **ingestion moat** before investing in new coding-agent capabilities.

## Worktree Mapping

- 🔧 **system-readiness** → Phases 1-4 (ingestion, clustering worker)
- 💰 **billing-integration** → Phase 6 (multi-tenant with project_id)
- 🎓 **onboarding-flow** → Customer-facing work (parallel track)

---

## Phase 1: Stabilize Ingestion + feedback:unclustered Semantics
**Worktree:** `worktrees/system-readiness`  
**Reference:** `documentation/ingestion_polling_architecture_plan.md` Phase 1
**Note:** Detailed day-by-day tasks from `tasks/PHASE1_CHECKLIST.md` have been consolidated here.

### Backend Tasks
- [x] **File: `backend/store.py`**
  - [x] Ensure `add_feedback_item()` writes to:
    - `feedback:{uuid}` (hash)
    - `feedback:created` (sorted set, score=timestamp)
    - `feedback:source:{source}` (set)
    - `feedback:unclustered` (set)
  - [x] Add helper: `get_unclustered_feedback()` → returns all items in `feedback:unclustered`
  - [x] Add helper: `remove_from_unclustered(feedback_id)` → removes from set when clustered

- [x] **File: `backend/models.py`**
  - [x] Verify `FeedbackItem` has all required fields: `id`, `source`, `created_at`, `raw_text`, `embedding`
  - [x] Add validation to ensure consistent shape across all sources

- [ ] **File: `backend/main.py`**
  - [ ] Review all ingest endpoints:
    - `/ingest/reddit` ✓
    - `/ingest/sentry` ✓
    - `/ingest/manual` (via `/feedback` POST)
    - `/ingest/github/sync/{name}` ✓ (moved ingestion to backend; frontend now proxies)
  - [ ] Ensure each normalizes to `FeedbackItem` before calling `store.add_feedback_item()`
  - [ ] Add consistent logging: `logger.info(f"Ingested {source} feedback: {feedback_id}")`

### Testing
- [ ] **File: `backend/tests/test_ingestion.py`**
  - [x] Test `add_feedback_item()` writes to all 4 Redis keys
  - [x] Test `feedback:unclustered` contains new items
  - [ ] Test each ingest endpoint produces consistent `FeedbackItem` shape
  - [x] Test duplicate detection (if implemented)

### Acceptance Criteria
- ✅ Every feedback item lands in `feedback:unclustered`
- ✅ All ingest sources produce identical data shape
- ✅ Tests cover happy path + edge cases
- ✅ Redis key patterns documented in `documentation/db_design.md`
- ✅ Ingest endpoints emit logging for `feedback_id` and `source`
- 🎯 Tests target >80% coverage on store/ingestion paths
- ℹ️ Current deployment supports GitHub ingestion only; Reddit/Sentry are deferred to Phase 2.

---

## Phase 2: Standardize Reddit Poller
**Worktree:** `worktrees/system-readiness`  
**Reference:** `documentation/ingestion_polling_architecture_plan.md` Phase 2

### Backend Tasks
- [ ] **File: `backend/reddit_poller.py`**
  - [ ] Remove any direct `store.add_feedback_item()` calls
  - [ ] Always POST to `BACKEND_URL/ingest/reddit`
  - [ ] Change config priority:
    1. Fetch from `config:reddit:subreddits` (Redis)
    2. Fallback to `REDDIT_SUBREDDITS` env var
  - [ ] Add logging: `logger.info(f"Polling {len(subreddits)} subreddits: {subreddits}")`

- [ ] **File: `backend/main.py`**
  - [ ] Add endpoints:
    - `GET /config/reddit/subreddits` → read `config:reddit:subreddits`
    - `PUT /config/reddit/subreddits` → write to Redis list
  - [ ] These already exist in `dashboard/app/api/config/reddit/subreddits/route.ts`, ensure backend has them too

### Dashboard Tasks
- [ ] **File: `dashboard/components/SourceConfig.tsx`**
  - [ ] Verify Reddit config UI reads/writes via `/api/config/reddit/subreddits`
  - [ ] Show current active subreddits
  - [ ] Allow add/remove subreddits

### Testing
- [ ] **File: `backend/tests/test_reddit_poller.py`**
  - [ ] Test poller reads from Redis first
  - [ ] Test fallback to env var
  - [ ] Test poller calls `/ingest/reddit` (not direct store)
  - [ ] Mock HTTP calls to avoid hitting real Reddit API

- [ ] **File: `backend/tests/test_reddit_config_api.py`**
  - [ ] Test GET/PUT `/config/reddit/subreddits`

### Acceptance Criteria
- ✅ Reddit poller is "just another producer" (no special store access)
- ✅ Config stored in Redis, editable via dashboard
- ✅ Poller can be restarted without code changes

---

## Phase 3: Clarify API Read/Write Boundaries
**Worktree:** `worktrees/system-readiness`  
**Reference:** `documentation/api_workers_architecture_plan.md` Phase 1

### Backend API (Read/Write)
- [x] **File: `backend/main.py`**
  - [x] Ensure these endpoints exist and work:
    - `GET /feedback` → list all feedback
    - `GET /feedback/{id}` → single item
    - `POST /feedback` → manual ingestion
    - `PUT /feedback/{id}` → update feedback
    - `GET /clusters` → list clusters
    - `GET /clusters/{id}` → single cluster
    - `POST /clusters/{id}/start_fix` → trigger agent (backend owns this)
    - `GET /jobs` → list agent jobs
    - `GET /jobs/{id}` → single job
    - `PATCH /jobs/{id}` → update job status (from agent)

- [ ] **File: `backend/store.py`**
  - [ ] Add docstrings clarifying read vs. write operations
  - [ ] Ensure atomic operations where needed (Redis transactions)
  - [ ] Add `get_cluster_status(cluster_id)` if missing
  - [ ] Add `update_cluster_pr_url(cluster_id, pr_url)` if missing

### Dashboard API (Proxy Only)
- [x] **Files: `dashboard/app/api/**/route.ts`**
  - [x] Review all route handlers
  - [x] Identify which ones write directly to Redis (anti-pattern)
  - [x] Migrate: proxy feedback/clusters/stats/Reddit config to backend endpoints

### Acceptance Criteria
- ✅ Backend owns all writes to Redis
- ✅ Dashboard proxies to backend for writes (doesn't write directly)
- ✅ Clear boundary documented in `documentation/api_workers_architecture_plan.md`

---

## Phase 4: Build Clustering Worker
**Worktree:** `worktrees/system-readiness`  
**Reference:** `documentation/clustering_worker_architecture_plan.md`
**Current state:** Clustering runs in dashboard today (`dashboard/lib/clustering.ts`, `dashboard/lib/vector.ts`, `/api/clusters/run`). This phase migrates that logic into a backend worker.

### Step 1: Extract Pure Clustering Module
- [ ] **File: `backend/clustering.py`** (NEW)
  - [ ] Move clustering logic from `dashboard/lib/clustering.ts` to Python
  - [ ] Functions:
    - `compute_embeddings(texts: List[str]) -> List[List[float]]`
    - `cluster_feedback(feedback_items: List[FeedbackItem]) -> List[Cluster]`
    - `summarize_cluster(feedback_items: List[FeedbackItem]) -> str`
  - [ ] Use Gemini API (same as dashboard currently uses)
  - [ ] Make it pure/testable (no Redis access in core logic)

- [ ] **File: `backend/tests/test_clustering.py`** (NEW)
  - [ ] Test embedding generation
  - [ ] Test clustering algorithm (cosine similarity)
  - [ ] Test summarization
  - [ ] Use fixtures/mocks for LLM calls

### Step 2: Create Clustering Worker
- [ ] **File: `backend/clustering_worker.py`** (NEW)
  ```python
  # Standalone script that:
  # 1. Fetches feedback:unclustered from Redis
  # 2. Runs clustering.cluster_feedback()
  # 3. Writes cluster:* keys to Redis
  # 4. Removes clustered items from feedback:unclustered
  # 5. Updates cluster-job status
  ```
  - [ ] Add CLI: `python -m backend.clustering_worker --job-id <uuid>`
  - [ ] Add logging to CloudWatch
  - [ ] Handle errors gracefully (mark job as failed)

### Step 3: Backend Cluster Job API
- [ ] **File: `backend/main.py`**
  - [ ] Add endpoints:
    - `POST /cluster-jobs` → create new cluster job, trigger worker
    - `GET /cluster-jobs/{id}` → get job status
    - `PATCH /cluster-jobs/{id}` → update job (from worker)

- [ ] **File: `backend/models.py`**
  - [ ] Add `ClusterJob` model:
    ```python
    class ClusterJob(BaseModel):
        id: str
        status: Literal["pending", "running", "completed", "failed"]
        created_at: datetime
        started_at: Optional[datetime]
        completed_at: Optional[datetime]
        error: Optional[str]
        clusters_created: int
    ```

### Step 4: Worker Container
- [ ] **File: `backend/Dockerfile.clustering-worker`** (NEW)
  - [ ] Based on `backend/Dockerfile` or create new
  - [ ] CMD: `python -m backend.clustering_worker`

- [ ] **File: `backend/terraform/clustering-ecs.tf`** (NEW)
  - [ ] ECS task definition for clustering worker
  - [ ] Reuse networking from coding-agent setup
  - [ ] Environment variables: `REDIS_URL`, `GEMINI_API_KEY`, etc.

### Step 5: Trigger Worker from Dashboard
- [ ] **File: `dashboard/app/api/clusters/run/route.ts`**
  - [ ] Change from running clustering inline to:
    ```typescript
    // POST to backend /cluster-jobs
    // Return job_id to frontend
    // Frontend polls /cluster-jobs/{id} for status
    ```

- [ ] **File: `dashboard/lib/clustering.ts`**
  - [ ] Mark current code as `// DEPRECATED: Moving to backend worker`
  - [ ] Keep for backward compatibility initially
  - [ ] Add env flag: `USE_BACKEND_CLUSTERING_WORKER`

### Step 6: Disable Auto-Clustering
- [ ] **File: `dashboard/lib/redis.ts`** (or wherever auto-clustering lives)
  - [ ] Find `_auto_cluster_feedback()` calls
  - [ ] Wrap in: `if (process.env.AUTO_CLUSTER_ENABLED === 'true')`
  - [ ] Default to `false` once worker is stable

### Testing
- [ ] **File: `backend/tests/test_clustering_worker.py`** (NEW)
  - [ ] Test worker reads unclustered feedback
  - [ ] Test worker creates clusters
  - [ ] Test worker updates job status
  - [ ] Test error handling

### Acceptance Criteria
- ✅ Clustering runs as async worker (not blocking dashboard)
- ✅ Dashboard triggers worker via backend API
- ✅ Worker can be scaled independently (ECS task count)
- ✅ Auto-clustering is disabled in favor of explicit jobs

---

## Phase 5: Unify "Generate Fix" Orchestration
**Worktree:** `worktrees/system-readiness`  
**Reference:** `documentation/api_workers_architecture_plan.md` + `documentation/coding_agent_sandbox_architecture.md` Plan 1

### Backend Owns RunTask
- [ ] **File: `backend/main.py`**
  - [ ] Enhance `POST /clusters/{id}/start_fix`:
    ```python
    # 1. Create AgentJob in Redis
    # 2. Call ECS RunTask with job_id, cluster_id
    # 3. Return job_id to caller
    ```
  - [ ] Move ECS client logic from dashboard to backend
  - [ ] Add AWS credentials to backend env: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`

- [ ] **File: `backend/aws_client.py`** (NEW)
  - [ ] Function: `run_coding_agent_task(cluster_id, job_id, github_issue_url)`
  - [ ] Uses `boto3` to call ECS RunTask
  - [ ] Passes environment overrides: `JOB_ID`, `GITHUB_ISSUE_URL`, etc.

### Dashboard Calls Backend
- [ ] **File: `dashboard/app/api/clusters/[id]/start_fix/route.ts`**
  - [ ] Simplify to just:
    ```typescript
    // Call backend POST /clusters/{id}/start_fix
    // Return job_id to frontend
    ```
  - [ ] Remove ECS client logic from dashboard
  - [ ] Remove `dashboard/app/api/trigger-agent/route.ts` (deprecated)

### Refactor Coding Agent
- [ ] **File: `coding-agent/fix_issue.py`**
  - [ ] Extract: `run_kilo_github_agent(issue_url, job_id, backend_url)`
  - [ ] Keep CLI wrapper thin:
    ```python
    if __name__ == "__main__":
        issue_url = sys.argv[1]
        job_id = os.getenv("JOB_ID")
        run_kilo_github_agent(issue_url, job_id, BACKEND_URL)
    ```
  - [ ] Don't change Kilo/GitHub behavior (keep as-is)

### Testing
- [ ] **File: `backend/tests/test_agent_orchestration.py`** (NEW)
  - [ ] Test `POST /clusters/{id}/start_fix` creates job
  - [ ] Test ECS RunTask is called (mock boto3)
  - [ ] Test job status is tracked

### Acceptance Criteria
- ✅ Backend owns agent orchestration (dashboard is just UI)
- ✅ Coding agent flow: dashboard → backend → ECS → agent → PR
- ✅ All job tracking centralized in backend

---

## Phase 6: Multi-Tenant / Project-Scoped Storage
**Worktree:** `worktrees/billing-integration`  
**Reference:** `documentation/db_design.md`

### Add project_id to Models
- [ ] **File: `backend/models.py`**
  - [ ] Add `project_id: str` to:
    - `FeedbackItem`
    - `IssueCluster`
    - `AgentJob`
  - [ ] Add `Project` model:
    ```python
    class Project(BaseModel):
        id: str
        name: str
        github_repo: str
        owner_user_id: str
        created_at: datetime
    ```

### Update Store Abstraction
- [ ] **File: `backend/store.py`**
  - [ ] Change key patterns:
    - `feedback:{uuid}` → `project:{project_id}:feedback:{uuid}`
    - `cluster:{uuid}` → `project:{project_id}:cluster:{uuid}`
    - `job:{uuid}` → `project:{project_id}:job:{uuid}`
  - [ ] Add backward-compat reads:
    ```python
    # Try project-scoped key first
    # Fall back to legacy global key
    ```
  - [ ] Add helpers:
    - `add_feedback_item(item, project_id)`
    - `get_clusters(project_id)`
    - `get_jobs(project_id)`

### Update Backend Routes
- [ ] **File: `backend/main.py`**
  - [ ] Add `project_id` parameter to routes:
    - `GET /projects/{project_id}/feedback`
    - `GET /projects/{project_id}/clusters`
    - `POST /projects/{project_id}/clusters/{id}/start_fix`
  - [ ] Keep legacy routes for back-compat (no project_id → use default)
  - [ ] Add project management routes:
    - `GET /projects` → list projects for user
    - `POST /projects` → create new project
    - `GET /projects/{id}` → get project details

### Dashboard Integration
- [ ] **File: `dashboard/lib/redis.ts`**
  - [ ] Add `project_id` to all Redis operations
  - [ ] Add project selector UI component

- [ ] **File: `dashboard/app/api/*/route.ts`**
  - [ ] Propagate `project_id` from session/context
  - [ ] Update all backend calls to use project-scoped routes

### Billing Link
- [ ] **File: `dashboard/lib/billing.ts`**
  - [ ] Link Stripe subscription to `project_id`
  - [ ] Check subscription status before allowing:
    - Feedback ingestion
    - Cluster creation
    - Agent runs
  - [ ] Add usage tracking per project

### Testing
- [ ] **File: `backend/tests/test_projects.py`** (NEW)
  - [ ] Test project CRUD
  - [ ] Test project-scoped data isolation
  - [ ] Test backward-compat with legacy keys

### Migration
- [ ] **File: `backend/scripts/migrate_to_projects.py`** (NEW)
  - [ ] Script to migrate legacy keys to project-scoped keys
  - [ ] Assign all existing data to a default project

### Acceptance Criteria
- ✅ All data is project-scoped
- ✅ Multiple projects per user supported
- ✅ Billing tied to projects
- ✅ Legacy data migrated
- ✅ Backward compatibility maintained during rollout

---

## Phase 7: New Coding-Agent Capabilities (Future)
**Worktree:** TBD (new worktree when ready)  
**Reference:** `documentation/coding_agent_sandbox_architecture.md` Plans 2–3

### Only After Phases 1-6 Are Stable
- [ ] Add LLM+tools agent (Plan 2):
  - [ ] New ECS task definition: `AGENT_TYPE=tools`
  - [ ] Runs Claude/GPT with tool calling
  - [ ] Shared GitHub operations with Kilo agent
  - [ ] Unified job model

- [ ] Gradually unify abstractions:
  - [ ] Extract common code from `fix_issue.py`
  - [ ] Create `coding-agent/lib/github_ops.py`
  - [ ] Create `coding-agent/lib/job_tracker.py`

### Not Prioritized Yet
- This phase is explicitly **deferred** until ingestion moat is rock-solid.

---

## Implementation Order Summary

```
┌─────────────────────────────────────────────┐
│ Phase 1-3: Ingestion Stability              │
│ Worktree: system-readiness                  │
│ Time: ~3-5 days                             │
│ Files: store.py, main.py, reddit_poller.py  │
└─────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│ Phase 4: Clustering Worker                  │
│ Worktree: system-readiness                  │
│ Time: ~5-7 days                             │
│ Files: clustering.py, clustering_worker.py  │
│ Infra: ECS task, Terraform                  │
└─────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│ Phase 5: Unify Agent Orchestration          │
│ Worktree: system-readiness                  │
│ Time: ~2-3 days                             │
│ Files: aws_client.py, fix_issue.py          │
└─────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│ Phase 6: Multi-Tenant Storage               │
│ Worktree: billing-integration               │
│ Time: ~5-7 days                             │
│ Files: models.py, store.py, billing.ts      │
└─────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│ Phase 7: New Agent Capabilities (Future)    │
│ Worktree: TBD                               │
│ Time: TBD                                   │
└─────────────────────────────────────────────┘
```

---

## Next Steps

1. **Start in `worktrees/system-readiness`**:
   ```bash
   cd worktrees/system-readiness
   git checkout -b phase1-ingestion-stability
   ```

2. **Begin Phase 1 Tasks**:
   - Open `backend/store.py`
   - Ensure `add_feedback_item()` writes to all 4 keys
   - Write tests first (TDD)

3. **Track Progress**:
   - Check off items in this file as you complete them
   - Create PRs for each phase
   - Merge to main only when phase is stable

4. **Parallel Work**:
   - Keep `worktrees/onboarding-flow` for customer-facing work
   - Keep `worktrees/billing-integration` for Phase 6 prep
   - Keep `main` branch clean for production deploys

---

## Success Metrics

After completing Phases 1-5:
- ✅ Ingestion is rock-solid (no data loss)
- ✅ Clustering scales independently
- ✅ Agent orchestration is clean
- ✅ Ready for multi-tenant (Phase 6)
- ✅ Can onboard design partners confidently

After Phase 6:
- ✅ Can charge per project
- ✅ Data isolation between customers
- ✅ Usage tracking per project
- ✅ Ready for $200+ MRR


