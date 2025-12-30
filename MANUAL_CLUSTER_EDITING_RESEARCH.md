# Manual Cluster Editing - Research & Implementation Guide

**Status**: Research completed, implementation pending
**Last Updated**: 2025-12-30
**Priority**: Phase 1 (low-medium) - start after vector DB clustering is merged to main

## Overview

This document captures comprehensive research on user workflows, UX patterns, and implementation strategies for manual cluster editing in Soulcaster. The research covers data loss prevention, conflict resolution with automated clustering, vector DB consistency, and API design.

## Key Findings Summary

### 1. Priority Operations (in order of importance)

1. **Reassign Items** - Move feedback items between clusters (Medium priority)
2. **Merge Clusters** - Consolidate duplicates (High priority)
3. **Remove Items** - Isolate misclassified items (Medium priority)
4. **Split Clusters** - Separate divergent discussions (Low-Medium priority)

### 2. Critical Constraints

- **Conflict Prevention**: Lock-based mechanism needed to prevent manual edits during automated clustering
- **Centroid Consistency**: Vector DB centroids must be recomputed after every manual edit
- **Audit Trail**: Track all manual changes with user attribution, timestamp, before/after state
- **Data Loss Prevention**: Implement soft-delete with 24-hour undo window for destructive operations

### 3. Implementation Phases

| Phase | Features | Complexity | Timeline | Benefits |
|-------|----------|-----------|----------|----------|
| **Phase 1** | Reassign item, Remove item | Low-Medium | 1-2 weeks | Basic triage corrections |
| **Phase 2** | Merge clusters, Edit locks | Medium | 2-3 weeks | Duplicate cleanup, conflict prevention |
| **Phase 3** | Split clusters, Undo window | Medium-High | 3-4 weeks | Power-user curation |
| **Phase 4** | RBAC, Approval workflows | High | 3-4 weeks | Enterprise governance |

## Detailed Recommendations

### Vector DB Consistency Strategy

**Critical Decision**: When to recompute centroids?

- **Immediate recomputation** (Recommended):
  - Merge: 2-3 Vector DB API calls, 50-100ms latency
  - Reassign: 3-4 API calls, 100-200ms latency
  - Remove: 1-2 API calls, 50-100ms latency
  - Split: 2-3 API calls, 150-300ms latency
  - Benefit: Clustering queries always find accurate neighbors

- **Deferred recomputation** (Not recommended):
  - Update Redis immediately, batch Vector DB updates nightly
  - Risk: Clustering may find items in "wrong" clusters for 24 hours
  - Could create inconsistent clustering results

**Recommended approach**: Recompute immediately, accept latency cost for accuracy.

### Conflict Prevention with Automated Clustering

**When user edits during active clustering**:

Option A: **Queue manual edits** (User-friendly)
- Show warning: "Clustering in progress. Your edits will be applied after clustering finishes."
- User doesn't block; edits execute after clustering job completes
- Risk: User may not realize their edits were delayed

Option B: **Block edits entirely** (Conservative)
- Show message: "Wait for clustering to complete before editing (Est. 30 seconds)"
- Force user to wait or try again later
- Risk: Friction for power users during peak clustering times

Option C: **Cluster edit locks** (Hybrid)
- Acquire cluster-level lock when user starts editing
- Clustering checks lock; if locked, skips that cluster
- Allows partial clustering of other clusters
- Recommended for multi-cluster projects

### Audit Trail Implementation

**Minimum fields to track**:
```python
{
  "id": "uuid",
  "timestamp": "2025-12-30T14:30:00Z",
  "user_id": "uuid",
  "action_type": "merge" | "split" | "reassign_item" | "remove_item",
  "cluster_id": "string",
  "before_state": {...},  # snapshot
  "after_state": {...},   # snapshot
  "affected_item_ids": ["id1", "id2"],
  "reason": "optional user note",
  "is_undone": false
}
```

**Storage location**: Redis sorted set by timestamp
```
edit_audit_log:{project_id}
  score: unix_timestamp
  member: json_encoded_audit_entry
```

### New API Endpoints

See full specification in section below. Key endpoints:

