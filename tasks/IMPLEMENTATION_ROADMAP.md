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
- 🚧 Phases 2+ are post-MVP; no automated Reddit/Sentry polling in MVP.

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

## Phase 4: Backend Async Clustering (In-Process, No Separate Service) ✅ COMPLETE
**Reference:** `documentation/clustering_worker_architecture_plan.md` (updated: in-process runner + future external worker)
**Status:** ✅ **COMPLETE** - Backend in-process async clustering is now live. Clustering runs asynchronously in the backend process with Redis locks. Dashboard is status-only (no inline clustering). All ingestion paths trigger clustering automatically.
**Goal:** Backend becomes the single clustering engine. Ingestion only writes feedback + marks it unclustered. Backend starts clustering asynchronously *in the same backend process* (no ECS/Fargate worker, no extra service), with a Redis lock + job status tracking.

### Step 1: Clustering Core Module (Backend) — Implement 3 Strategies, Default Best
- [x] **File: `backend/clustering.py`** (NEW)
  - [x] **Goal:** Implement all 3 clustering algorithms from the local experiment notebook behind a single strategy interface.
  - [x] **Reference (canonical):** `documentation/clustering_worker_architecture_plan.md` (see “Reference code snippets (Python)”)
  - [x] **Planned API surface:**
    - `prepare_issue_texts(issues, truncate_body_chars=1500) -> list[str]`
    - `embed_texts_gemini(texts, model="gemini-embedding-001", output_dimensionality=768) -> list[list[float]]`
    - `cluster_agglomerative(embeddings, sim_threshold=0.72, min_cluster_size=2) -> labels`
    - `cluster_centroid(embeddings, sim_threshold=0.72) -> labels`
    - `cluster_vector_like(embeddings, sim_threshold=0.72) -> labels`
    - `cluster_issues(issues, method, sim_threshold, min_cluster_size, truncate_body_chars) -> {labels, clusters, singletons, texts}`
  - [x] **Default in production (ship only the best):**
    - `CLUSTERING_METHOD=agglomerative`
    - `CLUSTERING_SIM_THRESHOLD=0.72`
    - `CLUSTERING_MIN_CLUSTER_SIZE=2`
    - `CLUSTERING_TRUNCATE_BODY_CHARS=1500`
  - [x] **Docstrings must include:**
    - Reference to the notebook path above
    - Time complexity notes for each method
  - [x] **Time complexity notes (must document):**
    - `agglomerative`: ~O(n^2) memory-ish, ~O(n^2)–O(n^3) time (n = items)
    - `centroid`: O(n·k·d) (k clusters; d=768)
    - `vector_like`: O(n^2·d) (baseline; compares each item to all prior items; not ANN/vector DB)
  - [x] Use Gemini API (same as dashboard currently uses)
  - [x] Make it pure/testable (no Redis access in core logic)

### Step 1.1: Dependencies (Backend)
- [x] **File: `backend/requirements.txt`**
  - [x] Add: `numpy`, `scikit-learn`, `packaging`, `google-genai`
  - [x] (Optional/deferred) Add `sentence-transformers` only if we want HF fallback in production

### Step 1.2: Tests (Clustering Strategies + Quality)
- [x] **File: `backend/tests/test_clustering_strategies.py`** (NEW)
  - [x] Ensure all 3 strategies run and return labels (smoke test)
- [x] **File: `backend/tests/test_clustering_quality.py`** (NEW)
  - [x] Use a small labeled fixture derived from the notebook CSV workflow to regress quality for the default method
  - [x] CI should not call Gemini: use saved embeddings fixture or mock embedding function

