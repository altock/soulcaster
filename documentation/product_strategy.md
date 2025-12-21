# Product Strategy: Ideal Customer Profile & Use Cases

## 1. Ideal Customer Profile (ICP)

**Target Audience:** Software Engineering Teams & Open Source Maintainers
**Industry:** SaaS, Developer Tools, Open Source Software
**Company Stage:** Early-stage startups to mid-sized engineering organizations (where resources are tight and triage load is high).

### Roles
*   **The Overwhelmed Maintainer:** Maintains popular open-source projects or internal libraries. Drowning in GitHub Issues and duplicates. Needs help separating signal from noise and clearing the backlog.
*   **The Tech Lead / Senior Engineer:** Responsible for product quality but stuck doing low-value maintenance work. Wants to focus on architecture and features, not minor bug fixes.
*   **The "DevOps" Minded Developer:** Cares about automation and efficiency (CI/CD, self-healing systems).

### Pains
*   **Triage Fatigue:** Spending hours manually reviewing, labeling, and deduplicating bug reports across multiple channels (GitHub, Sentry, Reddit).
*   **Context Switching:** Constant interruptions from minor bugs prevent deep work on core features.
*   **Slow Feedback Loops:** User reports a bug, it sits in a backlog for weeks because it's "low priority," leading to user churn.
*   **Fragmentation:** Feedback is scattered across Reddit threads, Sentry logs, and GitHub issues, making it hard to see the "big picture" of what's broken.

## 2. Primary Use Cases

### A. Automated Bug Triage & Resolution (The "Self-Healing" Loop)
*   **Scenario:** A runtime error occurs in production (captured by Sentry) or a user files a bug report on GitHub.
*   **Action:** Soulcaster ingests the report, checks if it matches existing clusters (deduplication), and if it's actionable, the AI agent attempts to reproduce and fix it in a sandboxed environment.
*   **Benefit:** The engineer wakes up to a PR fixing the bug instead of an alert notification.

### B. Community Feedback Aggregation
*   **Scenario:** Users are complaining about a specific UI glitch or workflow friction on a subreddit or community forum.
*   **Action:** Soulcaster polls the subreddit, identifies the cluster of negative sentiment/bug reports, summarizes the core issue, and prepares a fix or a detailed spec for the developer.
*   **Benefit:** Proactive community management; users feel heard without the team manually scouring forums.

### C. Backlog Grooming & Janitorial Work
*   **Scenario:** A project has hundreds of stale issues.
*   **Action:** Soulcaster analyzes the backlog, clusters duplicates, identifies "wontfix" items, and proposes fixes for low-hanging fruit.
*   **Benefit:** Reduces technical debt and cleans up the project hygiene.

## 3. MVP Scope (Current State)

*   **Ingestion:**
    *   Reddit (Polling specific subreddits)
    *   Sentry (Webhooks)
    *   GitHub Issues
    *   Manual Entry
*   **Intelligence:**
    *   Vector-based Clustering (Gemini Embeddings + Upstash) to group similar feedback.
    *   LLM Summarization for cluster titles and descriptions.
*   **Execution:**
    *   AI Coding Agent (running in E2B sandboxes) that can read code, write patches, and run tests.
    *   GitHub Integration to open PRs directly from the user's account.
*   **Interface:**
    *   Next.js Dashboard for human-in-the-loop review (approve fixes, view clusters).

## 4. Key Messaging Bullets

*   **"Turn Noise into Code":** Don't just log bugs—fix them.
*   **"Your AI Junior Engineer":** Handles the triage and minor fixes so you can focus on the hard stuff.
*   **"Unified Feedback Stream":** See what users are saying on Reddit, GitHub, and Sentry in one prioritized view.
*   **"One-Click Fixes":** Move from problem identification to Pull Request in a single click.