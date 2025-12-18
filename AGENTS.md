# Repository Guidelines (agents + per-surface quickstart)

## Project Structure
- Backend (FastAPI ingestion + clustering + agent orchestration) in `backend/` (`main.py`, `store.py`, `models.py`, `clustering*.py`, `planner.py`, `agent_runner/`, `e2b_template/`, tests under `backend/tests/`).
- Dashboard (Next.js App Router) in `dashboard/` with pages + API routes in `app/`, Prisma schema in `prisma/`, and shared helpers in `lib/` (`auth.ts`, `prisma.ts`, `project.ts`, `github.ts`, `vector.ts`, `clustering.ts`).
- Coding agent artifacts in `coding-agent/` (`fix_issue.py`, `Dockerfile`, `terraform/` and `FARGATE_DEPLOYMENT.md` for legacy ECS/Fargate).
- Docs: repo root (`README.md`, `AGENTS.md`, `CLAUDE.md`), design notes in `docs/`, architecture + db design in `documentation/`, and roadmap notes in `tasks/`.

## Backend (FastAPI)
- Install: `pip install -r backend/requirements.txt`.
- Run API locally: `uvicorn backend.main:app --reload` (from root) or `cd backend && uvicorn main:app --reload`.
- Clustering jobs: backend-owned async runner via `POST /cluster-jobs` + `GET /clustering/status`.
- Deploy: Build path `./backend/`, start command `uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}`. Use `main:app` (not `backend.main:app`) when build/working dir is inside backend folder.
- Reddit poller (optional): `python -m backend.reddit_poller` (uses public JSON; respects `REDDIT_SUBREDDITS`, `REDDIT_SORTS`, `BACKEND_URL`).
- Storage: defaults to in-memory; set `REDIS_URL`/`UPSTASH_REDIS_URL` or `UPSTASH_REDIS_REST_URL`+`UPSTASH_REDIS_REST_TOKEN` to enable Redis/Upstash (key patterns in `documentation/db_design.md`).
- Tests: `pytest backend/tests -q --cov=backend`.

## Dashboard (Next.js)
- Install: `npm install --prefix dashboard`.
- Dev server: `npm run dev --prefix dashboard`.
- DB setup (Prisma): `cd dashboard && npx prisma migrate dev`.
- Lint/tests: `npm run lint --prefix dashboard`; `npm run test --prefix dashboard`; `npm run type-check --prefix dashboard`.
- Data: Upstash Redis + Upstash Vector (`UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`, `UPSTASH_VECTOR_REST_URL`, `UPSTASH_VECTOR_REST_TOKEN`) plus `BACKEND_URL` for backend APIs/proxies.
- GitHub OAuth via NextAuth: set `GITHUB_ID`, `GITHUB_SECRET`, `NEXTAUTH_URL`, `NEXTAUTH_SECRET` and `DATABASE_URL`; GitHub API calls use the per-user OAuth token from the session.
- Dashboard-triggered clustering routes (`/api/clusters/run*`) return 410s unless `ENABLE_DASHBOARD_CLUSTERING=true` is explicitly set for local testing; use backend `/cluster-jobs*` + `/clustering/status` via `/api/clusters/jobs`.

## Coding Agent (E2B sandbox)
- Primary path: backend `POST /clusters/{id}/start_fix` selects `CODING_AGENT_RUNNER` (default: `sandbox_kilo`) and streams logs back via jobs (`/jobs`).
- `sandbox_kilo` requires `E2B_API_KEY`, `KILOCODE_TEMPLATE_NAME` (or `KILOCODE_TEMPLATE_ID`) and provider creds for Kilocode (e.g. `GEMINI_API_KEY`); GitHub auth comes from `X-GitHub-Token` header or falls back to `GITHUB_TOKEN`.
- Known edge case: a run can push a branch successfully but fail to return a PR URL (e.g., `gh pr create` fails and the fallback `gh pr list --head <branch>` returns no URL), so a PR may need to be opened manually from the pushed branch.

## Coding Agent (ECS/Fargate) (deprecated)
- The legacy ECS/Fargate trigger route is kept only for manual/testing scenarios (`dashboard/app/api/trigger-agent/route.ts` + `coding-agent/terraform/`) and should not be used as the default path.

## Coding Style & Naming
- Backend: Black + Ruff where available (`black backend && ruff backend`), snake_case functions/modules, PascalCase Pydantic models, UPPER_SNAKE_CASE constants.
- Dashboard: ESLint/Prettier via `npm run lint --prefix dashboard` / `npm run format --prefix dashboard`; React components in PascalCase; colocate Tailwind styling.

## Testing Expectations
- Add/adjust specs before implementation. Backend: `pytest backend/tests -q --cov=backend`. Dashboard: `npm run test --prefix dashboard` (Jest). If something can’t be automated, provide logs or screenshots in the PR.

## Commit & PR Hygiene
- Use Conventional Commits (`feat: …`, `fix: …`), subject <=72 chars, reference cluster IDs/GitHub issues when relevant. In PRs list commands run, link updated docs, include UI screenshots when applicable, and tag reviewers from both layers when changes cross backend/dashboard.

## Secrets & Config
- Secrets live only in `.env` (backend) and `.env.local` (dashboard). Do not commit tokens. Prefer `direnv`/`doppler run` for local loading. Point `GITHUB_REPO` at a sandbox when exercising the coding agent; confirm diffs locally before letting it open a production PR.

## Data Storage
- Redis plan and key patterns in `documentation/db_design.md`. Reddit subreddit lists are project-scoped at `config:reddit:subreddits:{project_id}` and exposed via backend `/config/reddit/subreddits?project_id=...` (dashboard proxies via `/api/config/reddit/subreddits`).
