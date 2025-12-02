# FeedbackAgent Dashboard

Next.js dashboard for the FeedbackAgent self-healing dev loop system.

## Overview

This dashboard provides a web interface for:

- Viewing clustered issues from Reddit and GitHub feedback
- Reviewing cluster details and associated feedback items
- Triggering the coding agent to generate fixes
- Monitoring PR creation status

## Tech Stack

- **Next.js 16** (App Router)
- **TypeScript**
- **Tailwind CSS**
- **React 19**

## Getting Started

### Prerequisites

- Node.js 18+ or 20+
- A running FeedbackAgent backend (Python/FastAPI)
- PostgreSQL database

### Installation

```bash
npm install
```

### Environment Variables

Copy `.env.example` to `.env.local` and configure:

```bash
BACKEND_URL=http://localhost:8000
```

For production (Vercel), set this in your Vercel project settings.

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

The dashboard proxies requests to the backend:

- `GET /api/clusters` → `GET {BACKEND_URL}/clusters`
- `GET /api/clusters/[id]` → `GET {BACKEND_URL}/clusters/{id}`
- `POST /api/clusters/[id]/start_fix` → `POST {BACKEND_URL}/clusters/{id}/start_fix`

## Deployment

### Vercel (Recommended)

1. Push your code to GitHub
2. Import the repository in Vercel
3. Set the **Root Directory** to `dashboard`
4. Add environment variable: `BACKEND_URL=https://your-backend-url.com`
5. Deploy

The dashboard will automatically deploy on push to main.

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

### Clusters List Page

- View all issue clusters in a table
- See cluster title, summary, feedback count, sources, and status
- Click to view details or navigate to cluster detail page

### Cluster Detail Page

- View full cluster information
- See all associated feedback items with links to sources
- Generate fixes with one click
- View GitHub PR when available
- Auto-refresh while fix is in progress

## License

See LICENSE in the root of the repository.
