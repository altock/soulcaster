# Coding Agent & Sandbox Architecture — Soulcaster vs. E2B Pattern

This document compares the current Soulcaster coding agent architecture with:

- The E2B/OpenAI coding agent pattern from the deeplearning.ai materials (in `temp/projects/docs.md`)
- Recent patterns from GitHub Copilot’s coding agent, Claude Code, and VS Code’s agent guidance

and proposes a modular, security‑aware architecture that supports:

- **Our current “GitHub + Kilo + ECS task” agent**
- **An “LLM + tool-calling” agent that treats each ECS task as the coding sandbox**
- **Optional future support for remote sandboxes (E2B-style) behind the same interface**

The goal is to preserve what already works for GitHub issue fixing, while moving toward the industry-standard “LLM + tools + per-job sandbox” pattern with clear security and isolation guarantees.

---

## 1. Today’s Soulcaster Coding Agent Architecture

### 1.1 High-level flow

```mermaid
sequenceDiagram
    participant User
    participant Dashboard
    participant Backend
    participant ECS as ECS/Fargate
    participant Kilo as Kilo CLI
    participant GitHub
    
    User->>Dashboard: Click "Generate Fix"
    Dashboard->>Backend: POST /jobs
    Dashboard->>ECS: RunTaskCommand
    
    ECS->>GitHub: gh auth & fork repo
    ECS->>Kilo: kilocode --auto <prompt>
    Kilo->>Kilo: Analyze & edit code
    ECS->>GitHub: Commit & push branch
    ECS->>GitHub: gh pr create
    ECS->>Backend: PATCH /jobs (status, pr_url)
    
    Dashboard->>Backend: Poll job status
    Backend-->>Dashboard: Job complete + PR URL
    Dashboard-->>User: Show PR link
```

**User → Dashboard → Backend → ECS/Fargate → GitHub PR**

- User clicks **“Generate Fix”** on a cluster in the dashboard.
- Dashboard:
  - Creates a job in the backend (`POST /jobs`).
  - Triggers `RunTaskCommand` on ECS (`/api/trigger-agent`) with:
    - `issue_url`
    - `JOB_ID`
    - `BACKEND_URL`
    - `GH_TOKEN`, `GIT_USER_NAME`, `GIT_USER_EMAIL`, provider keys, etc.
- ECS runs the `coding-agent` container whose entrypoint is:
  - `uv run fix_issue.py <issue_url> [--job-id UUID]`
- `fix_issue.py`:
  - Configures Kilo CLI (`~/.kilocode/cli/config.json`) with Gemini or Minimax.
  - Uses `gh` CLI to:
    - Determine the authenticated GitHub user.
    - Ensure a fork of the target repo exists (unique `aie-fork-{repo}-{suffix}` name).
    - Clone the fork into a temporary directory.
    - Add `upstream` remote pointing at the original repo.
  - Configures Git (`user.name`, `user.email`, `credential.helper` using `GH_TOKEN`).
  - Creates a feature branch for the issue.
  - Runs `kilocode --auto "<prompt>"` in the repo directory to generate fixes.
  - If changes exist:
    - Commits with a standard `Fix issue #<n>` message.
    - Pushes to the forked repo.
    - Opens a PR against the upstream default branch using `gh pr create`.
  - Throughout the process, calls `update_job(job_id, status, logs, pr_url)` to patch the backend job status (`pending` → `running` → `success`/`failed`).

### 1.2 Execution + sandbox model (today)

```mermaid
graph TB
    subgraph "ECS/Fargate Task (Sandbox Boundary)"
        Container[Docker Container]
        FS[Ephemeral Filesystem<br/>/tmp workspace]
        Kilo[Kilo CLI Agent]
        Git[Git + gh CLI]
        
        Container --> FS
        Container --> Kilo
        Container --> Git
    end
    
    subgraph "External Services"
        GitHub[GitHub<br/>Fork & PR]
        Backend[Backend<br/>Job Status]
        Provider[Gemini/Minimax<br/>via Kilo]
    end
    
    Git <-->|GH_TOKEN| GitHub
    Kilo -->|API calls| Provider
    Container -->|Update job| Backend
    
    style Container fill:#e8f5e9
    style FS fill:#fff4e1
    style Kilo fill:#ffe1f5
    style Git fill:#e1f5ff
```

