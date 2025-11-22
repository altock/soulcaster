FeedbackAgent – Combined MVP PRD (24h Hackathon)

Status: Draft  
 Timeline: 24h (2 devs, \~12h coding)  
 Priority: Prove the loop, not productionize it

---

## **1\. Executive Summary**

Build a “self-healing dev loop” MVP:

Reddit/Sentry → Clustered Issues → human reviews on triage dashboard \-\> One‑Click Fix → GitHub PR

Constraints:

* Single target repo.

* Happy-path only.

* Prioritize functional code over robustness, tests, or scale.  
* Test Driven Development (TDD)

---

## **2\. Scope & Guardrails**

### **2.1 What We’re Building (MVP)**

* Python ingestion service:

  * Polls Reddit for bug reports (PRAW).

  * Receives Sentry webhooks.

* LLM-based triage:

  * Embedding-based clustering of feedback into “issues.”

  * LLM summaries per cluster.

* Next.js dashboard on Vercel:

  * Shows clustered issues.

  * One‑click “Generate Fix.”

* Coding agent (Python):

  * Uses GitHub API (PyGithub) to fetch candidate files.

  * Generates code patch via LLM.

  * Runs basic code reviews, optionally with CodeRabbit.

  * Opens a real PR on GitHub.

### **2.2 What We’re NOT Building (for 24h)**

* No auth/permissions (hardcoded keys / env only).

* No multi-repo routing (one repo only).

* No historical backfill or complex search.

* No robust retries / rate limiting / observability.

* No chat UI (this is “click to fix,” not a chatbot).

* No serious test suite (manual happy-path verification only).

---

## **3\. System Overview – The Loop**

* **The Ears (Ingestion)**  
   Reddit poller \+ Sentry webhook → normalized feedback items.

* **The Brain (Triage \+ Coding)**  
   Embedding-based clustering \+ LLM summaries → coding agent that turns a cluster into a patch.

* **The Hands (Execution)**  
   GitHub API (and optionally Actions later) → branch \+ commit \+ PR.

---

## **4\. MVP Scope Details**

### **4.1 Ingestion Layer (The Ears)**

#### **Reddit Poller**

* Script: `reddit_poller.py` (Python).

* Tech: PRAW.

* Behavior:

  * Poll specified subreddits every N minutes (e.g., 1–5).

  * Filter posts/comments by keywords: `"bug"`, `"broken"`, `"error"`, `"crash"`, `"doesn't work"`, `"feature"`.

  * Normalize to `FeedbackItem` and send to backend via `POST /ingest/reddit`.

* Normalized `FeedbackItem` fields (for Reddit):

  * `id` (internal UUID).

  * `source = "reddit"`.

  * `external_id` (Reddit ID).

  * `title` (post title or first 80 chars of comment).

  * `body` (full text, truncated to max length).

  * `metadata` (subreddit, permalink, author, created\_utc).

  * `created_at`.

#### **Sentry Webhook**

* Endpoint: `POST /ingest/sentry` (FastAPI).

* Body: Sentry event JSON.

* Behavior:

  * Extract:

    * `title` (Sentry issue title).

    * `body` \= error message \+ top 1–3 stack frames (filename:line).

    * `metadata` \= project, environment, release, tags, event\_id, timestamp.

  * Normalize to `FeedbackItem` with:

    * `source = "sentry"`, `external_id = event_id`.

Storage (MVP):

* Keep `FeedbackItem`s in an in-memory store (Python dict or list).

* Post‑Hackathon: swap to Redis/Supabase.

---

### **4.2 Triage Agent (The Brain – Part 1\)**

Goal: Turn noisy feedback into deduped “Issue Clusters” for humans to act on.

#### **Data Model (Conceptual)**

* `FeedbackItem`:

  * `id`

  * `source` ("reddit" | "sentry")

  * `external_id`

  * `title`

  * `body`

  * `metadata` (JSON)

  * `created_at`

  * `embedding` (vector or opaque blob)

* `IssueCluster`:

  * `id`

  * `title` (LLM-generated issue title)

  * `summary` (2–3 sentence description)

  * `feedback_ids` (list of `FeedbackItem.id`)

  * `status` ("new" | "fixing" | "pr\_opened" | "failed")

  * `created_at`

  * `updated_at`

  * `embedding_centroid` (vector)

  * `github_branch` (optional)

  * `github_pr_url` (optional)

  * `error_message` (optional for failures)

