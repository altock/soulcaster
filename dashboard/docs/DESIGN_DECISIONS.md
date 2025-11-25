# Design Decisions

This document captures key architectural and algorithmic decisions for the Soulcaster clustering system.

## Clustering Architecture

### Vector Database vs Centroid Matching

**Decision**: Use Upstash Vector for similarity search instead of storing centroids in Redis.

**Rationale**:
- O(log n) approximate nearest neighbor search vs O(n) centroid comparison
- Scales better as feedback count grows
- Enables richer queries (find similar items, cluster membership by metadata)
- Vector DB handles index optimization automatically

**Trade-offs**:
- Additional service dependency (Upstash Vector)
- Slightly higher latency for single queries (~10-50ms vs ~5ms for small datasets)
- For <1000 items, centroid matching would be fast enough

**Alternatives considered**:
- Pinecone: More features but higher cost
- pgvector: Would require Postgres migration
- In-memory HNSW: No persistence, memory overhead

---

## Embedding Model

### text-embedding-004 (768 dimensions)

**Decision**: Use Google's `text-embedding-004` model with explicit 768-dimensional output.

**Rationale**:
- Already using Gemini for LLM summaries (single API dependency)
- 768 dimensions matches our Upstash Vector index configuration
- `outputDimensionality: 768` ensures consistent dimensions (model default can vary)
- Quality comparable to OpenAI embeddings for this use case
- Cost-effective within Google AI usage

**Note**: We previously tried `gemini-embedding-001` but it was returning 3072 dimensions
which didn't match our index. Switched to `text-embedding-004` with explicit dimension config.

**Trade-offs**:
- OpenAI's `text-embedding-3-small` may have slightly better quality
- Cohere or Voyage might perform better for technical/code content

**When to reconsider**:
- If clustering quality is poor on technical bug reports
- If we need multilingual support (Cohere excels here)
- If we self-host (switch to BGE or E5)

---

## Similarity Threshold

### 0.72 for vector clustering (0.65 for centroid cleanup)

**Config location**: `lib/vector.ts` exports `VECTOR_CLUSTERING_THRESHOLD` (0.72) and `CLEANUP_MERGE_THRESHOLD` (0.65) as the single source of truth.

**Decision**: Use 0.72 cosine similarity threshold for vector-based cluster assignment.
Use 0.65 for centroid-based cleanup/merging (lower because centroids are averages with naturally lower similarity).

**Rationale**:

The PRD suggested 0.80-0.85, but this is too conservative for a **human-in-the-loop triage system**:

| Threshold | Behavior | Best For |
|-----------|----------|----------|
| 0.90+ | Near-duplicates only | Automated deduplication |
| 0.80-0.85 | Tight clusters | Autonomous systems |
| **0.70-0.75** | Broader grouping | **Human triage** |
| 0.60-0.65 | Very loose | Topic modeling |

Key insight: **It's easier for humans to split a broad cluster than to discover missed connections.**

With 0.72:
- Related issues appear together
- Human reviewer can split if too broad
- Fewer "orphan" clusters with single items
- Better signal-to-noise for triage

**Cohesion scoring** compensates: We calculate and display cluster cohesion so humans know when a cluster might need review.

**When to increase threshold**:
- If clusters are consistently too broad
- If automated actions depend on cluster assignment
- If human reviewers complain about noise

---

## Cluster Cohesion Scoring

### Quality Tiers: tight / moderate / loose

**Decision**: Calculate and store cluster cohesion (average pairwise similarity) with quality labels.

**Thresholds**:
- `tight` (>0.85): Items are very similar, clear cluster
- `moderate` (0.70-0.85): Related items, good for triage
- `loose` (<0.70): Broad grouping, consider splitting

**Rationale**:
- Gives humans signal about cluster quality without changing clustering behavior
- Allows aggressive grouping (0.72) while flagging uncertain clusters
- Enables future features: auto-suggest splits, quality dashboards

**Implementation note**: Cohesion is O(n²) for n items in cluster. For large clusters (>50 items), consider sampling.

---

## Storage Model

### Dual Storage: Redis (metadata) + Vector DB (embeddings)

**Decision**: Store cluster metadata in Redis, embeddings in Upstash Vector.

```
Redis:
  cluster:{id}        - Hash with title, summary, status, cohesion
  cluster:items:{id}  - Set of feedback IDs
  feedback:{id}       - Hash with title, body, source

Upstash Vector:
  {id}                - Embedding vector + metadata (clusterId, source)
```

**Rationale**:
- Redis excels at structured data, sets, sorted sets
- Vector DB excels at similarity search
- Keeps existing Redis schema intact
- Vector DB metadata enables cluster-filtered queries

**Trade-offs**:
- Must keep Redis and Vector DB in sync
- Two places to update on cluster assignment changes
- Slightly more complex failure modes

---

## Future Considerations

### Real-time vs Batch Clustering

Current: Batch (manual trigger via API)
Consider: Real-time clustering on ingest

**Pros of real-time**:
- Immediate cluster assignment
- No "unclustered" state
- Better UX for monitoring dashboards

**Cons**:
- Higher latency on ingest
- More complex error handling
- Embedding API rate limits

**Recommendation**: Keep batch for now; add real-time as opt-in later.

### Cluster Merging/Splitting

Current: Manual via cleanup endpoint
Consider: Automated merge suggestions

Would require:
- Periodic job to find similar cluster centroids
- UI for merge/split approval
- Audit trail for cluster changes

---

## Changelog

| Date | Decision | Author |
|------|----------|--------|
| 2025-11-24 | Initial vector DB implementation | Claude |
| 2025-11-24 | Changed threshold from 0.82 to 0.72 | Claude |
| 2025-11-24 | Added cohesion scoring | Claude |
| 2025-11-25 | Switched from gemini-embedding-001 to text-embedding-004 | Claude |