**Sandbox boundary: ECS task + GitHub fork**

- **Isolation unit**: the ECS/Fargate task running our Docker image.
  - The task has its own container filesystem and ephemeral `/tmp` workspace.
  - It talks to:
    - GitHub (via `gh` + `GH_TOKEN`).
    - Backend (`BACKEND_URL`).
    - (Optionally) providers like Gemini/Minimax via Kilo CLI.
- **“Sandbox” here is at the infrastructure level** (Docker/ECS), not a programmatic, per-request code execution sandbox like E2B.
- All code editing happens indirectly via **Kilo CLI**, which:
  - Drives its own inner loop (agent, tools, MCP, etc.) that we do not control.
  - Has its own auto-approval / allowlist system (we set this via `config.json`).
- We don’t call an LLM directly from Soulcaster; Kilo is the abstraction layer.

### 1.3 Strengths & trade-offs

**Strengths**
- Leverages Kilo’s mature coding agent:
  - Multi-language, multi-file editing.
  - Deep repo understanding and MCP ecosystem.
- GitHub workflow is fully automated:
  - Fork creation, branch naming, PR creation.
- Operational model is well-aligned with AWS ECS / Fargate:
  - Each job is a container task.
  - Backend has a simple job state machine.

**Trade-offs / Limitations**
- **LLM + tool loop is opaque**:
  - We don’t own the inner agent; we can’t easily modify tool schemas, add custom tools, or inspect intermediate reasoning.
- **No fine-grained code sandbox**:
  - Execution happens in the repo directly via `kilocode` and `gh`, not in an explicit “code interpreter” sandbox like E2B.
  - Harder to do safe experimentation, partial changes, or rich notebook-style workflows.
- **Tight coupling to GitHub issues and Kilo**:
  - Agent is strongly focused on “take issue URL, fix repo, open PR”.
  - Harder to extend to generic “coding agent sessions”, notebooks, or ad-hoc sandbox tasks.

---

## 2. Industry reference patterns (Copilot, Claude Code, E2B)

This section summarizes how modern cloud coding agents handle orchestration, sandboxes, and security. It does **not** change what Soulcaster does today; it provides reference points for where we’re heading.

### 2.1 GitHub Copilot coding agent

- Lives inside GitHub’s world:
  - Operates on a single repository where it’s assigned.
  - Only available to users with appropriate repo permissions.
  - Can now run dev environments on self-hosted Actions runners, which means ephemeral, isolated workspaces on the customer’s infrastructure while Copilot controls the agent logic.
- Security / isolation characteristics:
  - One task → one isolated runner workspace (no reuse across repos).
  - Access is scoped to that repo and its GitHub token.
  - GitHub’s “agentic security principles” call out:
    - Preventing data exfiltration.
    - Respecting permissions / impersonation boundaries.
    - Controlling resource usage and abuse.

### 2.2 Claude Code

- Local (VS Code / terminal) mode:
  - Access is scoped to the folder where you start Claude Code and its subfolders.
  - Uses an explicit permission model:
    - Read-only by default.
    - Requests approval for edits, tests, and shell commands.
    - Org-level policies can auto-approve certain operations to avoid fatigue.
- Web / cloud mode:
  - Runs in Anthropic-managed, isolated VMs per session.
  - Uses a credential proxy so a scoped GitHub credential in the VM maps to the user’s actual GitHub permissions without exposing raw tokens to the model.
  - Network is constrained; only necessary endpoints are reachable.

### 2.3 E2B / deeplearning.ai coding agent pattern

Source: `temp/projects/docs.md`.

#### Core abstractions

The lesson proposes a **composable, LLM-first agent loop** with:

- **LLM client** (`OpenAI`):
  - Called with `client.responses.create(...)`, passing:
    - A **developer/system message** with behavior and tool usage instructions.
    - A list of **messages** (user, agent, tool outputs).
    - A list of **tool schemas** (functions with JSON schemas).
