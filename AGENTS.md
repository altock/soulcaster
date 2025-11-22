# Repository Guidelines

## Project Structure & Module Organization
Source is split by layer: `backend/` houses the FastAPI ingestion, triage, and coding-agent services with routers in `app/api/`, clustering logic in `app/services/`, and shared schemas in `app/models/`. Unit tests mirror the service tree under `backend/tests/`. The Next.js dashboard lives in `dashboard/` with UI specs in `dashboard/__tests__/`. CLI utilities such as `reddit_poller.py` go in `scripts/`, while docs (PRD, CLAUDE, AGENTS) stay in `docs/`.

## Build, Test, and Development Commands
Install backend deps with `pip install -r backend/requirements.txt`, run the API via `uvicorn backend.app.main:app --reload`, and start Reddit ingestion separately through `python scripts/reddit_poller.py`. Frontend work begins with `npm install --prefix dashboard`; `npm run dev --prefix dashboard` launches the dashboard and `npm run lint --prefix dashboard` enforces lint. Seed fixtures through `python scripts/seed_feedback.py` (or equivalent) so the UI can exercise cluster flows.

## Coding Style & Naming Conventions
Python code follows Black-formatted four-space indentation plus Ruff linting; run `black backend && ruff backend` before every push. Use `snake_case` for modules and functions, `PascalCase` for Pydantic models, and `UPPER_SNAKE_CASE` for configuration constants. React/Next components stay in `PascalCase`, colocate Tailwind styling, and rely on ESLint + Prettier rules invoked through `npm run lint`.

## Testing Guidelines
Lean into the PRD’s TDD guardrail: add or update a spec first, then implement. Execute backend coverage with `pytest backend/tests -q --cov=backend/app` and mention intentionally skipped cases in the PR. Dashboard flows should gain at least one Vitest or Playwright check: `npm run test --prefix dashboard -- --runInBand`. When automation cannot cover a scenario, drop screenshots or logs into the PR description.

## Commit & Pull Request Guidelines
Git history currently holds only the “Initial commit,” so adopt Conventional Commits going forward (`feat: cluster triage summary`, `fix: sentry webhook parsing`). Keep subject lines under 72 characters, add imperative detail in the body, and reference cluster IDs or GitHub issues. Every PR should list the commands you ran, link updated docs, provide screenshots for UI work, and tag reviewers from both layers when the change crosses backend and dashboard boundaries.

## Security & Configuration Tips
Store secrets only in `.env` (backend) and `.env.local` (dashboard); never commit tokens. Load them with `direnv` or `doppler run` so `GITHUB_TOKEN`, Reddit credentials, and LLM keys stay out of shell history. Point `GITHUB_REPO` at a sandbox repo while testing the coding agent and confirm diffs locally (`git diff`) before letting it open a production PR.
