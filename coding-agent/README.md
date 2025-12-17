# Soulcaster Coding Agent

This directory contains documentation and reference material for the Soulcaster Coding Agent, which is responsible for autonomously fixing issues identified by the platform.

## Architecture (Phase 5.1)

The coding agent architecture has moved to a **Plan-Execute** model:

1.  **Coding Plan Generation**:
    *   The `Planner` (in `backend/planner.py`) uses an LLM (Gemini) to analyze an `IssueCluster` and feedback items.
    *   It generates a structured `CodingPlan` containing:
        *   Title & Description
        *   Files to edit
        *   Step-by-step tasks
    *   Plans are stored in the backend (Redis/Memory).

2.  **Execution (Runners)**:
    *   Runners are pluggable components defined in `backend/agent_runner/`.
    *   **Sandbox Runner** (`sandbox_kilo`): Uses the E2B SDK (`e2b`) to spin up a secure sandbox, install the Kilocode agent, and execute the plan.
    *   **AWS Runner** (`aws_kilo`): Legacy support for running the agent in an ECS Fargate task (requires AWS credentials).

3.  **Orchestration**:
    *   The backend exposes `POST /clusters/{id}/start_fix`.
    *   This endpoint:
        1.  Ensures a `CodingPlan` exists (generating one if needed).
        2.  Selects the configured runner (via `CODING_AGENT_RUNNER` env var).
        3.  Dispatches an `AgentJob` to the runner.
        4.  Updates job status and logs.

## Configuration

### Environment Variables

*   `GEMINI_API_KEY`: Required for generating coding plans.
*   `E2B_API_KEY`: Required for the Sandbox runner.
*   `CODING_AGENT_RUNNER`: processing runner to use (default: `sandbox_kilo`).
*   `KILOCODE_TEMPLATE_NAME`: E2B template name for the agent environment (recommended).
*   `KILOCODE_TEMPLATE_ID`: E2B template ID for the agent environment (fallback, default: `base`).

## Usage

Generated plans and job status can be viewed in the Soulcaster Dashboard on the Cluster Detail page.