- **Tools**:
  - Python callables with JSON-serializable inputs/outputs.
  - Example tools: `execute_code`, `read_file`, `write_file`.
  - A helper `execute_tool(name, args_json, tools)` handles:
    - JSON parsing and error handling.
    - Routing calls to the correct function.
#### Sandbox model

- `coding_agent` loop:
  - Calls the LLM with current messages + tool schemas.
  - For each `function_call` in output:
    - Executes the corresponding Python tool.
    - Appends a `function_call_output` message with `call_id` and JSON output.
  - Stops when:
    - There are no more function calls, or
    - `max_steps` is reached.

- E2B `Sandbox`:
  - Remote, time-bounded environment (`Sandbox.create(timeout=3600)`).
  - Supports `run_code` in different languages (`python`, `javascript`, `bash`).
  - Has file APIs:
    - `sbx.files.write`, `sbx.files.read`, `sbx.files.make_dir`, `sbx.files.remove`.
  - Can be queried/filtered with metadata, reconnected via `Sandbox.connect`, and killed.

- `coding_agent_sandbox`:
  - Same agent loop, but tools receive `sbx` as an extra argument and call `sbx.run_code`.
  - Tools return `(result_json, metadata)`; metadata can include images.

#### Characteristics

**Strengths**
- Architecturally simple and composable:
  - Explicit tool schemas and implementations.
  - Clear agent loop and message history.
- First-class sandbox:
  - Per-session remote environment with strict timeout and lifecycle.
  - Great for safe code execution, notebooks, and exploratory workflows.
- Easy to extend:
  - Add new tools (e.g., repo manipulation, test running, HTTP calls) by defining schemas + functions.

**Trade-offs**
- GitHub workflow is not built-in:
  - You must design tools for `git`/GitHub operations (clone, branch, PR).
- Some responsibilities shift to you:
  - Designing prompts, tools, and safety/guardrails.
  - Managing sandbox lifecycle and cost.

---

## 3. Side‑by‑side comparison

```mermaid
graph TB
    subgraph "Soulcaster (Current)"
        SC1[Dashboard + Backend<br/>orchestrate ECS tasks]
        SC2[Kilo CLI<br/>drives code changes]
        SC3[Container-level<br/>isolation per job]
        SC1 --> SC2
        SC2 --> SC3
    end
    
    subgraph "E2B Pattern"
        E1[Python orchestrates<br/>LLM + tool calls]
        E2[Tools operate on<br/>Sandbox object]
        E3[Per-session remote<br/>sandbox with timeout]
        E1 --> E2
        E2 --> E3
    end
    
    SC1 -.->|Control Plane| Control[Control Plane]
    E1 -.->|Control Plane| Control
    
    SC2 -.->|Data Plane| Data[Data Plane]
    E2 -.->|Data Plane| Data
    
    style SC1 fill:#e1f5ff
    style SC2 fill:#ffe1f5
    style SC3 fill:#e8f5e9
    style E1 fill:#e1f5ff
    style E2 fill:#ffe1f5
    style E3 fill:#e8f5e9
```

### 3.1 Control plane vs. data plane (today)

- **Soulcaster today**
  - Control plane:
    - Dashboard + backend orchestrate **ECS tasks** and job states.
  - Data plane:
    - Kilo CLI drives code changes inside the repo.
    - Our code doesn’t manage individual tool calls or execution steps.

- **E2B pattern**
  - Control plane:
    - Python process orchestrates **LLM responses + tool calls** explicitly.
  - Data plane:
    - Tools operate either on:
      - Local process state, or
      - A sandbox (`Sandbox`) that encapsulates file system and code execution.

### 3.2 Sandbox / isolation

- **Soulcaster**
  - Isolation: container-level (ECS task) per job.
  - Primary side effects: git operations in a forked repo, network calls to GitHub/backend/providers.
  - No “inner sandbox” – the code agent (Kilo) operates directly on the repo workspace in the container.

