# Dashboard Integration Plan

This plan outlines the steps to integrate the data ingestion layer with a Next.js dashboard, following Test Driven Development (TDD).

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     DASHBOARD (Next.js)                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Feedback List View                                  │   │
│  │  - Display all feedback items                        │   │
│  │  - Filter by source (reddit/sentry/manual)           │   │
│  │  - Prepare for clustering view (placeholder)         │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Add Source Buttons                                  │   │
│  │  - Manual: Form to submit text                       │   │
│  │  - Reddit: Config status/instructions                │   │
│  │  - Sentry: Webhook URL + instructions                │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP/REST
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  BACKEND API (FastAPI)                       │
│  - GET /feedback - List all feedback items                  │
│  - GET /feedback/{id} - Get single item                     │
│  - POST /ingest/* - Existing ingestion endpoints            │
│  - GET /stats - Summary statistics                          │
└─────────────────────────────────────────────────────────────┘
```

## Phase 1: Backend API Extensions (TDD)

### 1.1 Feedback Retrieval Endpoints
- [x] **Test**: Write test for `GET /feedback` to return all items  
- [x] **Test**: Add test for pagination (limit, offset)  
- [x] **Test**: Add test for filtering by source  
- [x] **Implement**: Create `/feedback` endpoint in `backend/main.py`  
- [x] **Refactor**: Ensure clean code  

### 1.2 Single Item Retrieval
- [x] **Test**: Write test for `GET /feedback/{id}`  
- [x] **Implement**: Create endpoint to get single item  
- [x] **Test**: Add test for non-existent ID (404)  

### 1.3 Statistics Endpoint
- [x] **Test**: Write test for `GET /stats` endpoint  
- [x] **Implement**: Return counts by source, total items, etc.  
- [x] **Note**: Prepare structure for future cluster stats  

### 1.4 CORS Configuration
- [x] Add CORS middleware for frontend access  
- [x] Configure allowed origins for development  

## Phase 2: Frontend Setup

### 2.1 Project Structure
- [x] Create `dashboard/` directory (Next.js App Router)  
- [x] Initialize Next.js project with TypeScript  
- [x] Setup Tailwind CSS  
- [x] Create basic layout structure  

### 2.2 Dependencies
- [x] Add `package.json` with dependencies:  
  - `next`
  - `react`, `react-dom`
  - `typescript`
  - `tailwindcss`
  - `@tanstack/react-query` (for API calls)
  - `date-fns` (for date formatting)
  - `lucide-react` (for icons)

### 2.3 Environment Configuration
- [~] Create `.env.local` with `NEXT_PUBLIC_API_URL`  
  _Partially done – the dashboard uses `BACKEND_URL` and other env vars; local env files are used but this exact named variable is not the only configuration knob._
- [~] Create `.env.example` template  
  _Partially done – env expectations are documented in README, but there is no dedicated `dashboard/.env.example` checked in._

## Phase 3: API Client Layer

### 3.1 TypeScript Types
- [x] Create `dashboard/types/feedback.ts`:  
 
  - `FeedbackItem` interface
  - `FeedbackSource` type
  - `Stats` interface
  - API response types

### 3.2 API Client
- [~] Create `dashboard/lib/api.ts`:  
  _Partially done – API access is implemented via route handlers (`/app/api/*`) and helpers like `dashboard/lib/redis.ts` instead of a single `api.ts` wrapper._
  - `fetchFeedback()` function
  - `fetchFeedbackById()` function
  - `submitManualFeedback()` function
  - `fetchStats()` function
  - Error handling wrapper

## Phase 4: Core Components (TDD with React Testing Library)

### 4.1 FeedbackList Component
- [~] **Test**: Write test for rendering empty state  
  _Partially done – dashboard has Jest setup and tests for some flows; FeedbackList is not fully covered yet._
- [~] **Test**: Write test for rendering feedback items  
  _Partially done – similar as above; coverage is partial._
- [~] **Test**: Write test for source filtering  
  _Partially done – logic exists in `FeedbackList.tsx`, but tests are incomplete._
- [x] **Implement**: Create `dashboard/components/FeedbackList.tsx`  
- [x] **Style**: Add responsive design with Tailwind  
 

### 4.2 FeedbackItem Component
- [~] **Test**: Write test for displaying item data  
  _Partially done – some components are tested, but FeedbackItem-style card behavior is not fully covered._
- [~] **Test**: Write test for different source types  
  _Partially done – UI supports multiple sources but lacks targeted tests._
- [x] **Implement**: Create `dashboard/components/FeedbackItem.tsx`  
- [x] **Style**: Card layout with metadata  
 

### 4.3 AddSourceButton Component
- [~] **Test**: Write test for button interactions  
  _Partially done – some UI interactions are tested; dedicated tests for add-source controls are limited._
- [x] **Implement**: Create `dashboard/components/AddSourceButton.tsx`  
- [~] **Implement**: Modal/dropdown for source selection  
  _Partially done – the UI provides controls for adding feedback and configuring sources, though not via a single consolidated modal._

### 4.4 ManualFeedbackForm Component
- [~] **Test**: Write test for form validation  
  _Partially done – Jest setup exists, but this form is not fully covered._
- [~] **Test**: Write test for submission  
  _Partially done – no dedicated test file yet._
- [x] **Implement**: Create `dashboard/components/ManualFeedbackForm.tsx`  
- [x] **Implement**: Form with textarea and submit button  
 

### 4.5 SourceConfig Component
- [~] **Test**: Write test for Reddit config display  
  _Partially done – UI exists but test coverage is incomplete._
- [~] **Test**: Write test for Sentry config display  
  _Partially done – Sentry-specific views are limited and not fully tested._
- [x] **Implement**: Create `dashboard/components/SourceConfig.tsx`  
- [x] **Implement**: Show webhook URLs, environment variables, status  
 

### 4.6 StatsCard Component
- [~] **Test**: Write test for stats display  
  _Partially done – stats are rendered and wired to `/api/stats`, but test coverage is partial._
- [x] **Implement**: Create `dashboard/components/StatsCard.tsx`  
- [x] **Implement**: Display total items, breakdown by source  
 

## Phase 5: Pages and Routing

### 5.1 Main Dashboard Page
- [x] Create `dashboard/app/page.tsx`:  
  - Fetch and display feedback list
  - Show stats cards
  - Add source buttons
  - Filter controls

### 5.2 Feedback Detail Page (Optional)
- [~] Create `dashboard/app/feedback/[id]/page.tsx`  
  _Partially done – `dashboard/app/feedback/page.tsx` and card UIs show feedback; a dedicated per-ID page is optional._
- [~] Display full feedback item with all metadata  
  _Partially done – feedback details are visible in cards and cluster views, though not in a single dedicated detail page for every item._

## Phase 6: Clustering Preparation

### 6.1 Data Structure
- [x] Design cluster data model (not implemented yet):  
  ```typescript
  interface Cluster {
    id: string
    title: string
    summary: string
    feedbackIds: string[]
    status: 'new' | 'fixing' | 'pr_opened' | 'failed'
    createdAt: string
    updatedAt: string
  }
  ```

### 6.2 UI Placeholders
- [x] Add "View Clusters" tab (disabled/placeholder)  
  _Done – clusters have their own dedicated page and navigation entry rather than a disabled tab._
- [x] Add cluster count to stats (shows 0 for now)  
  _Done – stats API and UI include cluster counts._
- [x] Add comments in code indicating clustering integration points  
  _Done – comments/docs/architecture files document clustering integration and vector pipeline._

### 6.3 Backend Preparation
- [x] Add placeholder `/clusters` endpoint (returns empty array)  
  _Done (and beyond) – full `/clusters` and `/clusters/{id}` endpoints are implemented._
- [x] Add test for future cluster endpoint  
  _Done – `backend/tests/test_clusters.py` covers cluster API behavior._
- [x] Document clustering integration points in code  
  _Done – documentation and comments outline both legacy and vector-based clustering._

## Phase 7: Integration Testing

### 7.1 End-to-End Flow
- [~] Test: Start backend server  
  _Partially done – performed manually during development but not codified here._
- [~] Test: Start frontend dev server  
  _Partially done – regularly done for local dev, not a tracked one-time task._
- [~] Test: Submit manual feedback via form  
  _Partially done – validated in practice via `ManualFeedbackForm`, but not scripted._
- [~] Test: Verify feedback appears in list  
  _Partially done – observed behavior, not automated._
- [~] Test: Check stats update correctly  
  _Partially done – stats view is wired up and manually verified._

### 7.2 Error Handling
- [~] Test: Backend offline scenario  
  _Partially done – some error states are handled in UI with generic fallbacks; explicit tests are limited._
- [~] Test: Network error handling  
  _Partially done – components handle fetch errors, but tests are not comprehensive._
- [~] Test: Invalid form submissions  
  _Partially done – basic validation exists; automated tests are sparse._

## Phase 8: Documentation and Polish

### 8.1 Documentation
- [x] Update `dashboard/README.md` with setup instructions  
- [~] Document API integration points  
  _Partially done – README and docs cover key routes, but not every new worker/proxy endpoint._
- [~] Add screenshots to README  
  _Partially done – screenshots are not consistently maintained in this repo._

### 8.2 Code Quality
- [x] Add ESLint configuration  
- [x] Add Prettier configuration  
- [x] Ensure all components have TypeScript types  
 
- [~] Add loading states and error boundaries  
  _Partially done – many views have loading/error states; full error boundary coverage is not complete._

### 8.3 Responsive Design
- [~] Test on mobile viewport  
  _Partially done – design is responsive and used on typical viewports; explicit test coverage is limited._
- [~] Test on tablet viewport  
  _Partially done – as above._
- [~] Ensure all interactions work on touch  
  _Partially done – UI is touch-friendly, but not exhaustively validated._

## Phase 9: Deployment Preparation

### 9.1 Environment Variables
- [~] Document all required environment variables  
  _Partially done – README and PRD list major env vars; not all variants are in a single canonical list._
- [~] Create `.env.example` files  
  _Partially done – there is not yet a comprehensive `.env.example` for dashboard + backend combined._

### 9.2 Build Configuration
- [~] Test production build (`npm run build`)  
  _Partially done – builds have been run during development, but not tracked against this checklist._
- [~] Configure backend URL for production  
  _Partially done – `BACKEND_URL` is used in README and Vercel config, but this item hasn’t been diligently updated._
- [x] Add deployment instructions to README  
 

## Success Criteria

- [~] Dashboard displays all feedback items from backend  
  _Partially done – dashboard reads from Redis via its own API routes; backend endpoints remain aligned but are not always the direct source._
- [x] Users can submit manual feedback via form  
- [~] Reddit and Sentry configuration instructions are clear  
  _Partially done – SourceConfig and docs mention Reddit; Sentry docs exist but are less prominent in the dashboard._
- [~] Stats accurately reflect feedback counts  
  _Partially done – stats are computed from Redis and generally correct; they may diverge if legacy clustering and vector clustering are both in play._
- [~] All tests pass (backend and frontend)  
  _Partially done – backend tests pass; dashboard tests are present but not exhaustive._
- [~] Responsive design works on all screen sizes  
  _Partially done – design is responsive for common sizes; not fully certified across all devices._
- [~] Code is well-documented and follows best practices  
  _Partially done – docs and structure are solid; there is still cleanup/tightening to do as features stabilize._
- [x] Clear integration points for future clustering feature  
 

## Future Enhancements (Post-MVP)

**Not implemented in this phase:**
- Real-time updates (WebSocket)
- Infinite scroll pagination
- Advanced filtering and search
- Bulk actions
- Cluster management UI
- PR status tracking
- Authentication and authorization
