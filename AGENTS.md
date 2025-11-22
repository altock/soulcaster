# Repository Guidelines

## Project Structure & Module Organization
Keep code grouped by layer so the “ears, brain, hands” loop stays readable. `backend/` hosts the FastAPI service for ingestion, triage, and code generation; place routers under `backend/app/api/`, clustering logic under `backend/app/services/`, and shared schemas inside `backend/app/models/`. Store automation helpers (e.g., candidate-file selectors, GitHub wrappers) under `backend/app/agents/` with unit tests mirroring the tree inside `backend/tests/`. The Next.js dashboard lives in `dashboard/` (App Router, Tailwind), while UI component stories and tests sit in `dashboard/__tests__/`. CLI scripts such as `reddit_poller.py` and seeding utilities belong in `scripts/`, and docs—including this guide, PRD.md, and CLAUDE.md—remain under `docs/`.

## Build, Test, and Development Commands
Backend: `pip install -r backend/requirements.txt` to install, `uvicorn backend.app.main:app --reload` to run APIs, and a separate `python scripts/reddit_poller.py` worker for Reddit polling. Frontend: `npm install --prefix dashboard`, `npm run dev --prefix dashboard` for local development, `npm run lint --prefix dashboard` before committing. Use `python -m scripts.seed_feedback` (once added) to load sample data so the dashboard has clusters to display.

## Coding Style & Naming Conventions
Follow Black-formatted, 4-space-indented Python with Ruff linting; run `black backend && ruff backend` before pushing. Modules, variables, and functions remain `snake_case`, data classes and Pydantic models stay `PascalCase`, and configuration constants are `UPPER_SNAKE_CASE`. Frontend code follows ESLint + Prettier defaults via `npm run lint`, keeps React components in `PascalCase`, and colocates CSS (or Tailwind) with components. Name feature branches `feedbackagent/{cluster-id}-{slug}` so automation can map PRs back to clusters.

## Testing Guidelines
The PRD calls for TDD even in hackathon mode: create or update a test before every backend change. Run `pytest backend/tests -q` for focused suites and enable coverage snapshots with `pytest --cov=backend/app --cov-report=term-missing` when touching triage logic. Frontend interactions should ship with at least one Vitest/RTL spec: `npm run test --prefix dashboard -- --watch`. Log manual validation steps (e.g., screenshot of a successful cluster-to-PR run) in your PR when automated coverage is not practical.

## Commit & Pull Request Guidelines
History currently only contains the “Initial commit,” so please adopt a Conventional Commits style (`feat:`, `fix:`, `chore:`) with <72-character subjects and actionable bodies describing the specific loop you touched. Every PR should include: summary bullet list, linked issue or cluster ID, screenshots or terminal output for dashboard/backend changes, and a checklist confirming `uvicorn` + dashboard dev server start without errors. Request a reviewer for both backend and frontend when a change crosses layers, and ensure GitHub tokens or subreddit details stay redacted in descriptions.

## Security & Configuration Tips
Never commit secrets. Copy `.env.example` to `.env` (backend) and `.env.local` (dashboard), then load them via `direnv` or `doppler run -- uvicorn ...`. GitHub personal access tokens require `repo` scope; Reddit credentials must stay in the `.env` files and should be rotated after every demo. When running agents locally, use sandbox repositories first, verify generated patches with `git diff`, and only point `GITHUB_REPO` at production once the flow has passed manual review.