- **E2B**
  - Isolation: explicit sandbox object per session.
  - Tools operate **within** sandbox (files, code execution, environment).
  - Easier to reason about per-session resources and kill/timeout behavior.

### 3.3 Agent composition

- **Soulcaster**
  - Agent = Kilo CLI (external).
  - We configure:
    - Provider (Gemini/Minimax).
    - Auto-approval rules / allow/deny command lists.
  - Kilo decides which tools to call, how to edit files, etc.

- **E2B**
  - Agent loop is in our code (`coding_agent` / `coding_agent_sandbox`).
  - We design:
    - System instructions.
    - Tools and schemas.
    - Step limits and safety behavior.

### 3.4 GitHub workflow

- **Soulcaster**
  - Fully-baked GitHub workflow:
    - Fork management, branching, PR creation, job status reporting.
  - Implementation relies on `gh` CLI and a lot of glue code in `fix_issue.py`.

- **E2B**
  - GitHub is an optional tool:
    - You’d implement separate tools for clone, branch, commit, push, PR creation, etc.
  - More flexible, but more work to get to parity with today’s flow.

---

## 4. Future architecture: LLM + tools on top of ECS-as-sandbox

```mermaid
graph TB
    subgraph "Agent Runner (ECS Task)"
        Runner[runner.py<br/>Parse CLI & env]
        Kilo[Kilo GitHub Agent<br/>Current behavior]
        LLM[LLM Tools Agent<br/>Direct tool calls]
        External[External Sandbox Agent<br/>E2B-style]
        
        Runner --> Kilo
        Runner --> LLM
        Runner --> External
    end
    
    subgraph "Execution Backends"
        Local[LocalEcsWorkspace<br/>Repo checkout]
        Remote[ExternalSandbox<br/>E2B/Remote]
        
        Kilo --> Local
        LLM --> Local
        External --> Remote
    end
    
    subgraph "External Services"
        GH[GitHub]
        BE[Backend]
    end
    
    Local -->|Git operations| GH
    Remote -->|API calls| GH
    Runner -->|Update status| BE
    
    style Runner fill:#e8f5e9
    style Kilo fill:#ffe1f5
    style LLM fill:#ffe1f5
    style External fill:#ffe1f5
    style Local fill:#fff4e1
    style Remote fill:#fff4e1
```

Instead of nesting another sandbox inside ECS (which would create "double sandbox" complexity), we treat each ECS task as the primary coding sandbox, similar to how Copilot and Claude treat a dev container or VM. E2B-style sandboxes remain an **optional backend implementation**, not the default.

### 4.1 Conceptual model (jobs, agents, execution backends)

At a high level:

- **AgentJob** (already exists in backend):
  - Represents a unit of work (e.g., “fix this cluster’s GitHub issue”).
  - Fields can be extended with:
    - `agent_type`: `"kilo_github"` | `"llm_tools"` | `"external_sandbox"` | etc.
    - `sandbox_id` (optional, for external sandboxes).
    - `config` blob: serialized tool config, system prompt, repo info, etc.

- **Agent Runner**:
  - A container/service that:
    - Reads environment (JOB_ID, BACKEND_URL, agent type).
    - Dispatches to the appropriate implementation.
  - Today, `fix_issue.py` is effectively “Agent Runner + Kilo implementation”.

- **Execution backend**:
  - `LocalEcsWorkspace`:
    - The current ECS task + repo checkout.
    - Acts as the per-job sandbox for file operations and commands.
  - `ExternalSandbox` (future):
    - An E2B-style remote sandbox or similar.
    - The agent loop calls into it via a thin executor interface instead of shelling directly in the container.

### 4.2 Proposed modularization of our agent

In `coding-agent/`, we can gradually refactor into:

- `runner.py` (or extend `fix_issue.py`):
  - Parses CLI args and env:
    - `issue_url`
    - `--job-id`
    - `AGENT_TYPE` (defaults to `"kilo_github"` for backwards compatibility).
  - Calls appropriate implementation:
    - `run_kilo_github_agent(...)` (today’s behavior).
    - `run_llm_tools_agent(...)` that uses LLM + tools on top of the local ECS workspace.
    - `run_external_sandbox_agent(...)` (future) that routes tools into E2B or similar.

