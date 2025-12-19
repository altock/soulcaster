## Complete User Flow Documentation

### Overview
Soulcaster is a self-healing development loop that automatically ingests feedback from multiple sources, clusters related issues using AI embeddings, enables human triage via a dashboard, and generates code fixes as GitHub PRs.

**Flow**: `Reddit/Sentry/GitHub → Clustered Issues → Dashboard Triage → Coding Agent → GitHub PR`

---

## 1. Authentication Flow
**Entry Point**: `/auth/signin`

- Users sign in via GitHub OAuth (mandatory)
- PRs are created from the user's GitHub account (not a bot)
- Token stored securely in encrypted NextAuth session
- Required scopes: `repo`, `read:user`

---

## 2. Feedback Ingestion Flow

### Sources

| Source | Endpoint | Trigger |
|--------|----------|---------|
| Reddit | `POST /ingest/reddit` | Automatic polling (configurable subreddits) |
| Sentry | `POST /ingest/sentry` | Webhook (signature verified) |
| GitHub | `POST /ingest/github/sync/{repo}` | Sync configured repositories |
| Manual | `POST /ingest/manual` | User submits via dashboard |
| Splunk | `POST /ingest/splunk/webhook` | Alert webhooks |
| Datadog | `POST /ingest/datadog/webhook` | Monitor alerts |
| PostHog | `POST /ingest/posthog/webhook` | Event webhooks |

### Configuration
Dashboard → Feedback Page → "Configure Sources" to set up:
- Subreddits to monitor
- GitHub repositories to sync
- Webhook secrets and filters for integrations

---

## 3. Clustering Flow

### Algorithm (Vector-Based)
1. Generate embedding via Gemini API (`gemini-embedding-001`)
2. Query Upstash Vector for similar items (top-K ANN search)
3. Apply threshold logic (**0.72** similarity):
   - Match ≥ 0.72 + already clustered → join existing cluster
   - Match ≥ 0.72 + unclustered → create new cluster with similar items
   - No match → create single-item cluster
4. Generate LLM summary for new/changed clusters

Clustering is **automatically triggered** after each feedback ingestion.

---

## 4. Dashboard User Flow

### Pages

| Page | URL | Purpose |
|------|-----|---------|
| Home | `/dashboard` | Stats overview (clusters, feedback, PRs) |
| Clusters | `/dashboard/clusters` | List all issue clusters with status |
| Cluster Detail | `/dashboard/clusters/{id}` | View cluster info, feedback items, coding plan, fix jobs |
| Feedback | `/dashboard/feedback` | View all feedback, configure sources |
| PRs | `/dashboard/prs` | Track all agent jobs and created PRs |

### Cluster Detail Page Features
1. **Cluster Information** - Title, status, description, GitHub repo
2. **Coding Plan** - Auto-generated plan with files to modify and tasks
3. **Feedback Items** - All feedback grouped in this cluster
4. **Fix Job Status** - Real-time job monitoring with logs

---

## 5. Agent/Fix Generation Flow

### Trigger Fix
1. User reviews cluster and feedback items
2. Views/generates coding plan (auto-generated or manual)
3. Clicks **"Start Fix"** button

### Execution
1. Backend creates `AgentJob` (status: `pending`)
2. Cluster status → `fixing`
3. E2B Sandbox spins up with Kilocode agent
4. Agent: clones repo → analyzes code → generates patches → creates branch → commits → opens PR
5. PR URL stored in job, cluster status → `pr_opened`

### Monitoring
- Dashboard polls every 5 seconds for job status
- Logs stream in real-time
- States: `pending` → `running` → `success`/`failed`

---

## 6. Cluster Status Lifecycle

```plaintext
new (Initial)
 ↓ User clicks "Start Fix"
fixing (Agent Running)
 ├── success → pr_opened (PR Created)
 └── failed (Retry Available)
```

---

## 7. End-to-End Example

**Scenario**: User reports bug on Reddit about export crashes

1. **Ingest**: Reddit poller discovers post → creates `FeedbackItem`
2. **Cluster**: Embedding generated → finds similar GitHub issue (0.78 score) → joins existing "Export failures" cluster
3. **View**: User logs in → sees cluster on dashboard
4. **Review**: Views cluster detail with 3 grouped feedback items
5. **Plan**: Clicks "Generate Plan" → sees file modifications and tasks
6. **Fix**: Clicks "Start Fix" → E2B agent runs
7. **Monitor**: Watches job progress → logs stream in
8. **PR**: Agent creates PR → link appears on dashboard
9. **Merge**: User reviews on GitHub → merges if satisfied

---

## 8. Key Design Decisions

- **Multi-tenancy**: All operations scoped by `project_id`
- **User attribution**: PRs created from user's GitHub account
- **Backend-owned clustering**: Runs in FastAPI with vector embeddings
- **Pluggable runners**: E2B (default) or AWS Fargate
- **Real-time updates**: 2-5 second polling intervals
