# Future Tasks

This document tracks planned features and improvements for future implementation.

---

## Option B: Full Multi-Project Support

**Priority**: Medium  
**Complexity**: High  
**Status**: Planned

### Overview

Currently, the system uses a hardcoded default `project_id` ("default") for all feedback and GitHub sync operations. This task involves implementing full multi-project support, allowing users to manage feedback across multiple projects with proper isolation.

### Requirements

1. **Project Management UI**
   - Add project creation/selection UI in the dashboard
   - Allow users to switch between projects
   - Display project name in the header/navigation
   - Store selected project in user session or localStorage

2. **Frontend API Integration**
   - Update `FeedbackList.tsx` to pass `project_id` on all `/api/feedback` calls
   - Update GitHub sync components to pass `project_id` when triggering sync
   - Update cluster components to scope clusters by project
   - Add project context provider for React components

3. **Backend API Changes**
   - Update `/api/ingest/github/sync/route.ts` to accept `project_id` parameter
   - Update `/api/ingest/github/sync/[name]/route.ts` to accept `project_id` parameter
   - Update `/api/feedback/route.ts` to require `project_id` (remove default fallback)
   - Update `/api/clusters/*` routes to scope by project

4. **Database/Redis Schema**
   - Ensure all feedback keys follow pattern: `feedback:{projectId}:{id}`
   - Ensure all index keys follow pattern: `feedback:created:{projectId}`, `feedback:source:{projectId}:{source}`
   - Add project metadata storage: `project:{projectId}:meta`
   - Add user-project association: `user:{userId}:projects`

5. **Data Migration**
   - Create migration script to move existing "default" project data to new project structure
   - Handle backward compatibility during transition period

### Implementation Steps

1. [ ] Create `Project` model and API routes (`/api/projects`)
2. [ ] Add project selection dropdown to dashboard header
3. [ ] Create React context for current project (`ProjectContext`)
4. [ ] Update all frontend components to use project context
5. [ ] Update all API routes to use project_id from request
6. [ ] Update Redis key helpers in `lib/redis.ts` (already done)
7. [ ] Create data migration script for existing feedback
8. [ ] Add tests for multi-project scenarios
9. [ ] Update documentation

### Files to Modify

- `dashboard/components/Header.tsx` - Add project selector
- `dashboard/components/FeedbackList.tsx` - Pass project_id
- `dashboard/app/api/projects/route.ts` - New file for project CRUD
- `dashboard/app/api/feedback/route.ts` - Require project_id
- `dashboard/app/api/ingest/github/sync/route.ts` - Accept project_id
- `dashboard/app/api/ingest/github/sync/[name]/route.ts` - Accept project_id
- `dashboard/lib/project.ts` - Remove default fallback, add project management functions
- `dashboard/lib/redis.ts` - Add project metadata functions

### Estimated Effort

- Frontend UI: 4-6 hours
- API changes: 2-3 hours
- Migration script: 2-3 hours
- Testing: 2-3 hours
- **Total**: 10-15 hours

---

## Other Future Tasks

(Add additional planned features here as needed)