- `agents/kilo_github.py`:
  - Contains most of today’s logic from `_run_agent_logic`.
  - Clear boundary:
    - Input: issue URL, GitHub+Kilo credentials, job_id.
    - Output: PR URL, logs, status.

- `agents/sandbox_agent.py` (future):
  - Implements an LLM + tools agent loop:
    - Uses OpenAI / Anthropic models directly (Claude-style, Copilot-style).
    - Tools operate on `LocalEcsWorkspace`:
      - `read_file` / `write_file` scoped under the repo directory.
      - `run_shell` / `run_tests` with an allowlist (pytest, npm test, go test, etc.).
      - `git_*` operations (branch, commit, push) wrapped as explicit tools.
    - Optionally, an alternate execution backend can be plugged in (E2B) without changing the agent loop.

This layout makes it easy to:

- Keep the current PR-based path stable.
- Experiment with an LLM + tools agent for non-PR scenarios (e.g., “analysis-only”, “suggest patches”, “run tests and explain errors”) using the existing ECS sandbox.
- Later, integrate LLM + tools into the full PR workflow and/or swap in external sandboxes if needed.

### 4.3 Dashboard / backend integration

We can generalize the `POST /jobs` call (backend) and `/api/trigger-agent` (dashboard) to support agent types:

- Backend `AgentJob`:
  - Add `agent_type` enum.
  - Optional `agent_config` JSON for:
    - System prompt ID.
    - Tool set.
    - Sandbox parameters (timeout, language, etc.).

- Dashboard `/api/trigger-agent`:
  - Accept a `agentType` query/body param (`"kilo_github"` by default).
  - Pass `AGENT_TYPE` and any config env to ECS.

This gives us a clear switch:

- “Use today’s GitHub PR agent” → `agentType=kilo_github`.
- “Use new LLM + tools agent on ECS sandbox” → `agentType=llm_tools`.
- “Use external sandbox-backed agent” → `agentType=external_sandbox`.

---

## 5. Security and isolation design for Soulcaster's agent

```mermaid
graph TB
    subgraph "Per-Job Isolation"
        Job1[Job 1<br/>ECS Task]
        Job2[Job 2<br/>ECS Task]
        Job3[Job 3<br/>ECS Task]
    end
    
    subgraph "Security Controls"
        S1[Scoped GitHub Token<br/>Per tenant/repo]
        S2[Path-level Protection<br/>Denylist secrets]
        S3[Command Allowlist<br/>Safe operations only]
        S4[Network Restrictions<br/>VPC/Security Groups]
    end
    
    subgraph "Secrets Management"
        SM[AWS Secrets Manager<br/>Inject per task]
        Env[Environment Variables<br/>Job-specific only]
    end
    
    Job1 --> S1
    Job1 --> S2
    Job1 --> S3
    Job1 --> S4
    
    SM --> Job1
    SM --> Job2
    SM --> Job3
    
    Env --> Job1
    Env --> Job2
    Env --> Job3
    
    style Job1 fill:#e8f5e9
    style Job2 fill:#e8f5e9
    style Job3 fill:#e8f5e9
    style S1 fill:#ffe1f5
    style S2 fill:#ffe1f5
    style S3 fill:#ffe1f5
    style S4 fill:#ffe1f5
    style SM fill:#fff4e1
```

This section captures how we should evolve toward Copilot/Claude-grade security and isolation while reusing our ECS task as the primary sandbox.

### 5.1 Per-job and per-project isolation

- **One job = one ECS task = one workspace**
  - Keep the existing pattern: each `AgentJob` maps to a dedicated ECS task.
  - No task handles two different repos or tenants.
- **Single repo per workspace**
  - Only clone the target repo for the job.
  - Agent tools operate only under `/workspace/<repo>` (no `..` escapes).
