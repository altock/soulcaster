# GitHub Integration & Test Data Plan

This plan outlines the steps to implement comprehensive GitHub issue ingestion and test data generation for the Soulcaster platform, following a Test Driven Development (TDD) approach.

## Overview

**Goal:** Create a robust GitHub integration that can ingest issues from real repositories, generate test data for development, and ensure clustering works correctly.

**Estimated Time:** 5-7 days  
**Priority:** 🔥 HIGH (Critical for demo and customer validation)

---

## Phase 1: GitHub Issue Ingestion (Days 1-2)

### 1.1 Environment Setup
- [ ] Verify GitHub OAuth is configured in dashboard
  - [ ] `GITHUB_ID` set
  - [ ] `GITHUB_SECRET` set
  - [ ] `GITHUB_TOKEN` for API rate limits
- [ ] Test GitHub API connection:
  ```bash
  curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
  ```

### 1.2 Domain Models Extension
- [ ] Open `backend/models.py`
- [ ] Extend `FeedbackItem` to support GitHub-specific metadata:
  ```python
  class GitHubMetadata(BaseModel):
      issue_number: int
      repo_owner: str
      repo_name: str
      issue_url: str
      labels: List[str]
      state: str
      assignees: List[str]
      comments_count: int
      reactions: dict
  ```

### 1.3 GitHub API Client
- [ ] Create `backend/github_client.py`
- [ ] Implement functions:
  ```python
  def get_repo_issues(owner: str, repo: str, state: str = "open") -> List[dict]
  def get_issue_details(owner: str, repo: str, issue_number: int) -> dict
  def get_issue_comments(owner: str, repo: str, issue_number: int) -> List[dict]
  def search_issues_by_label(owner: str, repo: str, labels: List[str]) -> List[dict]
  ```
- [ ] Add rate limit handling with exponential backoff
- [ ] Add logging for all API calls

### 1.4 Tests for GitHub Client
- [ ] Create `backend/tests/test_github_client.py`
- [ ] Test cases:
  ```python
  def test_get_repo_issues_success():
      # Mock GitHub API response
      # Verify data normalization
  
  def test_get_repo_issues_rate_limited():
      # Mock 403 rate limit response
      # Verify retry logic with backoff
  
  def test_normalize_github_issue_to_feedback():
      # Verify conversion to FeedbackItem
  ```

### 1.5 API Endpoints
- [ ] Extend `backend/main.py` with GitHub endpoints:
  ```python
  @app.post("/ingest/github/repo/{owner}/{repo}")
  async def ingest_github_repo(owner: str, repo: str, labels: Optional[List[str]] = None)
  
  @app.post("/ingest/github/issue")
  async def ingest_github_issue(issue_url: str)
  
  @app.get("/config/github/repos")
  async def get_tracked_repos()
  
  @app.post("/config/github/repos")
  async def add_tracked_repo(owner: str, repo: str, labels: Optional[List[str]] = None)
  ```

### 1.6 Integration Tests
- [ ] Create `backend/tests/test_github_ingestion.py`
- [ ] Test full flow:
  ```python
  def test_ingest_github_repo_creates_feedback_items():
      # Mock GitHub API
      # Call endpoint
      # Verify items in Redis
      # Verify in feedback:unclustered
  
  def test_ingest_respects_label_filters():
      # Only bugs labeled "bug" are ingested
  ```

---

## Phase 2: Test Data Generation (Days 3-4)

### 2.1 Enhanced Test Data Generator
- [ ] Create `scripts/generate_github_test_data.py` with:
  - [ ] Multiple code modules (math, string, user management, API client, database layer)
  - [ ] More sophisticated bugs (race conditions, memory leaks, security issues)
  - [ ] Realistic issue clusters (5-10 issues per bug)
  - [ ] Noise issues (documentation, enhancements, questions)

### 2.2 Issue Templates
- [ ] Define issue cluster templates:
  ```python
  CLUSTER_TEMPLATES = {
      "division_by_zero": {
          "severity": "critical",
          "count": 5,
          "variations": [...],
      },
      "memory_leak": {
          "severity": "high",
          "count": 4,
          "variations": [...],
      },
      "race_condition": {
          "severity": "high",
          "count": 6,
          "variations": [...],
      },
  }
  ```

### 2.3 Repo Creation Automation
- [ ] Add functions to:
  ```python
  def create_github_repo(token: str, repo_name: str, description: str) -> str
  def initialize_repo_with_code(repo_url: str, code_modules: List[str])
  def create_issue_batch(repo: str, issues: List[dict], delay: int = 2)
  ```

### 2.4 Test Data Validation
- [ ] Create validation script `scripts/validate_test_data.py`:
  ```python
  def validate_repo_structure(repo_url: str) -> bool
  def validate_issue_clusters(repo_url: str, expected_clusters: int) -> bool
  def validate_noise_ratio(repo_url: str, expected_ratio: float) -> bool
  ```

---

## Phase 3: Dashboard Integration (Day 5)

### 3.1 GitHub Config UI
- [ ] Create `dashboard/components/GitHubRepoConfig.tsx`:
  - [ ] List tracked repositories
  - [ ] Add new repository form
  - [ ] Configure label filters
  - [ ] Manual sync button per repo
  - [ ] Display last sync timestamp

### 3.2 API Routes
- [ ] Create `dashboard/app/api/config/github/repos/route.ts`:
  ```typescript
  export async function GET() {
    // Fetch tracked repos from Redis
  }
  
  export async function POST(req: Request) {
    // Add new tracked repo
  }
  ```

### 3.3 GitHub Helper Functions
- [ ] Create `dashboard/lib/github.ts`:
  ```typescript
  export async function syncGitHubRepo(owner: string, repo: string): Promise<{synced: number}>
  export async function getTrackedRepos(): Promise<TrackedRepo[]>
  export async function addTrackedRepo(owner: string, repo: string, labels?: string[]): Promise<void>
  ```