### Step 2: Backend In-Process Clustering Runner (Async Task)
- [x] **File: `backend/clustering_runner.py`** (NEW)
  - [x] Implement `maybe_start_clustering(project_id)`:
    - Acquire per-project Redis lock (prevents duplicate runs across workers/replicas)
    - Create `ClusterJob` record (status=pending/running)
    - Start background task inside FastAPI process (`asyncio.create_task(...)`)
    - Return `job_id` immediately
  - [x] Implement `run_clustering_job(project_id, job_id)`:
    - Read `feedback:unclustered:{project_id}`
    - Embed + assign clusters + summarize
    - Write `cluster:{project_id}:{id}`, `cluster:{project_id}:{id}:items`, `clusters:{project_id}:all`
    - Remove successfully processed IDs from `feedback:unclustered:{project_id}`
    - Update `ClusterJob` (stats + status succeeded/failed)
  - [x] Handle restarts safely:
    - Lock TTL + optional heartbeat timestamp
    - Treat stale "running" as failed/retryable

**Note:** The runner should call the clustering core via the strategy interface, but production defaults to the best-performing method (agglomerative @ 0.72). Other strategies remain switchable by env for later evaluation.

### Step 3: Backend Cluster Job API (Status + Optional Manual Trigger)
- [x] **File: `backend/main.py`**
  - [x] Add endpoints:
    - `POST /cluster-jobs` → create new cluster job and start in-process async task (optional; UI may not expose a button)
    - `GET /cluster-jobs/{id}` → get job status
    - `GET /cluster-jobs` → list recent jobs for a project (optional)
    - `GET /clustering/status` → convenience endpoint (pending count, is_clustering, last job) (optional)

- [x] **File: `backend/models.py`**
  - [x] Add `ClusterJob` model:
    ```python
    class ClusterJob(BaseModel):
        id: str
        project_id: Union[str, UUID]
        status: Literal["pending", "running", "succeeded", "failed"]
        created_at: datetime
        started_at: Optional[datetime]
        finished_at: Optional[datetime]
        error: Optional[str]
        stats: Dict[str, int]  # clustered, new_clusters, updated_clusters, embedding_failures, etc.
    ```

### Step 4: Remove Frontend-Driven Clustering (Status-Only UI)
- [x] **File: `dashboard/app/(pages)/clusters/*` (or relevant UI)**
  - [x] Remove "Run clustering" button (clustering is automatic on ingest)
  - [x] Keep status display (pending count / last job status)
- [x] **Files: `dashboard/app/api/clusters/run*/route.ts`**
  - [x] Deprecate/remove inline clustering routes in production (keep behind a dev-only flag if needed)
  - [x] If a manual trigger is still desired, call backend `POST /cluster-jobs` (no heavy work in Next.js)
- [x] **File: `dashboard/lib/clustering.ts`**
  - [x] Mark as deprecated for production use (backend is canonical)
  - [x] Keep temporarily for local debugging / tests if needed

### Step 5: Disable Heuristic Auto-Clustering in Backend Ingest
- [x] **File: `backend/main.py`**
  - [x] Remove `_auto_cluster_feedback()` calls from all ingest paths (GitHub sync, manual, reddit, sentry)
  - [x] Ingest should only mark feedback as unclustered; clustering happens via the in-process runner

### Testing
- [x] **File: `backend/tests/test_clustering_runner.py`** (NEW)
  - [x] Test runner reads unclustered feedback
  - [x] Test runner writes cluster keys + removes from unclustered
  - [x] Test lock prevents concurrent runs
  - [x] Test job status transitions + error handling

### Acceptance Criteria
- [x] Clustering runs asynchronously inside the backend process (non-blocking)
- [x] Ingestion never clusters; it only marks feedback unclustered
- [x] Redis lock prevents concurrent clustering per project
- [x] Dashboard is status-only (no inline clustering in Next.js in production)
- [x] Separate clustering service (ECS/Fargate worker) is deferred to a future phase if scaling requires it
- [x] All 3 strategies exist in the clustering core, but only the best is enabled by default (others are behind config for later testing)

---

## Phase 5 – AWS Coding Agent (Deferred)
- Dashboard `/api/trigger-agent` triggers ECS/Fargate to run `coding-agent/fix_issue.py`, then backend `/clusters/{id}/start_fix` just flips status.
- Runs depended on creating/validating a GitHub issue per fix request.
- Status: kept for manual/testing scenarios (set `CODING_AGENT_RUNNER=aws_kilo`), but not the default path once Phase 5.1 lands.