- **No shared writable volumes across jobs**
  - Avoid cross-job writable mounts so state cannot leak between projects.
  - Shared caches (npm, pip) should be read-only or non-sensitive.

### 5.2 Tenant and permission boundaries

- **Per-tenant GitHub identity**
  - Use GitHub Apps or scoped tokens so each job has the minimum permissions needed for that repo.
  - Backend associates a job with a specific installation/token; ECS task only receives that scoped credential.
- **No “god-mode” tokens in containers**
  - Never inject a token with org-wide admin or full-repo rights.
  - Keep tokens out of model context and stdout logs.

### 5.3 Secrets and sensitive files

- **Secret injection**
  - Store secrets in AWS Secrets Manager / SSM / Doppler.
  - Inject into ECS tasks only as environment variables needed for that job (GitHub token, model API keys).
- **Path-level protections**
  - File tools enforce a denylist for paths like:
    - `.env`, `.env.local`, `id_rsa`, `.aws`, `config/secrets.*`, etc.
  - Attempts to read these either fail or return redacted content.
- **Prompt and log hygiene**
  - Do not send raw env vars or secret files to the model.
  - Redact secrets from logs before persisting them to the backend.

### 5.4 Command and network controls

- **Command allowlist for `run_shell`**
  - Only permit safe prefixes (e.g., `pytest`, `npm test`, `go test`, `cargo test`, `make test`, `git status`, `ls`, `node`, `python`, etc.).
  - Block dangerous commands and patterns (`rm -rf`, `curl`/`wget` to arbitrary hosts, `ssh`, disk formatting, etc.).
- **Optional approvals for risky actions**
  - For high-risk commands, adopt a Claude-style permission model:
    - Agent proposes commands.
    - Dashboard or policy engine decides to auto-approve or require human approval.
- **Network egress restriction**
  - At the VPC/security group level, allow only:
    - GitHub, model providers (OpenAI/Anthropic), your backend, and package registries.
  - Deny arbitrary outbound hosts to reduce data exfiltration risk.

### 5.5 Observability and lifecycle

- **Per-job logs and traces**
  - Capture agent decisions, tool calls, and shell output, tagged by `job_id` and tenant.
- **Retention and deletion**
  - Define a retention window for logs and prompt/response data; support tenant-initiated deletion.
- **Attribution**
  - Every PR and git action should clearly indicate it was generated by “Soulcaster AI agent” and which tenant/job initiated it.

---

## 6. Recommendations and phased plans

Below are concrete recommendations and phased plans for:

1. **Our current architecture (Kilo + ECS)**
2. **Adopting an LLM + tools agent on top of ECS-as-sandbox**
3. **Optionally supporting external sandboxes (E2B-style) behind the same interface**

### 6.1 Plan 1 — Evolve our current Kilo-based agent

Focus: harden and modularize our existing Kilo + GitHub agent without changing behavior.

**Recommendations**
- Extract current logic into reusable functions/modules:
  - Dependency: minor refactor of `fix_issue.py` into smaller units (fork management, branch creation, Kilo invocation, PR creation).
- Tighten logging and observability:
  - Standardize log prefixes and capture more structured events (e.g., JSON logs).
  - Ensure `update_job` always gets final logs and PR URL.
- Clarify safety/allowlist in Kilo config:
  - Revisit the `autoApproval.execute.allowed/denied` lists.
  - Consider tightening commands that can be run by Kilo.
- Make `AGENT_TYPE` explicit (even if always `"kilo_github"` for now):
  - Start treating this as a pluggable slot.

**Short-term tasks**
- [ ] Refactor `fix_issue.py` into:
  - `run_kilo_github_agent(issue_url, job_id)` (pure Python function).
  - Simple `main()` that parses CLI and calls it.
- [ ] Add `AGENT_TYPE` env parsing (default `"kilo_github"`).
- [ ] Document the Kilo agent behavior in this file and link from `FARGATE_DEPLOYMENT.md`.

### 6.2 Plan 2 — Introduce an LLM + tools agent on ECS-as-sandbox

Focus: add a second agent path that follows the deeplearning.ai tool-calling pattern, running entirely in the existing ECS workspace, initially **without** taking over the production PR workflow.

