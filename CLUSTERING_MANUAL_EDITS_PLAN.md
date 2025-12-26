# Clustering Algorithm & Manual Edit Handling - Analysis & Plan

**Date**: 2025-12-22
**Status**: Design Document
**Branch**: `docs/clustering-manual-edits-analysis`

---

## Executive Summary

This document analyzes how Soulcaster's clustering algorithm handles manual edits to clusters (split/delete/merge/move items) during reclustering or when new elements are ingested. It identifies architectural strengths, current limitations, and proposes enhancements for robust manual cluster management.

**Key Finding**: The algorithm uses **incremental clustering with implicit preservation** - manual edits are preserved because reclustering only processes unclustered items, never touching existing assignments.

---

## Table of Contents

1. [Current Clustering Algorithm Behavior](#current-clustering-algorithm-behavior)
2. [Manual Edit Preservation Mechanisms](#manual-edit-preservation-mechanisms)
3. [Limitations & Risks](#limitations--risks)
4. [Proposed Enhancements](#proposed-enhancements)
5. [Implementation Plan](#implementation-plan)
6. [Technical References](#technical-references)

---

## Current Clustering Algorithm Behavior

### 1. New Item Ingestion

**File**: `backend/vector_store.py:439-506`

When a new feedback item is ingested, the clustering algorithm follows this decision tree:

```
┌─────────────────────────────────────────────┐
│  New Feedback Item Received                 │
└─────────────┬───────────────────────────────┘
              │
              ▼
    ┌─────────────────────┐
    │ Generate Embedding  │
    │ (Gemini API)        │
    └─────────┬───────────┘
              │
              ▼
    ┌─────────────────────────────────────┐
    │ Query Upstash Vector DB             │
    │ for Similar Items                   │
    │ Threshold: similarity ≥ 0.72        │
    └─────────┬───────────────────────────┘
              │
              ▼
        ┌─────────────┐
        │  Similar    │
        │  items      │
        │  found?     │
        └──┬──────┬───┘
           │      │
          YES    NO
           │      │
           │      ▼
           │   ┌──────────────────────┐
           │   │ Create single-item   │
           │   │ cluster              │
           │   └──────────────────────┘
           │
           ▼
    ┌─────────────────────────────────────┐
    │ Are any similar items               │
    │ already clustered?                  │
    └─────────┬─────────┬─────────────────┘
              │         │
             YES       NO
              │         │
              │         ▼
              │    ┌────────────────────────┐
              │    │ Create new cluster     │
              │    │ with all similar items │
              │    └────────────────────────┘
              │
              ▼
    ┌─────────────────────────────────────┐
    │ Join cluster of most similar        │
    │ already-clustered item              │
    └─────────────────────────────────────┘
              │
              ▼
    ┌─────────────────────────────────────┐
    │ Remove from "unclustered" set       │
    │ ← ITEM IS NOW PERMANENT             │
    └─────────────────────────────────────┘
```

**Key Behaviors**:
- **Respects existing clusters**: If similar items exist in Cluster A, new items join Cluster A
- **Prevents cluster proliferation**: Won't create competing clusters for similar content
- **Threshold-based**: 0.72 similarity threshold determines cluster membership

### 2. Reclustering Workflow

**File**: `backend/clustering_runner.py:338-433`

When "Run Clustering" is triggered via `POST /api/clusters/jobs`:

```python
# Line 348 - CRITICAL: Only processes unclustered items
items = get_unclustered_feedback(project_id)

# Process only items in feedback:unclustered:{project_id} Redis set
for item in items:
    cluster_with_vector_db(item, project_id)
    remove_from_unclustered_batch([item.id], project_id)
```

**Behavior**:
- ✅ **Incremental only** - processes new/unclustered items
- ✅ **Never re-processes clustered items**
- ✅ **Existing assignments are permanent**
- ✅ **New items can join existing clusters** based on similarity

**This means**:
1. Once an item is clustered, it stays in that cluster forever (barring manual intervention)
2. Manual moves/merges/splits would be preserved if tools existed to perform them
3. No risk of automatic re-clustering overwriting manual edits

---

## Manual Edit Preservation Mechanisms

### Current State: Implicit Preservation

**How it works**:
- Items are tracked in `feedback:unclustered:{project_id}` Redis set
- Once clustered, items are removed from this set
- Clustering jobs **only fetch from the unclustered set**
- Result: Clustered items are never re-evaluated

**Strengths**:
- ✅ Simple and effective
- ✅ No complex locking mechanisms needed
- ✅ Manual edits are naturally preserved
- ✅ Performance-efficient (doesn't reprocess everything)

**Limitations**:
- ❌ No explicit "manual edit" tracking
- ❌ No audit trail of manual vs automatic clustering
- ❌ No way to distinguish intentional splits from algorithm errors
- ❌ Cleanup endpoint can still merge manually-separated clusters

### Data Model Analysis

**Files Examined**:
- `backend/models.py` - Pydantic models
- `dashboard/types/index.ts` - TypeScript types

**FeedbackItem Model**:
```python
class FeedbackItem(BaseModel):
    id: str
    source: str
    title: str
    body: str
    metadata: Dict[str, Any]
    created_at: datetime
    # Missing: manual_override, locked, cluster_assignment_type
```

**IssueCluster Model**:
```python
class IssueCluster(BaseModel):
    id: str
    title: str
    summary: str
    status: str
    centroid: List[float]
    feedback_ids: List[str]
    # Missing: locked, manually_edited, created_by_user
```

**No fields exist for**:
- Manual override flags
- Lock status
- Cluster assignment type (auto vs manual)
- Edit history/audit trail

---

## Limitations & Risks

### 1. No Manual Editing Infrastructure

**Current State**: Backend has functions but no exposed endpoints

**Available Functions** (in `store.py`):
- `add_feedback_to_cluster(cluster_id, feedback_id)` ✅ Exists
- `update_cluster(cluster_id, **fields)` ✅ Exists
- `delete_cluster(cluster_id)` ✅ Exists

**Missing API Endpoints**:
- ❌ `PUT /feedback/{id}/cluster` - Move item between clusters
- ❌ `POST /clusters/merge` - Manually merge two clusters
- ❌ `POST /clusters/{id}/split` - Split cluster by selecting items
- ❌ `DELETE /clusters/{id}` - Delete individual cluster
- ❌ `POST /clusters/{id}/lock` - Protect from auto-cleanup

**Missing UI Features**:
- ❌ Drag-and-drop items between clusters
- ❌ Multi-select items for bulk operations
- ❌ Visual cluster merge interface
- ❌ Cluster split workflow
- ❌ Lock/unlock toggle

### 2. Cleanup Endpoint Risk

**File**: `backend/main.py` - `POST /api/clusters/cleanup`

**What it does**:
1. Finds clusters with similar centroids (≥0.65 similarity)
2. Groups similar clusters using Union-Find algorithm
3. Merges clusters (keeps largest or "fixing" status)
4. Deletes duplicate clusters

**Risk to manual edits**:
- If you intentionally split Cluster A into Clusters B and C, cleanup might merge them back
- No "lock" mechanism prevents this
- Users have no visibility into which clusters will merge before running cleanup

**Current mitigation**: Cleanup is not exposed in UI (no button), so it won't run accidentally

### 3. Vector DB Metadata Sync

**Current Issue**: When manually moving items, two systems must be updated:
1. **Redis**: `cluster:{id}` feedback_ids array
2. **Upstash Vector DB**: `cluster_id` metadata for each embedding

**Risk**: Inconsistency if only one system is updated

**Missing**:
- Transaction-like coordination between Redis and Vector DB
- Validation that metadata matches cluster assignments
- Repair/sync tools for inconsistent states

### 4. No Audit Trail

Users cannot answer:
- Why is this item in this cluster?
- Was this cluster manually created or auto-generated?
- When was this cluster last modified?
- Who moved items between clusters?

---

## Proposed Enhancements

### Phase 1: Data Model Extensions

**Add to FeedbackItem**:
```python
class FeedbackItem(BaseModel):
    # ... existing fields ...
    manual_cluster_assignment: bool = False
    cluster_assignment_timestamp: datetime
    cluster_assignment_method: Literal["auto", "manual_move", "manual_merge", "manual_split"]
```

**Add to IssueCluster**:
```python
class IssueCluster(BaseModel):
    # ... existing fields ...
    locked: bool = False  # Prevent auto-cleanup merging
    manually_edited: bool = False
    created_by: Literal["algorithm", "user_merge", "user_split"]
    last_modified_at: datetime
    modification_history: List[ClusterModification] = []
```

**New Model - ClusterModification**:
```python
class ClusterModification(BaseModel):
    timestamp: datetime
    action: Literal["created", "merged", "split", "item_added", "item_removed", "locked", "unlocked"]
    user_id: Optional[str]  # From NextAuth session
    details: Dict[str, Any]  # Action-specific metadata
```

### Phase 2: API Endpoints

#### 2.1 Move Feedback Between Clusters
```
PUT /api/feedback/{feedback_id}/cluster
Body: { "cluster_id": "new-cluster-id" }

Logic:
1. Remove from old cluster's feedback_ids
2. Add to new cluster's feedback_ids
3. Update Vector DB metadata
4. Set manual_cluster_assignment = true
5. Log modification to both clusters
```

#### 2.2 Manual Cluster Merge
```
POST /api/clusters/merge
Body: {
  "source_cluster_ids": ["cluster-1", "cluster-2"],
  "target_cluster_id": "cluster-1",  # Optional: create new if omitted
  "title": "Merged cluster title",
  "locked": true  # Prevent future auto-merging
}

Logic:
1. Combine all feedback_ids
2. Merge modification histories
3. Recalculate centroid
4. Update Vector DB metadata for all items
5. Delete source clusters
6. Mark as manually_edited = true
```

#### 2.3 Manual Cluster Split
```
POST /api/clusters/{cluster_id}/split
Body: {
  "new_clusters": [
    {
      "title": "Cluster A",
      "feedback_ids": ["id1", "id2"],
      "locked": true
    },
    {
      "title": "Cluster B",
      "feedback_ids": ["id3", "id4"],
      "locked": true
    }
  ]
}

Logic:
1. Validate all feedback_ids belong to source cluster
2. Create new clusters with specified items
3. Update Vector DB metadata
4. Delete original cluster
5. Mark new clusters as created_by = "user_split"
```

#### 2.4 Lock/Unlock Cluster
```
POST /api/clusters/{cluster_id}/lock
POST /api/clusters/{cluster_id}/unlock

Logic:
1. Set locked flag
2. Modify cleanup endpoint to skip locked clusters
3. Log action to modification history
```

#### 2.5 Delete Individual Cluster
```
DELETE /api/clusters/{cluster_id}
Query: ?reassign_to={cluster_id} or ?mark_unclustered=true

Logic:
1. If reassign_to: move all items to target cluster
2. If mark_unclustered: add items back to unclustered set
3. Delete cluster from Redis
4. Update Vector DB metadata
5. Log deletion
```

### Phase 3: UI Components

#### 3.1 Cluster Management Toolbar
Location: `/dashboard/clusters/[id]` (Detail View)

**Features**:
- Lock/Unlock toggle (icon: 🔒/🔓)
- Delete cluster button
- Split cluster button → Opens modal
- Merge with another cluster → Search/select interface

#### 3.2 Item Reassignment Interface

**Option A: Drag-and-Drop**
- Draggable feedback items in Review tab
- Drop zones for other clusters (sidebar or modal)
- Confirmation dialog before moving

**Option B: Bulk Selection + Move**
- Checkboxes on feedback items
- "Move selected items" button
- Cluster picker dropdown
- Batch move operation

#### 3.3 Cluster Split Modal

**Workflow**:
1. Click "Split Cluster" button
2. Modal shows all feedback items with checkboxes
3. Create two groups (A and B)
4. Assign items to groups via checkboxes/drag-drop
5. Enter titles for new clusters
6. Option: "Lock new clusters to prevent auto-merging"
7. Confirm split

#### 3.4 Cluster Merge Interface

**Workflow**:
1. Click "Merge with another cluster" button
2. Search/select target cluster
3. Preview: Shows all items from both clusters
4. Choose merged cluster title
5. Option: "Lock merged cluster"
6. Confirm merge

#### 3.5 Modification History View

Location: New tab on cluster detail page - "History"

**Display**:
- Timeline of all modifications
- Icons for action types (merge, split, move, lock)
- Timestamps and user info
- Expandable details for each action

### Phase 4: Enhanced Cleanup Endpoint

**Modify**: `POST /api/clusters/cleanup`

**Changes**:
1. Skip clusters where `locked = true`
2. Add query parameter: `?preview=true` to see what would merge
3. Return detailed report:
   ```json
   {
     "preview": true,
     "merge_groups": [
       {
         "clusters": ["cluster-1", "cluster-2"],
         "similarity": 0.87,
         "would_keep": "cluster-1",
         "would_delete": ["cluster-2"],
         "locked": false
       }
     ],
     "locked_clusters_skipped": ["cluster-3", "cluster-4"]
   }
   ```
4. UI button: "Preview Cleanup" shows report, user approves before execution

### Phase 5: Consistency & Validation Tools

#### 5.1 Sync Validation Endpoint
```
GET /api/clusters/validate

Returns:
- Items in Redis clusters but missing Vector DB metadata
- Items with Vector DB metadata but not in any cluster
- Items in multiple clusters (data corruption)
- Orphaned Vector DB entries
```

#### 5.2 Repair Endpoint
```
POST /api/clusters/repair
Body: { "mode": "auto" | "manual", "actions": [...] }

Automatically fixes:
- Removes duplicate cluster assignments
- Syncs Vector DB metadata with Redis
- Rebuilds cluster:items:{id} sets from feedback_ids
```

---

## Implementation Plan

### Stage 1: Foundation (Week 1)
**Goal**: Add data model support without breaking existing functionality

**Tasks**:
1. Add new fields to `FeedbackItem` and `IssueCluster` models
2. Create `ClusterModification` model
3. Add migration script to populate defaults for existing data
4. Update storage layer (`store.py`) to handle new fields
5. Write unit tests for new fields

**Validation**:
- Existing clustering continues to work
- New fields default correctly
- No data loss during migration

### Stage 2: Move API (Week 2)
**Goal**: Enable moving feedback items between clusters

**Tasks**:
1. Implement `PUT /feedback/{id}/cluster` endpoint
2. Add Redis transaction logic (remove from old, add to new)
3. Update Vector DB metadata synchronously
4. Add modification logging
5. Write API tests
6. Create simple UI button "Move to another cluster" in feedback item card

**Validation**:
- Items move correctly between clusters
- Vector DB stays in sync
- Modification history is logged
- UI reflects changes immediately

### Stage 3: Lock & Delete APIs (Week 2)
**Goal**: Prevent unwanted auto-merging and allow cluster deletion

**Tasks**:
1. Implement `POST /clusters/{id}/lock` and `/unlock` endpoints
2. Modify cleanup endpoint to respect locked flag
3. Implement `DELETE /clusters/{id}` with reassignment options
4. Add UI toggle for lock/unlock in cluster header
5. Add delete button with confirmation dialog

**Validation**:
- Locked clusters are skipped during cleanup
- Deletion properly handles item reassignment
- UI shows lock status clearly

### Stage 4: Merge & Split APIs (Week 3)
**Goal**: Full manual cluster management capabilities

**Tasks**:
1. Implement `POST /clusters/merge` endpoint
2. Implement `POST /clusters/{id}/split` endpoint
3. Add comprehensive logging for both operations
4. Create merge UI modal with cluster search
5. Create split UI modal with item grouping interface
6. Add visual feedback during operations (loading states)

**Validation**:
- Merges combine all data correctly
- Splits create valid new clusters
- Vector DB metadata updates for all affected items
- UI workflows are intuitive

### Stage 5: Audit & Monitoring (Week 4)
**Goal**: Visibility and troubleshooting tools

**Tasks**:
1. Create "History" tab on cluster detail page
2. Implement modification timeline component
3. Add `GET /clusters/validate` endpoint
4. Add `POST /clusters/repair` endpoint
5. Create admin dashboard showing:
   - Manual vs automatic cluster counts
   - Locked cluster count
   - Recent modifications feed
   - Data consistency status

**Validation**:
- Users can see why clusters were modified
- Admins can detect and fix inconsistencies
- System health is visible

### Stage 6: Enhanced Cleanup (Week 5)
**Goal**: Safe, predictable cleanup with user control

**Tasks**:
1. Add preview mode to cleanup endpoint
2. Create "Preview Cleanup" UI button
3. Show detailed report of proposed merges
4. Allow users to lock clusters before running cleanup
5. Add progress tracking for long cleanup jobs

**Validation**:
- Users understand cleanup impact before running
- Can protect important clusters
- No surprises from automatic merging

---

## Technical References

### Key Files Modified

**Backend**:
- `backend/models.py` - Add new fields and ClusterModification model
- `backend/store.py` - Update storage functions for new fields
- `backend/vector_store.py` - Add Vector DB metadata sync for moves
- `backend/main.py` - Add new API endpoints
- `backend/clustering_runner.py` - Respect locked flag

**Dashboard**:
- `dashboard/types/index.ts` - Update TypeScript types
- `dashboard/app/clusters/[id]/page.tsx` - Add management UI
- `dashboard/lib/api.ts` - Add API client functions
- `dashboard/components/ClusterManagement/` - New component directory:
  - `MoveItemModal.tsx`
  - `MergeClusterModal.tsx`
  - `SplitClusterModal.tsx`
  - `ModificationHistory.tsx`
  - `LockToggle.tsx`

**Database Migrations**:
- `backend/migrations/add_manual_edit_fields.py` - Add new fields
- `backend/migrations/populate_defaults.py` - Set defaults for existing data

### Redis Schema Changes

**New Keys**:
```
cluster:{id}:modifications - List of ClusterModification JSON
cluster:{id}:locked - String "true"/"false"
feedback:{id}:manual_assignment - String "true"/"false"
```

**Updated Keys**:
```
cluster:{id} - Add fields: locked, manually_edited, created_by, last_modified_at
feedback:{id} - Add fields: manual_cluster_assignment, cluster_assignment_timestamp
```

### Vector DB Metadata Schema

**Current**:
```json
{
  "cluster_id": "cluster-123",
  "project_id": "proj-456"
}
```

**Enhanced**:
```json
{
  "cluster_id": "cluster-123",
  "project_id": "proj-456",
  "manual_assignment": false,
  "assignment_timestamp": "2025-12-22T10:30:00Z",
  "assignment_method": "auto"
}
```

### API Contract Examples

#### Move Feedback Item
```bash
curl -X PUT http://localhost:8000/api/feedback/fb-123/cluster \
  -H "Content-Type: application/json" \
  -d '{
    "cluster_id": "cluster-456",
    "reason": "User correction - item was misclassified"
  }'

# Response
{
  "success": true,
  "feedback_id": "fb-123",
  "old_cluster_id": "cluster-123",
  "new_cluster_id": "cluster-456",
  "modification": {
    "timestamp": "2025-12-22T10:30:00Z",
    "action": "item_moved",
    "user_id": "user-789"
  }
}
```

#### Merge Clusters
```bash
curl -X POST http://localhost:8000/api/clusters/merge \
  -H "Content-Type: application/json" \
  -d '{
    "source_cluster_ids": ["cluster-1", "cluster-2", "cluster-3"],
    "title": "Authentication Errors - Unified",
    "locked": true
  }'

# Response
{
  "success": true,
  "merged_cluster_id": "cluster-new",
  "deleted_cluster_ids": ["cluster-1", "cluster-2", "cluster-3"],
  "total_feedback_items": 47,
  "locked": true
}
```

#### Split Cluster
```bash
curl -X POST http://localhost:8000/api/clusters/cluster-123/split \
  -H "Content-Type: application/json" \
  -d '{
    "new_clusters": [
      {
        "title": "Login Failed - Invalid Credentials",
        "feedback_ids": ["fb-1", "fb-2", "fb-3"],
        "locked": true
      },
      {
        "title": "Login Failed - Network Issues",
        "feedback_ids": ["fb-4", "fb-5"],
        "locked": true
      }
    ]
  }'

# Response
{
  "success": true,
  "deleted_cluster_id": "cluster-123",
  "new_clusters": [
    {
      "id": "cluster-new-1",
      "title": "Login Failed - Invalid Credentials",
      "feedback_count": 3
    },
    {
      "id": "cluster-new-2",
      "title": "Login Failed - Network Issues",
      "feedback_count": 2
    }
  ]
}
```

---

## Security Considerations

### Authentication & Authorization

**Required**:
- All manual edit operations require authenticated user (NextAuth session)
- Log user ID in modification history
- Consider role-based access:
  - Viewers: Can only view clusters
  - Contributors: Can move items, lock/unlock
  - Admins: Can merge, split, delete, run cleanup

**Implementation**:
```typescript
// dashboard/app/api/feedback/[id]/cluster/route.ts
export async function PUT(req: Request, { params }: { params: { id: string } }) {
  const session = await getServerSession(authOptions);
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // Log modification with user ID
  const modification = {
    user_id: session.user.id,
    user_email: session.user.email,
    action: "item_moved",
    timestamp: new Date().toISOString()
  };

  // ... perform operation ...
}
```

### Validation

**Prevent**:
- Moving items between different projects (project_id mismatch)
- Creating empty clusters
- Splitting into clusters with overlapping items
- Merging locked clusters without explicit override
- Deleting clusters with active fix jobs

**Example Validation**:
```python
# backend/main.py
@app.put("/api/feedback/{feedback_id}/cluster")
async def move_feedback_to_cluster(feedback_id: str, body: MoveRequest):
    feedback = get_feedback_item(feedback_id)
    target_cluster = get_cluster(body.cluster_id)

    # Validate same project
    if feedback.project_id != target_cluster.project_id:
        raise HTTPException(400, "Cannot move items between projects")

    # Validate cluster exists and is not deleted
    if not target_cluster or target_cluster.deleted:
        raise HTTPException(404, "Target cluster not found")

    # ... perform move ...
```

---

## Performance Considerations

### Batch Operations

**Challenge**: Moving 100+ items individually = 100+ API calls

**Solution**: Add batch endpoints
```
POST /api/feedback/batch/move
Body: {
  "feedback_ids": ["fb-1", "fb-2", ..., "fb-100"],
  "target_cluster_id": "cluster-456"
}
```

**Implementation**:
- Use Redis pipelines for bulk updates
- Batch Vector DB metadata updates
- Return progress via WebSocket or polling endpoint

### Vector DB Sync

**Challenge**: Upstash Vector metadata updates can be slow

**Solution**: Make async with retry
```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def update_vector_metadata(item_id: str, metadata: dict):
    # Update Vector DB with retry logic
    await vector_client.update(item_id, metadata=metadata)
```

### Cleanup Performance

**Challenge**: Comparing all cluster centroids = O(n²)

**Current**: Uses Vector DB similarity search (efficient)

**Enhancement**: Add progress tracking
```python
@app.post("/api/clusters/cleanup")
async def cleanup_clusters(background_tasks: BackgroundTasks):
    job_id = create_cleanup_job()
    background_tasks.add_task(run_cleanup_with_progress, job_id)
    return {"job_id": job_id, "status": "started"}

async def run_cleanup_with_progress(job_id: str):
    total_clusters = count_clusters()
    for i, cluster in enumerate(get_all_clusters()):
        # ... cleanup logic ...
        update_job_progress(job_id, current=i+1, total=total_clusters)
```

---

## Open Questions

1. **Undo/Redo Support**:
   - Should we allow users to undo manual operations?
   - How long should we keep modification history?
   - What's the UX for reverting a merge or split?

2. **Conflict Resolution**:
   - What happens if two users try to move the same item simultaneously?
   - Should we use optimistic locking (version numbers)?
   - How do we handle Vector DB sync failures?

3. **Bulk Import**:
   - Should we support CSV import for cluster assignments?
   - Format: `feedback_id,cluster_id,locked`
   - Use case: Migrating from external clustering tools

4. **Similarity Thresholds**:
   - Should users be able to adjust the 0.72 clustering threshold per project?
   - What about per-cluster thresholds?
   - UI for testing different thresholds before committing?

5. **Cluster Templates**:
   - Should we support saving cluster configurations as templates?
   - Use case: "Common login errors" template for new projects
   - How do we handle template versioning?

---

## Success Metrics

After implementation, track:

1. **Usage Metrics**:
   - % of clusters that are manually edited
   - Most common manual operation (move, merge, split)
   - Average time from cluster creation to first manual edit
   - Locked cluster ratio

2. **Quality Metrics**:
   - Reduction in duplicate clusters after merge feature launch
   - User satisfaction scores (survey)
   - Support tickets related to clustering issues
   - False positive rate (items moved out of auto-clusters)

3. **Performance Metrics**:
   - Average time to move item between clusters
   - Merge operation duration (P50, P95, P99)
   - Split operation duration
   - Cleanup job duration

4. **Health Metrics**:
   - Redis-Vector DB sync failures per day
   - Data consistency validation errors
   - API error rates for new endpoints

---

## Conclusion

Soulcaster's clustering algorithm has a **solid foundation** for manual edit support:
- ✅ Incremental clustering naturally preserves manual changes
- ✅ Backend storage layer supports required operations
- ✅ Vector DB architecture enables efficient similarity search

**Missing pieces** are primarily in the **user-facing layer**:
- API endpoints to expose existing backend functions
- UI components for intuitive cluster management
- Data model fields to track manual edits and prevent unwanted auto-merging

The proposed enhancements follow a **phased approach**:
1. Start with simple move operations (highest ROI, lowest risk)
2. Add safety mechanisms (lock, delete, validate)
3. Build advanced features (merge, split, audit)
4. Enhance automation (cleanup preview, batch operations)

**Implementation time**: ~5 weeks for full feature set, or pick high-priority phases (1-3) for 2-week MVP.

---

**Next Steps**:
1. Review this plan with stakeholders
2. Prioritize phases based on user feedback
3. Create detailed technical specs for Phase 1
4. Set up feature flag for gradual rollout
5. Design UI mockups for cluster management interfaces

**Questions? Feedback?** Comment on this document or reach out to the engineering team.
