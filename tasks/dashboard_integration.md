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
- [ ] **Test**: Write test for `GET /feedback` to return all items
- [ ] **Test**: Add test for pagination (limit, offset)
- [ ] **Test**: Add test for filtering by source
- [ ] **Implement**: Create `/feedback` endpoint in `backend/main.py`
- [ ] **Refactor**: Ensure clean code

### 1.2 Single Item Retrieval
- [ ] **Test**: Write test for `GET /feedback/{id}`
- [ ] **Implement**: Create endpoint to get single item
- [ ] **Test**: Add test for non-existent ID (404)

### 1.3 Statistics Endpoint
- [ ] **Test**: Write test for `GET /stats` endpoint
- [ ] **Implement**: Return counts by source, total items, etc.
- [ ] **Note**: Prepare structure for future cluster stats

### 1.4 CORS Configuration
- [ ] Add CORS middleware for frontend access
- [ ] Configure allowed origins for development

## Phase 2: Frontend Setup

### 2.1 Project Structure
- [ ] Create `dashboard/` directory (Next.js App Router)
- [ ] Initialize Next.js project with TypeScript
- [ ] Setup Tailwind CSS
- [ ] Create basic layout structure

### 2.2 Dependencies
- [ ] Add `package.json` with dependencies:
  - `next`
  - `react`, `react-dom`
  - `typescript`
  - `tailwindcss`
  - `@tanstack/react-query` (for API calls)
  - `date-fns` (for date formatting)
  - `lucide-react` (for icons)

### 2.3 Environment Configuration
- [ ] Create `.env.local` with `NEXT_PUBLIC_API_URL`
- [ ] Create `.env.example` template

## Phase 3: API Client Layer

### 3.1 TypeScript Types
- [ ] Create `dashboard/types/feedback.ts`:
  - `FeedbackItem` interface
  - `FeedbackSource` type
  - `Stats` interface
  - API response types

### 3.2 API Client
- [ ] Create `dashboard/lib/api.ts`:
  - `fetchFeedback()` function
  - `fetchFeedbackById()` function
  - `submitManualFeedback()` function
  - `fetchStats()` function
  - Error handling wrapper

## Phase 4: Core Components (TDD with React Testing Library)

### 4.1 FeedbackList Component
- [ ] **Test**: Write test for rendering empty state
- [ ] **Test**: Write test for rendering feedback items
- [ ] **Test**: Write test for source filtering
- [ ] **Implement**: Create `dashboard/components/FeedbackList.tsx`
- [ ] **Style**: Add responsive design with Tailwind

### 4.2 FeedbackItem Component
- [ ] **Test**: Write test for displaying item data
- [ ] **Test**: Write test for different source types
- [ ] **Implement**: Create `dashboard/components/FeedbackItem.tsx`
- [ ] **Style**: Card layout with metadata

### 4.3 AddSourceButton Component
- [ ] **Test**: Write test for button interactions
- [ ] **Implement**: Create `dashboard/components/AddSourceButton.tsx`
- [ ] **Implement**: Modal/dropdown for source selection

### 4.4 ManualFeedbackForm Component
- [ ] **Test**: Write test for form validation
- [ ] **Test**: Write test for submission
- [ ] **Implement**: Create `dashboard/components/ManualFeedbackForm.tsx`
- [ ] **Implement**: Form with textarea and submit button

### 4.5 SourceConfig Component
- [ ] **Test**: Write test for Reddit config display
- [ ] **Test**: Write test for Sentry config display
- [ ] **Implement**: Create `dashboard/components/SourceConfig.tsx`
- [ ] **Implement**: Show webhook URLs, environment variables, status

### 4.6 StatsCard Component
- [ ] **Test**: Write test for stats display
- [ ] **Implement**: Create `dashboard/components/StatsCard.tsx`
- [ ] **Implement**: Display total items, breakdown by source

## Phase 5: Pages and Routing

### 5.1 Main Dashboard Page
- [ ] Create `dashboard/app/page.tsx`:
  - Fetch and display feedback list
  - Show stats cards
  - Add source buttons
  - Filter controls

### 5.2 Feedback Detail Page (Optional)
- [ ] Create `dashboard/app/feedback/[id]/page.tsx`
- [ ] Display full feedback item with all metadata

## Phase 6: Clustering Preparation

### 6.1 Data Structure
- [ ] Design cluster data model (not implemented yet):
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
- [ ] Add "View Clusters" tab (disabled/placeholder)
- [ ] Add cluster count to stats (shows 0 for now)
- [ ] Add comments in code indicating clustering integration points

### 6.3 Backend Preparation
- [ ] Add placeholder `/clusters` endpoint (returns empty array)
- [ ] Add test for future cluster endpoint
- [ ] Document clustering integration points in code

## Phase 7: Integration Testing

### 7.1 End-to-End Flow
- [ ] Test: Start backend server
- [ ] Test: Start frontend dev server
- [ ] Test: Submit manual feedback via form
- [ ] Test: Verify feedback appears in list
- [ ] Test: Check stats update correctly

### 7.2 Error Handling
- [ ] Test: Backend offline scenario
- [ ] Test: Network error handling
- [ ] Test: Invalid form submissions

## Phase 8: Documentation and Polish

### 8.1 Documentation
- [ ] Update `dashboard/README.md` with setup instructions
- [ ] Document API integration points
- [ ] Add screenshots to README

### 8.2 Code Quality
- [ ] Add ESLint configuration
- [ ] Add Prettier configuration
- [ ] Ensure all components have TypeScript types
- [ ] Add loading states and error boundaries

### 8.3 Responsive Design
- [ ] Test on mobile viewport
- [ ] Test on tablet viewport
- [ ] Ensure all interactions work on touch

## Phase 9: Deployment Preparation

### 9.1 Environment Variables
- [ ] Document all required environment variables
- [ ] Create `.env.example` files

### 9.2 Build Configuration
- [ ] Test production build (`npm run build`)
- [ ] Configure backend URL for production
- [ ] Add deployment instructions to README

## Success Criteria

- [ ] Dashboard displays all feedback items from backend
- [ ] Users can submit manual feedback via form
- [ ] Reddit and Sentry configuration instructions are clear
- [ ] Stats accurately reflect feedback counts
- [ ] All tests pass (backend and frontend)
- [ ] Responsive design works on all screen sizes
- [ ] Code is well-documented and follows best practices
- [ ] Clear integration points for future clustering feature

## Future Enhancements (Post-MVP)

**Not implemented in this phase:**
- Real-time updates (WebSocket)
- Infinite scroll pagination
- Advanced filtering and search
- Bulk actions
- Cluster management UI
- PR status tracking
- Authentication and authorization
