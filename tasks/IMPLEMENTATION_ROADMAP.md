# Implementation Roadmap

High-level phases for Soulcaster delivery. Phase 5.1 introduces the backend-first coding-agent planner + sandbox runner while the original AWS agent path (Phase 5) remains deferred/optional.

| Phase | Status | Summary |
| --- | --- | --- |
| Phase 1 | ✅ | Data ingestion + FastAPI plumbing (`tasks/data_ingestion.md`) |
| Phase 2 | ✅ | Dashboard scaffolding + API integrations (`tasks/dashboard_integration.md`) |
| Phase 3 | ✅ | Clustering, summaries, and triage UX |
| Phase 4 | ✅ | Job tracking primitives + legacy coding-agent hook |
| Phase 5 | ⏸️ Deferred | Dashboard `/api/trigger-agent` → AWS/ECS runner that required GitHub issues |
| Phase 5.1 | 🚧 WIP | Cluster coding plan + unified `/clusters/{id}/start_fix` orchestrator (default e2b/Kilocode runner, swappable registry, draft PR output) |

## Phase 5 – AWS Coding Agent (Deferred)
- Dashboard `/api/trigger-agent` triggers ECS/Fargate to run `coding-agent/fix_issue.py`, then backend `/clusters/{id}/start_fix` just flips status.
- Runs depended on creating/validating a GitHub issue per fix request.
- Status: kept for manual/testing scenarios (set `CODING_AGENT_RUNNER=aws_kilo`), but not the default path once Phase 5.1 lands.

## Phase 5.1 – Cluster Coding Plan & Sandbox Runner (WIP)
- Objective: when a user opens a cluster they see a generated high-level plan (summary, hypotheses, candidate files, validation steps) and can trigger a fix directly via backend `/clusters/{id}/start_fix`.
- Runner strategy: backend selects a runner (`CODING_AGENT_RUNNER`, default `sandbox_kilo`) from a registry. Default runner spins up an e2b sandbox, runs Kilocode, and opens a **branch + draft PR** (no GitHub issue). Legacy AWS runner stays opt-in for parity.
- Dashboard integration: `/app/api/clusters/[id]/start_fix` simply proxies to backend; legacy `/api/trigger-agent` remains for manual AWS triggers.
- Implementation reference: `tasks/coding_agent_plan.md` (combined plan + strategy with Kilocode/e2b doc links).
- Expected flow:
  1. Cluster opens → backend (or user) generates plan via `/clusters/{id}/plan`.
  2. User reviews/edits plan → clicks "Generate fix".
  3. Backend `/clusters/{id}/start_fix` creates job, selects runner, and dispatches to sandbox/provider.
  4. Runner streams logs, runs tests, and posts a draft PR; backend updates `/jobs` + cluster metadata.
- Status: WIP until planner, orchestrator, and sandbox runner are implemented; AWS runner remains behind `CODING_AGENT_RUNNER=aws_kilo`.

## Documentation Links
- Coding agent plan & strategy: `tasks/coding_agent_plan.md`
- Data model background: `documentation/db_design.md`