### 3.4 Tests
- [ ] Create `dashboard/__tests__/lib/github.test.ts`:
  ```typescript
  describe('syncGitHubRepo', () => {
    it('should sync issues and return count', async () => {
      // Test implementation
    });
  });
  ```

---

## Phase 4: Polling & Automation (Days 6-7)

### 4.1 GitHub Poller Service
- [ ] Create `backend/github_poller.py`:
  ```python
  class GitHubPoller:
      def __init__(self, interval_seconds: int = 300):
          self.interval = interval_seconds
      
      async def poll_once(self):
          """Poll all tracked repos for new issues"""
          tracked_repos = await get_tracked_repos()
          for repo in tracked_repos:
              await sync_repo_issues(repo.owner, repo.name, repo.labels)
      
      async def run_forever(self):
          """Continuous polling loop"""
          while True:
              await self.poll_once()
              await asyncio.sleep(self.interval)
  ```

### 4.2 Deduplication Logic
- [ ] Add to `backend/store.py`:
  ```python
  def is_duplicate_issue(external_id: str, source: str) -> bool:
      """Check if issue already exists"""
      return redis.exists(f"feedback:external:{source}:{external_id}")
  
  def mark_issue_ingested(external_id: str, source: str, feedback_id: str):
      """Track ingested issues to prevent duplicates"""
      redis.set(f"feedback:external:{source}:{external_id}", feedback_id)
  ```

### 4.3 Webhook Support (Optional)
- [ ] Create endpoint `POST /webhooks/github`:
  ```python
  @app.post("/webhooks/github")
  async def github_webhook(payload: dict, x_github_event: str):
      """Handle GitHub webhooks for real-time ingestion"""
      if x_github_event == "issues":
          action = payload.get("action")
          if action in ["opened", "reopened"]:
              issue = payload["issue"]
              await ingest_github_issue_data(issue)
  ```

### 4.4 Tests
- [ ] Create `backend/tests/test_github_poller.py`:
  ```python
  def test_poller_respects_deduplication():
      # Run poller twice
      # Verify no duplicate feedback items
  
  def test_poller_handles_api_errors():
      # Mock GitHub API failure
      # Verify poller continues
  ```

---

## Phase 5: End-to-End Testing (Day 7)

### 5.1 Integration Test Suite
- [ ] Create `backend/tests/test_e2e_github.py`:
  ```python
  async def test_full_github_flow():
      """Test: Add repo -> Sync issues -> Cluster -> Generate PR"""
      # 1. Add tracked repo via API
      # 2. Trigger sync
      # 3. Verify issues in feedback:unclustered
      # 4. Run clustering
      # 5. Verify cluster created
      # 6. Trigger coding agent
      # 7. Verify PR created
  ```

### 5.2 Load Testing
- [ ] Test with real repos:
  - [ ] Small repo (10-50 issues)
  - [ ] Medium repo (100-500 issues)
  - [ ] Large repo (1000+ issues)
- [ ] Measure:
  - [ ] Ingestion time
  - [ ] Memory usage
  - [ ] Clustering accuracy
  - [ ] Rate limit handling

### 5.3 Documentation
- [ ] Update `documentation/db_design.md`:
  - [ ] Document new Redis keys: `config:github:repos`, `feedback:external:github:*`
  - [ ] Add data flow diagram
- [ ] Update `README.md`:
  - [ ] Add GitHub setup instructions
  - [ ] Document webhook configuration

---

## Acceptance Criteria (All Phases Complete)

Before marking this complete, verify:

- ✅ **GitHub ingestion works for any public repo**
  - Test: Sync issues from 3 different repos
  
- ✅ **Test data generator creates realistic clusters**
  - Test: Generate repo, verify 5+ distinct clusters
  
- ✅ **Dashboard shows GitHub config UI**
  - Test: Add/remove tracked repos via UI
  
- ✅ **Poller runs without errors**
  - Test: Run poller for 1 hour, check logs
  
- ✅ **No duplicate issues**
  - Test: Sync same repo twice, verify deduplication
  
- ✅ **Rate limiting handled gracefully**
  - Test: Mock 429 response, verify backoff
  
- ✅ **All tests pass**
  - Run: `pytest backend/tests -v --cov=backend`
  - Coverage: >85% on new code

---

## Quick Start Commands

```bash
# Generate test data for a new repo
python scripts/generate_github_test_data.py https://github.com/YOUR_USERNAME/test-repo $GITHUB_TOKEN

# Start GitHub poller
python -m backend.github_poller

# Sync a specific repo
curl -X POST http://localhost:8000/ingest/github/repo/owner/repo -H "Authorization: Bearer $TOKEN"

# Run tests
pytest backend/tests/test_github_*.py -v
```

---

## Common Issues & Solutions

### Issue: "Rate limit exceeded"
**Solution:** 
- Increase polling interval
- Use authenticated requests (higher rate limit)
- Implement exponential backoff

### Issue: "Webhook not receiving events"
**Solution:**
- Verify webhook URL is publicly accessible
- Check webhook secret validation
- Review GitHub webhook delivery logs

### Issue: "Clustering creates too many small clusters"
**Solution:**
- Adjust embedding similarity threshold
- Increase minimum cluster size
- Improve issue text normalization

---

## Next Steps After Completion

1. **Customer Onboarding**: Use test data to demo to first design partners
2. **Analytics**: Track which issue types convert to PRs most effectively
3. **Optimization**: Implement incremental sync (only fetch new issues)
4. **Multi-Source**: Combine GitHub + Reddit + Sentry for richer clustering
