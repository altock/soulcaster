# Coding-Agent Plan & Strategy (Phase 5.1 – WIP)

Goal: transform each IssueCluster into a structured coding plan and execute that plan via a pluggable coding-agent runner (default: Kilocode inside an e2b sandbox) while keeping the legacy AWS path available but dormant. The new flow skips GitHub issue creation—each run opens a branch and draft PR like modern coding agents. All LLM reasoning stays inside the sandbox (Kilocode template + prompts) rather than running in the backend.

## Overview & Desired Flow
1. **Plan generation** – Backend creates a `CodingPlan` (summary, hypotheses, candidate files, validation steps) whenever a cluster loads or a plan regeneration is requested.
2. **Cluster view** – Dashboard fetches and displays the plan on the cluster detail page, allowing light edits before execution.
3. **Trigger fix** – Dashboard calls `/api/clusters/[id]/start_fix`, which simply proxies to backend `POST /clusters/{id}/start_fix`.
4. **Backend orchestration** – `/clusters/{id}/start_fix` becomes the single entry point: ensure plan exists, create `AgentJob`, pick a runner via `CODING_AGENT_RUNNER` (default `sandbox_kilo`, optional `aws_kilo`, future providers), and start the job.
5. **Runner execution** – Selected runner clones the repo, applies the plan, runs validation/tests, and opens a PR while streaming logs/status back to `/jobs/{id}`.
6. **Result propagation** – Backend updates the job + cluster metadata (status, PR URL, log excerpts); dashboard polls `/jobs` to show progress.

## Current State Recap
- Clusters and jobs already exist in FastAPI (`/clusters`, `/jobs`).
- Dashboard currently triggers the AWS agent directly (`/api/trigger-agent`) before calling backend `/clusters/{id}/start_fix`, which only flips status.
- Legacy runner (`coding-agent/fix_issue.py`) expects a GitHub issue URL and runs on ECS/Fargate via Kilocode CLI. Phase 5.1 removes that dependency by going straight to branch creation + draft PR.

## Implementation Status (PR #28)
- Backend exposes `GET/POST /clusters/{id}/plan` and stores `CodingPlan` records.
- `POST /clusters/{id}/start_fix` creates an `AgentJob`, clears cluster errors, infers `github_repo_url` from feedback items, and dispatches the configured runner.
- `SandboxKilocodeRunner` persists logs per job (Redis-backed where available) and the dashboard tails them via `GET /jobs/{id}/logs`.
- GitHub auth uses OAuth (required): users must sign in with GitHub. Their token is passed from dashboard → backend → E2B sandbox. PRs are created from the user's account (e.g., @username). Runner uses non-interactive git auth (no prompts).
- Future: GitHub App support planned for bot-based PRs (soulcaster[bot]).

## Target Architecture Components
1. **Plan generator** – Backend module that reads cluster + feedback items and stores a `CodingPlan` (Redis) with timestamps + metadata.
2. **Orchestrator endpoint** – Enhanced `POST /clusters/{id}/start_fix` that owns plan generation, job creation, runner selection, sandbox/provider setup, and status streaming.
3. **Runner registry** – Shared interface (e.g., `AgentRunner` protocol) with concrete implementations:
   - `SandboxKilocodeRunner` (default): spin up e2b sandbox, install deps, run Kilocode with plan context.
   - `AwsKilocodeRunner` (legacy): reuse existing ECS/Kilo flow for parity testing.
   - Future runners: other coding agents or sandbox vendors, selectable via env/config.
4. **Dashboard UX** – Shows the generated plan, allows minor edits, and polls `/jobs`; it remains agnostic to the runner type.

## Implementation Steps

### 1. Define data contracts
- Add `CodingPlan` model stored alongside clusters (Redis) with fields: cluster_id, plan text/JSON, metadata, created_at, updated_at.
- Extend `AgentJob` with `plan_id`, `runner`, `artifact_url`, and richer log metadata.
- Document plan + job schema in this file / inline docstrings (no separate doc needed).

### 2. Plan generation module
- Create `backend/planner.py` (or similar) responsible for generating/upserting plans via LLM (Gemini, etc.).
- Expose REST endpoints:
  - `POST /clusters/{cluster_id}/plan` → generate/regenerate.
  - `GET /clusters/{cluster_id}/plan` → fetch latest plan for dashboard.
- Add retries, validation, and audit timestamps.

### 3. Runner orchestration (`POST /clusters/{id}/start_fix`)
- Update existing endpoint to:
  - Ensure plan exists (generate if missing, or return 409 requiring user confirmation).
  - Create an `AgentJob` record and return the ID immediately.
  - Determine runner via `CODING_AGENT_RUNNER` (default `sandbox_kilo`; others: `aws_kilo`, future ones).
  - Dispatch to the appropriate runner via registry (async task, worker queue, or background thread) and stream logs back to `/jobs/{id}`.
- Background responsibilities for each runner:
  - Prepare sandbox/provider session (e2b, ECS, etc.).
  - Inject plan + cluster context + repo metadata + tokens.
  - Capture stdout/stderr, update job logs, and handle errors/timeouts.
  - Create a branch and draft PR (no GitHub issue needed) with plan/context in the description.
  - Report completion with PR URL / failure reason.

