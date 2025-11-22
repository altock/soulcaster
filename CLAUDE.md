# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**FeedbackAgent** is a self-healing dev loop MVP built for a 24-hour hackathon. The system ingests bug reports from Reddit and Sentry, uses LLM-based triage to cluster feedback into issues, and automatically generates code fixes via a coding agent that opens GitHub PRs.

**Flow**: Reddit/Sentry → Clustered Issues → Human triage dashboard → One-Click Fix → GitHub PR

## Architecture

### Three-Layer System ("Ears, Brain, Hands")

1. **The Ears (Ingestion Layer)**
   - Python service with Reddit poller (PRAW) and Sentry webhook endpoint
   - Normalizes feedback into `FeedbackItem` schema
   - In-memory storage (Python dicts) for MVP - no database

2. **The Brain (Triage + Coding Agents)**
   - Triage: Embedding-based clustering with cosine similarity (threshold: 0.8-0.85)
   - LLM generates cluster summaries
   - Coding Agent: Selects candidate files, generates patches, opens PRs

3. **The Hands (Execution)**
   - PyGithub integration for branch creation, commits, and PR opening
   - Syntax validation for Python files only (MVP scope)

### Tech Stack

**Backend (Python)**
- FastAPI for HTTP server
- PRAW for Reddit polling
- PyGithub for GitHub integration
- LiteLLM (optional) for model abstraction
- In-memory storage: `feedback_items` and `issue_clusters` dicts

**Frontend (Next.js)**
- App Router on Vercel
- Tailwind CSS (shadcn/ui optional)
- Polls backend for cluster status updates

**LLM Strategy**
- Fast/cheap model (e.g., Gemini Flash) for embeddings & summaries
- Stronger model (e.g., Claude Sonnet) for code generation

## Development Commands

### Backend (Python/FastAPI)

Currently not implemented. When implementing:

```bash
# Install dependencies
pip install -r requirements.txt  # or poetry install

# Run FastAPI server
uvicorn app.main:app --reload

# Run Reddit poller (separate process)
python scripts/reddit_poller.py

# Run tests (TDD approach per PRD)
pytest

# Run single test file
pytest tests/test_clustering.py -v
```

### Frontend (Next.js)

Currently not implemented. When implementing:

```bash
# Install dependencies
npm install  # or pnpm install

# Run development server
npm run dev

# Build for production
npm run build

# Run production build
npm start

# Lint
npm run lint
```

## Key Data Models

### FeedbackItem
- `id`: UUID
- `source`: "reddit" | "sentry"
- `external_id`: Original source ID
- `title`: Post title or truncated comment
- `body`: Full text content
- `metadata`: JSON (subreddit, permalink, stack frames, etc.)
- `created_at`: Timestamp
- `embedding`: Vector representation

### IssueCluster
- `id`: UUID
- `title`: LLM-generated (≤80 chars)
- `summary`: LLM-generated (≤300 chars)
- `feedback_ids`: List of associated FeedbackItem IDs
- `status`: "new" | "fixing" | "pr_opened" | "failed"
- `created_at`, `updated_at`: Timestamps
- `embedding_centroid`: Mean of member embeddings
- `github_branch`: Optional branch name
- `github_pr_url`: Optional PR URL
- `error_message`: Optional failure details

## API Endpoints

### Ingestion
- `POST /ingest/reddit` - Receive normalized Reddit feedback
- `POST /ingest/sentry` - Receive Sentry webhook events

### Clusters
- `GET /clusters` - List all clusters with summary info
- `GET /clusters/{id}` - Get cluster details with sample feedback
- `POST /clusters/{id}/start_fix` - Trigger coding agent for cluster

### Frontend API Routes (Next.js)
- `GET /api/clusters` → proxies to backend `/clusters`
- `GET /api/clusters/[id]` → proxies to backend `/clusters/{id}`
- `POST /api/clusters/[id]/start_fix` → proxies to backend `/clusters/{id}/start_fix`

## Critical Implementation Details

### Clustering Logic
1. Compute embedding for new feedback (`title + body`)
2. Compare to all cluster centroids using cosine similarity
3. If similarity ≥ 0.8-0.85: add to existing cluster and update centroid
4. Else: create new cluster with this single feedback
5. Generate/update LLM summary using up to 5 sample feedback items

### Candidate File Selection (Coding Agent)
1. **From Sentry feedback**: Extract filenames from stack traces, match against repo paths
2. **From text**: Extract keywords from cluster title, match file paths (case-insensitive)
3. **Limit**: Max 3-5 files, max 10k chars per file
4. **Fallback**: Send truncated file list to LLM for selection

### Patch Generation
- Prompt includes: cluster summary, feedback snippets, candidate file contents
- LLM returns JSON: `{files: [{path, updated_content}], summary}`
- Full-file replacement (no diff parsing in MVP)
- Python syntax check via `ast.parse()` before creating PR

### PR Creation Flow
1. Branch name: `feedbackagent/cluster-{id}-{slugified-title}`
2. For each file: fetch current SHA, update/create file on new branch
3. PR title: `Fix: {cluster.title}`
4. PR body includes: LLM summary, cluster summary, feedback source links, auto-generation notice
5. Update cluster: `status="pr_opened"`, set `github_branch` and `github_pr_url`

## Environment Variables (To Be Configured)

```bash
# Reddit API
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=
REDDIT_SUBREDDITS=  # Comma-separated

# GitHub
GITHUB_TOKEN=  # Personal access token with repo scope
GITHUB_REPO=  # Format: "owner/repo"
BASE_BRANCH=main  # Target branch for PRs

# LLM Provider(s)
OPENAI_API_KEY=  # or other provider keys
ANTHROPIC_API_KEY=

# Backend
BACKEND_URL=http://localhost:8000  # For frontend to call
```

## Scope Guardrails (MVP Only)

**What we ARE building:**
- Single target repo
- Happy-path only
- Functional code over robustness
- Test-driven development (TDD)
- In-memory storage

**What we are NOT building:**
- No auth/permissions (hardcoded env vars only)
- No multi-repo support
- No historical backfill
- No robust retries/rate limiting
- No chat UI (click-to-fix only)
- No comprehensive test suite (manual verification)

## Known Limitations

- Python-only syntax validation (no TypeScript, Go, etc.)
- No tests run by coding agent (just syntax check)
- Full-file replacement (can break large files)
- No RAG or codebase indexing
- No automatic PR merge or cluster closure
- Single-threaded background tasks (no queue system)

## Testing Strategy

Per PRD: Test-Driven Development (TDD) approach

When implementing, write tests for:
- Clustering logic (similarity thresholds, centroid updates)
- FeedbackItem normalization (Reddit/Sentry)
- Candidate file selection heuristics
- LLM response parsing
- GitHub API interactions (use mocks)

## Post-Hackathon Future Work

**DO NOT implement these during MVP:**
- Replace in-memory storage with Supabase/Postgres
- Add Redis for queues and caching
- GitHub Actions pipeline for running tests before PR
- Multi-language syntax validation
- Cluster merge/split UI controls
- RAG over codebase
- GitHub OAuth and multi-repo support
- Comprehensive observability and rate limiting
