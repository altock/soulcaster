# FeedbackAgent MVP Todos

## Shared Setup & Decisions
- [x] Confirm target GitHub repo and base branch @Sam @Shared  
- [~] Choose LLM provider(s) & models (Embeddings, Summarization, Code-gen) @Sam @LLM  
  _Partially done – Gemini is chosen and wired for embeddings + clustering and the coding agent; summarization/code‑gen prompts are still evolving._
- [~] Generate GitHub token with repo access and set env vars @Sam @Backend  
  _Partially done – flows assume `GITHUB_ID`/`GITHUB_SECRET`/`GH_TOKEN` and work locally/in cloud, but this is not fully productized or documented as a one‑time setup task._
- [~] Create .env.example for backend @Sam @Shared  
  _Partially done – env usage is documented in README/PRD, but there is no dedicated backend `.env.example` file checked in._
- [x] Decide on DB (In-memory/Redis selected) @Sam @Backend  

## Backend (Sam)
### Core & Ingestion
- [x] Scaffold FastAPI app @Sam @Backend  
- [x] Define data models (FeedbackItem, IssueCluster) @Sam @Backend  
- [x] Implement in-memory/Redis store @Sam @Backend  
- [x] Implement /ingest/reddit endpoint @Sam @Backend  
- [x] Implement /ingest/sentry endpoint @Sam @Backend  
- [x] Normalize Sentry payloads @Sam @Backend  
- [x] Implement GET /clusters @Sam @Backend  
- [x] Implement GET /clusters/{id} @Sam @Backend  
- [x] Implement POST /clusters/{id}/start_fix (Stub) @Sam @Backend  
- [x] Implement Reddit poller (JSON-based) @Sam @Backend  
- [x] Hook Reddit poller to /ingest/reddit @Sam @Backend  
- [x] Add logging for Reddit poller @Sam @Backend  

### Intelligence & Agents (Frontend/Serverless)
- [x] Add LLM dependencies (xenova/transformers) @Colleague @Frontend  
- [x] Implement EmbeddingClient wrapper (clustering.ts) @Colleague @Frontend  
- [~] Implement LLMClient wrapper (summarize, propose_fix, choose_files) @Sam @Backend @LLM  
  _Partially done – summarization is implemented in `dashboard/lib/clustering.ts` for clusters; there is no unified cross-service “LLMClient” abstraction yet._
- [x] Implement clustering logic (Embeddings + Cosine Similarity) @Colleague @Frontend  
- [x] Implement triage worker (Process FeedbackItems -> IssueClusters) @Colleague @Frontend  
- [x] Add embedding computation for new feedback on ingest @Colleague @Frontend  
- [~] Implement LLM summarization for new IssueClusters @Sam @Backend @LLM  
  _Partially done – Gemini-based summarization for clusters exists in TS; backend does not yet perform LLM summarization itself._
- [x] Store cluster embedding_centroid @Colleague @Frontend  
 

### Coding Agent (External AWS Service)
- [~] Obtain AWS Agent API endpoint and credentials @Sam @Backend  
  _Partially done – ECS task definition, AWS creds, and trigger route exist; this is wired for the current Fargate-based coding agent but not yet generalized as a reusable “Agent API”._
- [~] Implement AgentClient wrapper (send prompt -> receive PR URL) @Sam @Backend  
  _Partially done – `/api/trigger-agent` plus `coding-agent/fix_issue.py` together form the agent client; there is no single small wrapper class, but end-to-end PR creation works._
- [~] Update /clusters/{id}/start_fix to call AgentClient @Sam @Backend  
  _Partially done – dashboard `/api/clusters/[id]/start_fix` calls `/api/trigger-agent` and then backend `/clusters/{id}/start_fix`; the backend endpoint itself remains a simple status-flip stub._
- [x] Implement Job tracking API (POST/PATCH /jobs) @Sam @Backend  
  _Done – `/jobs` and `/jobs/{id}` exist and are used by the coding agent for status/log updates._
