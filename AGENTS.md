# Repository Guidelines (agents + per-surface quickstart)

## Project Structure
- Backend (FastAPI ingestion + clustering glue) in `backend/` (`main.py`, `models.py`, `store.py`, `reddit_poller.py`, tests under `backend/tests/`).
- Dashboard (Next.js App Router) in `dashboard/` with API routes proxying/working directly against Redis + Upstash Vector (`lib/redis.ts`, `lib/vector.ts`, `lib/clustering.ts`).
- Coding Agent (CLI + ECS/Fargate task runner) in `coding-agent/`.
- Docs (PRD, CLAUDE, AGENTS) in repo root; architectural notes in `documentation/`.

## Backend (FastAPI)
- Install: `pip install -r backend/requirements.txt`.
- Run API locally: `uvicorn backend.main:app --reload` (from root) or `cd backend && uvicorn main:app --reload`.
- Deploy: Build path `./backend/`, start command `uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}`. Use `main:app` (not `backend.main:app`) when build/working dir is inside backend folder.
- Reddit poller: `python -m backend.reddit_poller` (respects `REDDIT_SUBREDDITS`, `REDDIT_SORTS`, `BACKEND_URL`).
- Storage: defaults to in-memory; set `REDIS_URL`/`UPSTASH_REDIS_URL` or `UPSTASH_REDIS_REST_URL`+`UPSTASH_REDIS_REST_TOKEN` to enable Redis/Upstash (key patterns in `documentation/db_design.md`).
- Tests: `pytest backend/tests -q --cov=backend`.

## Dashboard (Next.js)
- Install: `npm install --prefix dashboard`.
- Dev server: `npm run dev --prefix dashboard`.
- Lint/tests: `npm run lint --prefix dashboard`; `npm run test --prefix dashboard -- --runInBand`.
- Relies on Upstash Redis (`UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`) and Gemini for embeddings (`GEMINI_API_KEY`/`GOOGLE_GENERATIVE_AI_API_KEY`); cluster runs via `/api/clusters/run` using the vector + Redis helpers.
- GitHub OAuth via NextAuth: set `GITHUB_ID`, `GITHUB_SECRET`, `NEXTAUTH_URL`, `NEXTAUTH_SECRET`; uses optional `GITHUB_TOKEN` for higher API limits when syncing issues.

## Coding Agent (CLI + AWS task)
- Local: `uv run coding-agent/fix_issue.py <issue_url> [--job-id UUID]`. Requires `GH_TOKEN` (repo scope), `GIT_USER_EMAIL`, `GIT_USER_NAME`, and a provider key (`GEMINI_API_KEY` or `MINIMAX_API_KEY`); optional `BACKEND_URL`/`JOB_ID` to report status.
- Kilo is configured on the fly (~/.kilocode/cli/config.json) to use Gemini/Minimax; branch + PR are created in a fork (via gh CLI).
- Fargate path: Next.js `/api/trigger-agent` starts the ECS task defined by `ECS_CLUSTER_NAME`/`ECS_TASK_DEFINITION`, passing GitHub token and job/env overrides; AWS creds (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, subnet/SG IDs) must be set in the dashboard environment.

## Coding Style & Naming
- Backend: Black + Ruff (`black backend && ruff backend`), snake_case functions/modules, PascalCase Pydantic models, UPPER_SNAKE_CASE constants.
- Dashboard: ESLint/Prettier via `npm run lint --prefix dashboard`; React components in PascalCase; colocate Tailwind styling.

## Testing Expectations
- Add/adjust specs before implementation. Backend: `pytest backend/tests -q --cov=backend`. Dashboard: at least one Vitest/Playwright/Jest flow where feasible (`npm run test --prefix dashboard -- --runInBand`). If something can’t be automated, provide logs or screenshots in the PR.

## Commit & PR Hygiene
- Use Conventional Commits (`feat: …`, `fix: …`), subject <=72 chars, reference cluster IDs/GitHub issues when relevant. In PRs list commands run, link updated docs, include UI screenshots when applicable, and tag reviewers from both layers when changes cross backend/dashboard.

## Secrets & Config
- Secrets live only in `.env` (backend) and `.env.local` (dashboard). Do not commit tokens. Prefer `direnv`/`doppler run` for local loading. Point `GITHUB_REPO` at a sandbox when exercising the coding agent; confirm diffs locally before letting it open a production PR.

## Data Storage
- Redis plan and key patterns in `documentation/db_design.md`. Global Reddit list is stored at `config:reddit:subreddits` and exposed via `/config/reddit/subreddits` and the dashboard SourceConfig UI.