- `POST /clusters/{id}/reassign-item` - Move item to different cluster
- `POST /clusters/{id}/remove-item` - Remove item from cluster
- `POST /clusters/{source_id}/merge` - Merge two clusters
- `POST /clusters/{id}/split` - Split cluster into two
- `GET /clusters/{id}/audit-log` - View edit history
- `POST /clusters/{id}/undo` - Undo previous operation

## API Specification

### POST /clusters/{id}/reassign-item

Move a feedback item from one cluster to another.

**Request**:
```json
{
  "feedback_id": "uuid",
  "destination_cluster_id": "string",
  "reason": "optional user-provided reason"
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "source_cluster": {
    "id": "...",
    "title": "...",
    "feedback_ids": [...]
  },
  "destination_cluster": {
    "id": "...",
    "title": "...",
    "feedback_ids": [...]
  },
  "audit_log_id": "string"
}
```

**Errors**:
- 404: Cluster or feedback item not found
- 409: Cluster currently being edited or clustering in progress
- 423: Lock conflict (another user editing)

---

### POST /clusters/{id}/remove-item

Remove item from cluster (soft delete to unclustered state).

**Request**:
```json
{
  "feedback_id": "uuid",
  "reason": "optional"
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "cluster": {
    "id": "...",
    "feedback_ids": [...]
  },
  "item_moved_to": "unclustered",
  "audit_log_id": "string"
}
```

---

### POST /clusters/{source_id}/merge

Merge source cluster into destination cluster.

**Request**:
```json
{
  "destination_cluster_id": "string",
  "confirm": true
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "kept_cluster_id": "string",
  "deleted_cluster_id": "string",
  "merged_items_count": 42,
  "audit_log_id": "string"
}
```

**Conflict handling**:
- 409: Clustering in progress - merge queued after clustering
- 423: Cluster locked by another user

---

### POST /clusters/{id}/split

Split cluster: move specified items to new cluster.

**Request**:
```json
{
  "split_item_ids": ["id1", "id2"],
  "new_cluster_title": "optional title",
  "confirm": true
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "old_cluster_id": "string",
  "new_cluster_id": "string",
  "audit_log_id": "string"
}
```

---

### GET /clusters/{id}/audit-log

View change history for a cluster.

**Query params**: `?limit=50&offset=0&action_type=merge`

**Response** (200 OK):
```json
{
  "logs": [
    {
      "id": "uuid",
      "timestamp": "2025-12-26T10:30:00Z",
      "user_id": "uuid",
      "action": "merge",
      "before": {...},
      "after": {...},
      "reason": "Duplicate of cluster X",
      "is_undone": false
    }
  ],
  "total_count": 147
}
```

---

### POST /clusters/{id}/undo

Undo a previous operation (24-hour window).

**Request**:
```json
{
  "audit_log_id": "string"
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "cluster": {...},
  "reverted_changes": {...}
}
```

**Errors**:
- 410: Undo window expired (>24 hours)
- 409: Cluster modified after target operation

## Stashed Work

A stash entry contains research context and dashboard configuration changes:
```bash
git stash pop # or git stash show -p
```

## Next Steps

1. **Decide on conflict prevention strategy** (Queue vs Block vs Locks)
2. **Choose audit storage** (Redis sorted set vs PostgreSQL)
3. **Implement Phase 1** (reassign + remove)
4. **Add E2E tests** for manual edit workflows
5. **Dashboard UI** for cluster editing (reassign, remove, merge UI)

## References

- **Industry patterns**: Linear Triage, Jira, GitHub issue management, Zendesk
- **Locking strategy**: Redis distributed locks (already used for clustering jobs)
- **Audit best practices**: MyData 2025 standards, HIPAA audit trail requirements
- **Vector DB consistency**: Weaviate centroid documentation, eventual consistency patterns

## Related PRs/Issues

- **Main feature branch**: `feature/impl-vector-clustering` (clustering with audit trail)
- **Research documents**:
  - `CLUSTERING_ANALYSIS.md`
  - `CLUSTERING_RESEARCH.md`
  - `UPSTASH_VECTOR_OPTIMIZATION_GUIDE.md`

---

**Owner**: Claude Code
**Reviewed by**: (pending)