### 4. Runner implementations & modularity
- Create `backend/agent_runner/` package with:
  - Shared utilities (repo checkout, PR helpers, log streaming).
  - `SandboxKilocodeRunner`: uses e2b SDK ([docs](https://e2b.dev/docs), [SDK reference](https://e2b.dev/docs/sdk-reference)) plus a reusable template (see Template links below) to spawn a sandbox, install Kilocode, run commands, and push branches. All coding-plan prompts are passed directly to Kilocode inside the sandbox—no backend LLM calls.
  - `AwsKilocodeRunner`: wraps existing ECS trigger or reuses `coding-agent/fix_issue.py` for environments that still rely on AWS.
- Provide env-driven configuration so swapping runners or sandbox providers requires no dashboard/code changes.

### 5. Dashboard updates
- `app/api/clusters/[id]/start_fix/route.ts` becomes a simple proxy to backend `/clusters/{id}/start_fix` (no direct runner calls).
- Legacy `/api/trigger-agent` remains for manual ECS triggers but is not used by default.
- Cluster detail page:
  - Fetch and render the coding plan (call `GET /clusters/{id}/plan`).
  - Allow light editing (optional) before calling start_fix.
  - Show which runner is active (read `NEXT_PUBLIC_CODING_AGENT_RUNNER`) for transparency.
- Job monitoring UI:
  - Poll `/jobs?cluster_id=...` and render streamed logs + PR links/error states.

### 6. Observability & safeguards
- Persist plan + job logs for auditing; consider storing plan snapshots alongside job records.
- Implement job cancellation/timeouts; allow admin cancellation via PATCH `/jobs/{id}`.
- Emit metrics (success rate, avg runtime, failure causes) for dashboard stats.

### 7. Migration strategy
- Default `CODING_AGENT_RUNNER` to `sandbox_kilo`; keep `aws_kilo` available for parity.
- Provide rollout checklist: e2b credentials, Kilocode provider config, GitHub tokens, Redis schema changes, dashboard env updates.
- Once sandbox runner stabilizes, deprecate routine use of AWS runner, but keep registry pattern so new agents/sandboxes can be added easily.

## Deliverables
- Backend planner module + endpoints with tests.
- Enhanced `/clusters/{id}/start_fix` orchestrator + runner registry + sandbox runner implementation.
- Updated dashboard cluster detail + API proxy + job monitoring.
- Documentation (this file) referencing Kilocode and e2b docs.
- Feature flags/env vars for runner selection.

## References
- Kilocode CLI & provider config: see `coding-agent/README.md` and upstream doc `https://github.com/Kilo-Org/kilocode/blob/ed3e401d7ab153bab5619219ed69ca62badfcef0/cli/docs/PROVIDER_CONFIGURATION.md`.
- e2b template + sandbox docs (helpful when building the Kilocode template that runs entirely in the sandbox):
  - Templates: `/docs/template/quickstart`, `/docs/template/how-it-works`, `/docs/quickstart/install-custom-packages`, `/docs/template/examples/claude-code`, `/docs/template/defining-template.md`
  - Filesystem: `/docs/filesystem`, `/docs/filesystem/read-write`, `/docs/filesystem/watch`, `/docs/filesystem/upload`, `/docs/filesystem/download`
  - Commands & runtime: `/docs/commands`, `/docs/sandbox/environment-variables`, `/docs/sandbox/persistence`
  - Other: `/docs/cli`, `/docs/sandbox/secured-access`, `/docs/sandbox/connect-bucket`
- e2b SDK reference: [https://e2b.dev/docs/sdk-reference](https://e2b.dev/docs/sdk-reference)

## Known Failure Modes & Troubleshooting
### ~~PR creation fails after branch push~~ **[RESOLVED - 2025-12-16]**
**Status**: Fixed in `backend/agent_runner/sandbox.py`

**What was broken**:
- PR creation would fail silently when old gh CLI didn't support `--json` flag
- PR URLs weren't extracted from "already exists" error messages
- Cluster status stayed as "fixing" even after successful job completion (missing `update_cluster` import)
- PR descriptions had literal `\n` instead of actual newlines

**Fixes applied**:
1. **Improved fallback logic**: Now properly extracts PR URLs from output even when `--json` flag fails
2. **Find existing PRs first**: Before creating new PR, checks if one already exists for the branch using `gh pr list --head`
3. **Extract from "already exists" errors**: Regex now captures PR URL from error messages like `"a pull request...already exists: https://github.com/..."`
4. **Fixed missing import**: Added `update_cluster` to imports so cluster status properly updates to "pr_opened"
5. **Fixed PR body formatting**: Changed `\n` to `\\n` so markdown renders correctly
6. **Draft PR workflow**: Creates draft PR early, runs Kilocode, then updates description with Gemini and marks ready

**Current behavior** (post-fix):
- Creates draft PR immediately after pushing empty commit
- Runs Kilocode to make actual changes
- Generates PR description using Gemini (or template fallback)
- Updates PR body and marks as ready for review
- Cluster status automatically updates to "pr_opened" on success

Checklist:
- Ensure user is signed in with GitHub OAuth (required for all environments - local and production).
- User's GitHub token must have `repo` and `read:user` scopes (automatically granted during OAuth flow).
- For private repos or org repos: ensure user has write access to the repository.
- If org has SSO enabled: user must authorize the OAuth app for that organization in their GitHub settings.
- Ensure the repo URL is correct (the runner infers `github_repo_url` from feedback items; stale fallback URLs should not persist across runs).
