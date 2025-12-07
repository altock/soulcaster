# Dashboard API Tests

This directory contains test scripts for the Dashboard API.

## `test_trigger.sh`

This script tests the `/api/trigger-agent` endpoint, which is responsible for triggering the backend coding agent (ECS task). It supports two modes:

1.  **Trigger with Existing Issue URL**:
    Validates that the issue exists and triggers the agent.
    ```bash
    ./test_trigger.sh https://github.com/owner/repo/issues/123
    ```

2.  **Trigger with Context (Create Issue)**:
    Creates a new GitHub issue from the provided context and title, then triggers the agent with the new issue.
    ```bash
    ./test_trigger.sh context "Bug description here" "Bug Title"
    ```

### Prerequisites

*   The Next.js dashboard must be running locally (`npm run dev` in `dashboard` directory).
*   Environment variables must be set in `dashboard/.env.local` (or `.env`):
    *   `GITHUB_OWNER`: Owner of the repo for new issues.
    *   `GITHUB_REPO`: Repository name for new issues.
    *   `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`: Required for triggering the ECS task.