#### **Clustering Logic (Happy-Path)**

On ingest of a new `FeedbackItem`:

1. Compute embedding for `body` (or `title + body`).

   * Threshold-based nearest neighbor.

   * Similarity metric: cosine.

2. Compare to all open clusters’ centroids:

   * If best similarity ≥ 0.8–0.85:

     * Attach feedback to that cluster:

       * Append `feedback_id`.

       * Update centroid as mean of member embeddings.

   * Else:

     * Create new `IssueCluster` with this single feedback.

3. Summarization:

   * For any new cluster:

     * Call LLM with up to N sample feedback bodies (e.g., up to 5).

     * Output JSON:

       * `title`: ≤80 characters.

       * `summary`: ≤300 characters.

No manual merge/split in MVP.

#### **Triage Endpoints (Backend)**

* `GET /clusters`

  * Returns list: `id`, `title`, `summary`, `count`, `status`, `sources[]`, `github_pr_url?`.

* `GET /clusters/{id}`

  * Returns cluster \+ sample `FeedbackItem`s.

* `POST /clusters/{id}/start_fix`

  * Sets `status="fixing"` and triggers Coding Agent.

---

### **4.3 Coding Agent (The Brain – Part 2\)**

Goal: For a chosen cluster, generate a minimal code patch and open a PR.

Assumptions:

* One target GitHub repo.

* MVP target language: Python (for syntax check).

* No tests run, just syntax sanity.

#### **Context Construction**

Inputs:

* Cluster data:

  * `title`, `summary`, up to 3 raw feedback texts.

* Repo data:

  * File path list (from GitHub API, cached).

  * Optional: repo description/stack hints from env.

#### **Candidate File Selection**

Heuristics:

1. From Sentry-based feedback:

   * Extract filenames from stack frames (regex on `filename` fields).

   * Match against repo paths (suffix match or contains).

2. From text:

   * Extract keywords from cluster title.

   * Select files whose path contains those tokens (case-insensitive).

3. Limit to:

   * Max 3–5 candidate files.

   * Max size per file (e.g., 10k chars).

If nothing found:

* Fallback: send a truncated file path list to the LLM and ask it to select 1–2 paths.

#### **Patch Generation (LLM)**

Prompt:

* Explain bug (cluster summary \+ feedback snippets).

* Include file path \+ current content for each candidate.

* Instruct LLM:

  * Make the smallest possible change that plausibly fixes this issue.

  * Do not refactor unrelated code.

Return JSON:

 {  
  "files": \[  
    {  
      "path": "path/to/file.py",  
      "updated\_content": "\<full file content after edit\>"  
    }  
  \],  
  "summary": "Short human-readable description of the change."  
}

* 

MVP: we do full-file replacement, not diff parsing.

#### **Syntax Check**

* For each modified `.py` file:

  * Run `ast.parse(updated_content)` in Python.

* If any parse fails:

  * Mark cluster `status="failed"`.

  * Store parse error in `error_message`.

* If parse passes (or file is non-Python), proceed.

(Real multi-language linting is Post‑Hackathon.)

#### **Branch & PR Creation (Execution Layer – The Hands)**

Using PyGithub:

1. Resolve target repo & base branch (`GITHUB_REPO`, `BASE_BRANCH`).

2. Create branch name:

   * `feedbackagent/cluster-{id}-{slugified-title}`.

3. For each modified file:

   * Fetch current file via `get_contents(path, ref=base_branch)` to get `sha`.

   * Use `update_file` / `create_file` on new branch with `updated_content`.

4. Create PR:

   * Title: `Fix: {cluster.title}`

   * Body:

     * LLM `summary`.

     * Cluster `summary`.

     * List of feedback sources (links to Reddit/Sentry where available).

     * Note: “Auto-generated by FeedbackAgent; please review carefully.”

5. Update `IssueCluster`:

   * `status="pr_opened"`

   * `github_branch`, `github_pr_url`.

Failure: any exception marks `status="failed"` and logs `error_message`. No automatic retries in MVP.

---

### **4.4 Dashboard (Next.js on Vercel)**

Minimal but usable.

#### **Views**

**Clusters List (Main Page)**