**Recommendations**
- Start with an **analysis and patch-suggestion agent**:
  - Example: “Analyze this repo and suggest a diff, but don’t open a PR”.
  - Use `apply_patches_from_markdown` as a bridge from agent output to repo changes.
- Implement a minimal tool set operating on `LocalEcsWorkspace`:
  - `read_file(path)`, `write_file(path)` under the repo root.
  - `run_shell(command)` with a strict allowlist (tests, lint, build).
  - `get_repo_status`, `summarize_diff`, `propose_commit_message`.
- Reuse the lesson patterns directly:
  - `coding_agent` loop with `max_steps`.
  - `execute_tool` helper pattern.
  - Tool schemas modeled closely on `temp/projects/docs.md`.
- Route model calls via a provider abstraction:
  - `call_model(provider="openai" | "anthropic", ...)`.

**Short-term tasks**
- [ ] Create `agents/llm_tools_agent.py` in `coding-agent/`:
  - Implement the LLM + tools loop using the local filesystem and shell.
  - Implement the first tool set with path and command allowlists.
- [ ] Add a CLI entry to run the tools agent locally:
  - `uv run llm_tools_agent.py --repo <path> --query "<task>"`.
- [ ] Optionally wire a **new dashboard mode** (e.g., “Try tools agent”) that:
  - Does not open PRs yet.
  - Surfaces explanations, diffs, and test results.

### 6.3 Plan 3 — Unified framework (both paths, optional external sandbox)

Focus: make the choice of agent type a **first-class configuration** and pave the way for industry-standard tool + sandbox flows while keeping our current PR agent.

**Recommendations**
- Promote `agent_type` to:
  - Backend `AgentJob` schema.
  - Dashboard `/api/trigger-agent` payload.
  - ECS task env (`AGENT_TYPE`).
- Implement a simple router in the agent container:
  - If `AGENT_TYPE == "kilo_github"` → current behavior.
  - If `AGENT_TYPE == "llm_tools"` → run LLM + tools loop on the ECS workspace.
  - If `AGENT_TYPE == "external_sandbox"` → route tools into an E2B-style remote sandbox.
- Eventually, unify GitHub workflows:
  - Break out GitHub operations into reusable tools:
    - `create_branch`, `commit_changes`, `open_pr`.
  - These tools can be:
    - Called directly from the sandbox agent, or
    - Reused by a future “Kilo-like” in-house agent.

**Medium-term tasks**
- [ ] Extend backend `AgentJob` model with `agent_type` and `agent_config`.
- [ ] Update dashboard to let users (or configs) pick agent type per cluster/job.
- [ ] Add metrics/telemetry to compare:
  - Success rates of Kilo vs sandbox agent.
  - Latency and cost.
  - PR review outcomes and developer satisfaction.

---

## 7. Where to lean into the lesson’s direction

The deeplearning.ai pattern aligns with where the ecosystem is moving:

- **LLM-native agent loops** with explicit tools.
- **First-class sandboxes** for safe, reproducible code execution.
- **Pluggable tools** for repo access, tests, GitHub operations, and beyond.

For Soulcaster, an incremental path that respects current constraints and modern security practices could be:

1. **Stabilize and modularize the existing Kilo agent** (Plan 1).
2. **Add an LLM + tools agent on top of the existing ECS sandbox** for analysis and experimentation (Plan 2).
3. **Gradually shift more responsibilities into the LLM + tools agent**:
   - Start with exploratory tasks, test running, and patch suggestion.
   - Later, add GitHub tools and optionally let the tools agent open PRs.
4. **Optionally introduce external sandboxes as an execution backend** when needed (Plan 3), without changing the agent loop.
5. **Keep both agents available**, with feature flags / configuration to:
   - Use Kilo for flows where we want to minimize change risk initially.
   - Use the tools agent for transparent, inspectable workflows and new features.

This approach keeps the current behavior and truth intact, while aligning Soulcaster with the security and architectural patterns used by Copilot, Claude Code, and E2B-style agents.