- [~] Update IssueCluster with PR URL from Agent response @Sam @Backend  
  _Partially done – the agent and dashboard propagate PR URLs into cluster records, but this is not yet consistently enforced across all paths._
- [~] Add logging for Agent API calls @Sam @Backend  
  _Partially done – there is logging in `/api/trigger-agent` and the coding agent, but no centralized structured logging/monitoring for all agent invocations._

### Deprecated / Handled by AWS Agent
- [x] Integrate PyGithub and connect to repo (Handled by AWS Agent)
- [x] Fetch and cache repo file tree (Handled by AWS Agent)
- [x] Implement candidate file selection (Handled by AWS Agent)
- [x] Implement coding agent pipeline (Handled by AWS Agent)
- [x] Implement Python syntax check (Handled by AWS Agent)
- [x] Implement branch creation via PyGithub (Handled by AWS Agent)
- [x] Implement file updates via PyGithub (Handled by AWS Agent)
- [x] Implement PR creation via PyGithub (Handled by AWS Agent)

## Frontend (Colleague)
- [x] Scaffold Next.js app @Colleague @Frontend  
- [x] Set up basic styling @Colleague @Frontend @UI  
- [x] Implement /api/clusters proxy @Colleague @Frontend  
- [x] Implement /api/clusters/[id] proxy @Colleague @Frontend  
- [x] Implement /api/clusters/[id]/start_fix proxy @Colleague @Frontend  
- [x] Wire clusters list page to live data @Colleague @Frontend  
- [x] Wire cluster detail page to live data @Colleague @Frontend  
- [x] Add "Generate Fix" button @Colleague @Frontend @UI  
- [~] Implement polling of cluster detail after Generate Fix @Colleague @Frontend  
  _Partially done – current UI refreshes state on demand; there is no continuous polling loop yet._
- [x] Display status badges (new, fixing, pr_opened, failed) @Colleague @Frontend @UI  
- [~] Display PR link when available @Colleague @Frontend @UI  
  _Partially done – PR URLs are surfaced where available, but not every view consistently shows them._
- [~] Display error message if failed @Colleague @Frontend @UI  
  _Partially done – agent errors surface through logs and some UI states, but there isn’t yet a dedicated “cluster failed” error component._
- [~] Add Reddit vs Sentry source badges @Colleague @Frontend @UI  
  _Partially done – sources (reddit/manual/github) are visible in several components, but there are no dedicated per-source icon badges in all views._

## Prompts & Instructions
- [~] Define triage summarization prompt @Sam @LLM  
  _Partially done – summarization prompts exist in TS clustering utilities; they are not yet formalized as a single shared spec._
- [~] Define coding agent patch-generation prompt @Sam @LLM  
  _Partially done – Kilo/coding-agent prompt flows are defined in the agent code and PRD, but there is no central prompt doc here._
- [~] Define fallback prompt for file selection @Sam @LLM  
  _Partially done – fallback behavior is encoded in the coding agent prompt, but not broken out as a reusable prompt asset._
- [~] Add README note text for auto-generated PRs @Sam  
  _Partially done – high-level behavior is documented in `README.md`/`PRD.md`, but there is no explicit “auto-generated PR notice” template._

## Testing & Demo
- [x] Create sample feedback fixtures (seed_mock_data in main.py) @Sam @Backend  
 
- [~] Create sample Sentry webhook fixture/curl script @Sam @Backend  
  _Partially done – tests contain sample webhook payloads; a standalone curl script is not yet checked in._
- [~] Run end-to-end test @Sam @Colleague  
  _Partially done – manual end-to-end flows have been exercised; there is no single automated E2E test script._
- [~] Capture repo/PR URL examples @Sam  
  _Partially done – PR examples exist in practice and in docs, but not curated in a single reference section._
- [~] Rehearse demo narrative @Sam @Colleague  
  _Partially done – the narrative is reflected in `PRD.md` and docs, but this checklist item was not rigorously kept in sync._