* Table of `IssueCluster`s:

  * Columns:

    * Title

    * Summary (truncated)

    * Count (\# feedback)

    * Sources (icons: Reddit / Sentry)

    * Status badge:

      * `new`, `fixing`, `pr_opened`, `failed`

    * Actions:

      * “Generate Fix” button (enabled if `status` in \[`new`, `failed`\]).

**Cluster Detail View**

* Route: `/clusters/[id]` or modal.

* Shows:

  * Title, summary, created/updated timestamps.

  * Counts by source (e.g., 3 Reddit, 2 Sentry).

  * Sample feedback list:

    * Text snippet.

    * Link to Reddit or Sentry issue page when available.

  * If `github_pr_url`:

    * Button: “View PR in GitHub.”

  * If `status="failed"`:

    * Show `error_message`.

#### **Dashboard–Backend API Contract**

Next.js API routes proxy to backend:

* `GET /api/clusters` → backend `/clusters`

* `GET /api/clusters/[id]` → backend `/clusters/{id}`

* `POST /api/clusters/[id]/start_fix` → backend `/clusters/{id}/start_fix`

Behavior:

* When “Generate Fix” clicked:

  * Call `start_fix`.

  * Optimistically set state to “Running…” and poll detail endpoint until `status` is `pr_opened` or `failed`.

---

## **5\. Technical Architecture**

### **5.1 Stack**

* Frontend:

  * Next.js (App Router).

  * Hosted on Vercel.

  * UI library: optional (e.g., shadcn/ui), but plain Tailwind is fine.

* Backend:

  * Python \+ FastAPI (recommended).

  * Single service:

    * Ingestion endpoints.

    * Triage logic.

    * Coding agent.

    * GitHub integration.

* Storage (MVP):

  * In-memory Python dicts for:

    * `feedback_items`

    * `issue_clusters`

  * No durable DB required to prove the loop.

* LLM / Embeddings:

  * Model-agnostic via wrapper (e.g., LiteLLM).

  * Recommended split:

    * Fast/cheap model (e.g., Gemini Flash-style) for embeddings & summaries.

    * Stronger model (e.g., Claude Sonnet-style) for code generation.

* Queue:

  * Simple in-process background tasks (threads / asyncio).

  * No external queue system.

### **5.2 Key Libraries / Tools**

* PRAW – Reddit polling.

* PyGithub – GitHub repo access \+ PR creation.

* FastAPI – Backend HTTP server.

* Next.js – Dashboard.

* LiteLLM (optional) – Model routing / abstraction.

### **5.3 TODO Decisions for Humans**

* LLM provider \+ models for:

  * summarization,

  * embeddings,

  * code generation.

* Storage choice:

  * stick with in-memory for demo vs. wire Supabase/Redis.

* Deployment target for Python backend (Railway/Render/fly/etc.).

* Single target repo \+ branch conventions.

---

## **6\. User Flow (Happy Path)**

1. **User reports bug**

   * Redditor posts “Export crashes on Safari” in your project subreddit.

   * Or a Sentry event fires: “Unhandled exception in export handler.”

2. **FeedbackAgent ingests**

   * Reddit poller detects keywords and posts to `/ingest/reddit`.

   * Sentry sends webhook to `/ingest/sentry`.

   * Backend creates `FeedbackItem` records.

3. **Triage agent clusters**

   * New feedback gets an embedding.

   * Similarity ≥ threshold with existing “Export crash” cluster → added there.

   * Cluster summary is updated or created via LLM.

4. **Dashboard shows cluster**

   * Next.js dashboard calls `/clusters`.

   * “Export crash in Safari” appears as a row with 4 reports (3 Reddit, 1 Sentry).

5. **Human clicks “Generate Fix”**

   * Dev opens cluster detail, confirms it’s legit.

   * Clicks “Generate Fix.”

6. **Coding agent generates patch**

   * Backend:

     * Marks status `fixing`.

     * Picks candidate files (e.g., `components/ExportButton.tsx` or `export.py`).

     * Calls LLM with context to produce updated file content.

     * Runs basic syntax check (Python).

7. **PR is opened**

   * Backend:

     * Creates branch \+ commit.

     * Opens PR: `Fix: Export crash in Safari`.

   * Cluster status set to `pr_opened`.

   * Dashboard shows PR link.

8. **Human/bot reviews & merges**

   * Human or CodeRabbit reviews PR.

   * After merge, FeedbackAgent is done; status can be updated manually post-MVP if desired.

---

## **7\. Implementation Plan (2 devs, \~12h)**

Assume:

* Dev A – Python/backend/agents.

* Dev B – Next.js/frontend.

Time is approximate; keep scope ruthless.

### **Phase 1 – Foundations (“The Pipes”) – \~3h**

**Dev A**

* Scaffold FastAPI app with endpoints:

  * `POST /ingest/reddit`

  * `POST /ingest/sentry`

  * `GET /clusters`

  * `GET /clusters/{id}`

  * `POST /clusters/{id}/start_fix` (stub).

* Implement in-memory stores:

  * `feedback_items` map.

  * `issue_clusters` map.

* Implement very naive clustering (no embeddings yet, just new cluster per feedback) to unblock UI.

**Dev B**

* Scaffold Next.js app on Vercel (or locally).

* Create `/` page with static mock cluster list.

* Create basic table UI with:

  * Title, count, status, “Generate Fix” (dummy click).

### **Phase 2 – Triage (“The Brain – Part 1”) – \~3h**

**Dev A**

* Implement `EmbeddingClient` and `LLMClient` wrappers (using chosen provider).

* Implement real clustering:

  * Embedding per feedback.

  * Similarity threshold logic.

  * Centroid maintenance.

* Implement LLM summarization for new clusters.

**Dev B**

* Wire `/` page to `GET /api/clusters` → backend.

* Implement cluster detail page:

  * `GET /api/clusters/[id]`.

  * Show sample feedback items.

Milestone: Real clusters and summaries appear on dashboard.

### **Phase 3 – Coding Agent (“The Brain – Part 2”) – \~3h**

**Dev A**

* Integrate PyGithub:

  * Connect to target repo.

  * Cache file tree.

* Implement candidate file selection heuristics (stack traces \+ title keywords).

* Implement patch generation:

  * Prompt building.

  * LLM call.

  * JSON parsing into `{path, updated_content}` objects.

* Implement syntax check (Python `ast.parse`).

**Dev B**

* Implement `POST /api/clusters/[id]/start_fix` → backend.

* Add UI state for “fixing”:

  * Disable button.

  * Poll cluster status on interval.

Milestone: “Generate Fix” triggers code generation, syntax check, but PR may still be stubbed.

### **Phase 4 – PR Integration (“The Hands”) – \~2h**

**Dev A**

* Implement branch \+ commit \+ PR creation flow via PyGithub.

* Set cluster `status` and `github_pr_url`.

* Ensure basic error handling for obvious failures.

**Dev B**

* Show PR link on cluster detail page when `github_pr_url` present.

* Show error message for `status="failed"`.

Milestone: End-to-end: ingest → cluster → click → PR.

### **Phase 5 – Polish & Demo – \~1h**

**Both**

* Add minimal logging.

* Seed example feedback (curl scripts, JSON fixtures).

* Update README:

  * Setup env vars.

  * How to run backend/frontend.

  * How to configure Reddit/Sentry/GitHub.

* Run final demo: record or rehearse.

---

## **8\. Future Scope (Tagged)**

These are explicitly Post‑Hackathon. Tags in brackets.

* Replace in-memory storage with real DB

  * `[db change]` Supabase Postgres schema for `feedback_items`, `issue_clusters`, embeddings.

  * `[db change]` Add indices on `status`, `created_at` for faster dashboard queries.

* Improve infra and frameworks

  * `[framework changes]` Introduce Redis for queues and caching embeddings/file trees.

  * `[framework changes]` Add GitHub Actions pipeline to: checkout repo, apply patch, run tests, then open PR.

* Enhance UI/UX

  * `[ui changes]` Cluster merge/split controls, labels, and severity tags.

  * `[ui changes]` Filters (source, status, timeframe), search, and pagination.

  * `[ui changes]` Timeline view of incidents per cluster.

* Smarter agent behavior

  * `[agent logic]` Multi-language syntax checks (TS/JS/Go/… via appropriate tools).

  * `[agent logic]` Limited RAG over codebase (index core modules, not full monorepo).

  * `[agent logic]` Auto-close clusters when linked PR merges.

* Productization

  * `[auth/security]` GitHub OAuth and per-user repos/projects.

  * `[auth/security]` Signed webhooks and strict token scoping.

  * `[ops]` Metrics, tracing, structured logs, rate limiting, and retry policies.

---

## **9\. Success Metrics (for MVP)**

* ≥1 real PR opened from real Reddit or Sentry feedback.

* Dashboard shows clustered issues with sensible summaries.

* Full loop (ingest → cluster → click → PR) completes in \<2 minutes on average for small repos.

* Devs feel comfortable reviewing, not re-writing, the auto-generated PR.

