# Soulcaster Dashboard

Next.js dashboard for the Soulcaster self-healing development loop system.

## Overview

This dashboard provides a comprehensive web interface for:

- **Authentication**: GitHub OAuth via NextAuth for secure access
- **Project Management**: Create and manage multiple projects with isolated feedback
- **Feedback Triage**: View and manage feedback from Reddit, GitHub, Sentry, and manual sources
- **Cluster Review**: Browse AI-clustered issues with summaries and context
- **Fix Generation**: One-click trigger for the coding agent (local or AWS Fargate)
- **Job Tracking**: Monitor agent jobs with status updates, logs, and PR links
- **Source Configuration**: Configure Reddit subreddits and GitHub repositories per project
- **Statistics Dashboard**: View aggregate metrics and trends

## Tech Stack

- **Next.js 16** (App Router)
- **React 19**
- **TypeScript**
- **Tailwind CSS 4**
- **NextAuth 4** (GitHub OAuth)
- **Prisma** (PostgreSQL for auth and projects)
- **Upstash Redis** (feedback and cluster storage)
- **Upstash Vector** (embeddings storage)
- **Google Gemini** (embeddings and clustering)
- **AWS SDK** (ECS/Fargate agent deployment)

## Getting Started

### Prerequisites

- Node.js 20+
- Upstash Redis account (for feedback and cluster storage)
- PostgreSQL database (for NextAuth sessions and projects)
- Google Gemini API key (for embeddings and clustering)
- GitHub OAuth app (for authentication)
- Optional: AWS account (for Fargate agent deployment)
- Optional: Backend service running (if using centralized polling)

### Installation

```bash
npm install
```

### Environment Variables

Copy `.env.example` to `.env.local` and configure:

**Required**:
```bash
# Database (PostgreSQL for NextAuth and projects)
DATABASE_URL=postgresql://user:password@host:5432/dbname

# Redis (Upstash for feedback and clusters)
UPSTASH_REDIS_REST_URL=https://your-redis.upstash.io
UPSTASH_REDIS_REST_TOKEN=your_token

# Gemini API (for embeddings and clustering)
GEMINI_API_KEY=your_gemini_key
# or
GOOGLE_GENERATIVE_AI_API_KEY=your_gemini_key

# NextAuth (GitHub OAuth)
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=your_secret_here  # Generate with: openssl rand -base64 32
GITHUB_ID=your_github_oauth_client_id
GITHUB_SECRET=your_github_oauth_client_secret
```

**Optional**:
```bash
# Backend API (if using centralized poller)
BACKEND_URL=http://localhost:8000

# GitHub (for higher API limits)
GITHUB_TOKEN=ghp_your_personal_access_token

# AWS (for Fargate agent deployment)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
ECS_CLUSTER_NAME=soulcaster-cluster
ECS_TASK_DEFINITION=coding-agent-task
ECS_SUBNET_IDS=subnet-xxx,subnet-yyy
ECS_SECURITY_GROUP_IDS=sg-xxx

# Default GitHub repo (for new issues)
GITHUB_OWNER=your_username
GITHUB_REPO=your_repo
```

For production (Vercel), set these in your Vercel project settings.

### Database Setup

1. Ensure your PostgreSQL database is running.
2. Run migrations to set up the schema:

```bash
npx prisma migrate dev
```

### Development

Run the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser.

### Building for Production

```bash
npm run build
npm start
```

## Testing

For testing API endpoints (like triggering the agent manually), see the [tests directory](./tests/README.md).

```bash
cd tests
./test_trigger.sh context "Bug description" "Title"
```

## API Routes

The dashboard implements its own API routes that interact directly with Redis and Upstash Vector:

### Authentication
- `GET/POST /api/auth/[...nextauth]` - NextAuth endpoints for GitHub OAuth

### Feedback & Ingestion
- `GET /api/feedback` - List feedback items with filters
- `POST /api/ingest/manual` - Submit manual feedback
- `POST /api/ingest/github/sync` - Sync GitHub issues
- `POST /api/ingest/github/sync/[name]` - Sync specific GitHub repo

### Clustering
- `GET /api/clusters` - List all clusters
- `GET /api/clusters/[id]` - Get cluster details
- `POST /api/clusters/run` - Deprecated (backend owns clustering)
- `POST /api/clusters/run-vector` - Deprecated (backend owns clustering)
- `GET /api/clusters/unclustered` - List unclustered feedback
- `POST /api/clusters/reset` - Reset all clusters (dev only)

### Job Management
- `POST /api/clusters/[id]/start_fix` - Create job and trigger agent
- `POST /api/trigger-agent` - Trigger agent (local or Fargate)

### Configuration
- `GET /api/config/reddit/subreddits` - Get Reddit subreddit config
- `POST /api/config/reddit/subreddits` - Update subreddit config
- `GET /api/config/github/repos` - List GitHub repositories
- `POST /api/config/github/repos` - Add GitHub repository
- `DELETE /api/config/github/repos/[name]` - Remove repository

### Statistics
- `GET /api/stats` - Get aggregate statistics

### Admin
- `POST /api/admin/cleanup` - Cleanup operations (admin only)

## Deployment

### Vercel (Recommended)

1. Push your code to GitHub
2. Import the repository in Vercel
3. Set the **Root Directory** to `dashboard`
4. Add environment variable: `BACKEND_URL=https://your-backend-url.com`
5. Deploy

The dashboard will automatically deploy on push to main.

## Clustering ownership

- Clustering runs automatically in the backend after ingestion.
- The dashboard does not trigger clustering; manual run routes are deprecated.
- For status or debugging, use backend endpoints (`POST /cluster-jobs`, `GET /cluster-jobs`, `GET /clustering/status`) via `BACKEND_URL`.

## Project Structure

```
dashboard/
├── app/
│   ├── api/
│   │   └── clusters/          # API route proxies
│   ├── clusters/
│   │   └── [id]/             # Cluster detail page
│   ├── globals.css           # Global styles with Tailwind
│   ├── layout.tsx            # Root layout
│   └── page.tsx              # Main clusters list
├── types/
│   └── index.ts              # TypeScript type definitions
└── package.json
```

## Features

### Authentication & Projects
- GitHub OAuth login via NextAuth
- Multi-tenant project support
- Project switching via header dropdown
- User profile and default project settings

### Dashboard Home
- Statistics cards: total feedback, clusters, sources, open PRs
- Recent activity feed
- Quick access to all features

### Clusters Page
- Browse all AI-clustered issues
- Filter by status, source, date
- View cluster titles, summaries, and feedback counts
- See source breakdown (Reddit, GitHub, Sentry, manual)
- Click to view detailed cluster information

### Cluster Detail Page
- Full cluster information with AI-generated summary
- List of all associated feedback items with original links
- One-click fix generation
- Job tracking with real-time status updates
- Logs viewer for debugging
- GitHub PR link when available
- Auto-refresh while fix is in progress

### Feedback Management
- View all feedback items across sources
- Filter by source, cluster status
- Edit feedback text and metadata
- Manual feedback submission form
- Bulk operations support

### Source Configuration
- Configure Reddit subreddits to monitor
- Add/remove GitHub repositories
- GitHub issue sync (manual or scheduled)
- Webhook setup instructions

### PR Tracking
- View all generated PRs
- Filter by status (open, merged, closed)
- Quick links to GitHub
- PR metadata and timing

## License

See LICENSE in the root of the repository.