## Phase 5.1 – Cluster Coding Plan & Sandbox Runner (WIP)
- Objective: when a user opens a cluster they see a generated high-level plan (summary, hypotheses, candidate files, validation steps) and can trigger a fix directly via backend `/clusters/{id}/start_fix`.
- Runner strategy: backend selects a runner (`CODING_AGENT_RUNNER`, default `sandbox_kilo`) from a registry. Default runner spins up an e2b sandbox, installs Kilocode via a reusable template, runs the LLM agent entirely inside the sandbox, and opens a **branch + draft PR** (no GitHub issue). Legacy AWS runner stays opt-in for parity.
- Dashboard integration: `/app/api/clusters/[id]/start_fix` simply proxies to backend; legacy `/api/trigger-agent` remains for manual AWS triggers.
- Implementation reference: `tasks/coding_agent_plan.md` (combined plan + strategy with Kilocode/e2b doc links).
- Expected flow:
  1. Cluster opens → backend (or user) generates plan via `/clusters/{id}/plan`.
  2. User reviews/edits plan → clicks "Generate fix".
  3. Backend `/clusters/{id}/start_fix` creates job, selects runner, and dispatches to sandbox/provider.
  4. Runner streams logs, runs tests, and posts a draft PR; backend updates `/jobs` + cluster metadata.
- Status: WIP until planner, orchestrator, and sandbox runner are implemented; AWS runner remains behind `CODING_AGENT_RUNNER=aws_kilo`.

### Phase 5.1 Checkpoints
**Backend Planner & Orchestrator**
- [x] `backend/planner.py`: generate/save `CodingPlan`, expose `GET/POST /clusters/{id}/plan`.
- [x] Update `AgentJob` schema (`plan_id`, `runner`, `artifact_url`, logs).
- [x] Enhance `POST /clusters/{id}/start_fix`: ensure plan, create job, select runner, dispatch async worker, stream logs.
- [x] Runner registry + interfaces (`backend/agent_runner/`).

**Sandbox Kilocode Runner**
- [x] Define e2b template (managed in e2b; set `KILOCODE_TEMPLATE_NAME`) that installs Kilocode, sets env vars, and runs commands.
- [x] Implement `SandboxKilocodeRunner`: start sandbox, upload plan/context, run Kilocode, create branch + draft PR, stream logs back via `/jobs/{id}`.
- [x] Document filesystem/command considerations (refs: `/docs/filesystem/*`, `/docs/commands`, `/docs/sandbox/environment-variables`, `/docs/sandbox/persistence`).

**Dashboard**
- [x] `app/api/clusters/[id]/start_fix/route.ts` → pure proxy to backend.
- [x] Cluster detail page: fetch/show coding plan, allow light edits, display active runner (from `NEXT_PUBLIC_CODING_AGENT_RUNNER`).
- [x] Job/log UI: poll `/jobs?cluster_id=...`, render log stream + PR link/draft status.

**Docs/References**
- [x] Update `coding-agent/README.md` with sandbox template instructions and links (Kilocode provider config, e2b template docs, CLI).
- [x] Keep `tasks/coding_agent_plan.md` as source of truth; ensure roadmap references stay in sync.

## Documentation Links
- Coding agent plan & strategy: `tasks/coding_agent_plan.md`
- Data model background: `documentation/db_design.md`

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

```text
┌─────────────────────────────────────────────┐
│ Phase 1-3: Ingestion Stability              │
│ Worktree: system-readiness                  │
│ Time: ~3-5 days                             │
│ Files: store.py, main.py, reddit_poller.py  │
└─────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│ Phase 4: Backend Async Clustering           │
│ Worktree: system-readiness                  │
│ Time: ~5-7 days                             │
│ Files: clustering.py, clustering_runner.py, │
│       main.py, models.py                    │
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
