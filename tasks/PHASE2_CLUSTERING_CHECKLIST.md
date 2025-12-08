# Phase 2: Clustering Pipeline - Immediate Action Checklist

**Goal:** Build robust clustering that groups similar feedback into actionable clusters.

**Worktree:** `system-readiness` or `main`  
**Estimated Time:** 4-6 days  
**Priority:** 🔥 CRITICAL (Your core value prop)

**Prerequisites:** Phase 1 complete (feedback:unclustered exists and populated)

---

## Day 1: Embedding Generation

### Morning (3-4 hours)

#### Setup Embedding Provider
- [ ] **Choose provider:** Gemini (free tier) vs OpenAI (better quality)
  ```bash
  # Test Gemini
  curl https://generativelanguage.googleapis.com/v1/models \
    -H "x-goog-api-key: $GEMINI_API_KEY"
  ```
- [ ] **Open: `dashboard/lib/vector.ts` (or `backend/embeddings.py` if backend-side)**
  - [ ] Find or create `generateEmbedding(text: string)` function
  - [ ] Verify it returns `number[]` of consistent dimension (e.g., 768 or 1536)
  - [ ] Add error handling for rate limits
  - [ ] Add retry logic with exponential backoff

#### Test Embedding Function
- [ ] **Create: `dashboard/__tests__/lib/vector.test.ts`**
  ```typescript
  describe('generateEmbedding', () => {
    it('should return embedding vector of correct dimension', async () => {
      const text = "Division by zero error in math_ops";
      const embedding = await generateEmbedding(text);
      expect(embedding).toHaveLength(768); // or 1536
      expect(embedding[0]).toBeTypeOf('number');
    });
    
    it('should handle empty text', async () => {
      await expect(generateEmbedding('')).rejects.toThrow();
    });
  });
  ```
- [ ] **Run test:** `npm run test --prefix dashboard -- vector.test.ts`

### Afternoon (3-4 hours)

#### Batch Embedding Generation
- [ ] **Add function to process multiple items:**
  ```typescript
  export async function generateEmbeddingsForFeedback(
    feedbackIds: string[]
  ): Promise<Map<string, number[]>> {
    const embeddings = new Map();
    
    // Process in batches to respect rate limits
    const BATCH_SIZE = 5;
    for (let i = 0; i < feedbackIds.length; i += BATCH_SIZE) {
      const batch = feedbackIds.slice(i, i + BATCH_SIZE);
      const results = await Promise.all(
        batch.map(async (id) => {
          const item = await getFeedbackItem(id);
          const embedding = await generateEmbedding(item.raw_text);
          return [id, embedding];
        })
      );
      results.forEach(([id, emb]) => embeddings.set(id, emb));
      
      // Rate limit pause
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    
    return embeddings;
  }
  ```

#### Store Embeddings
- [ ] **Choose storage:** Upstash Vector (recommended) or Redis + separate vectors
- [ ] **If Upstash Vector:**
  - [ ] Configure in `.env.local`: `UPSTASH_VECTOR_REST_URL`, `UPSTASH_VECTOR_REST_TOKEN`
  - [ ] Add upsert function:
    ```typescript
    export async function upsertFeedbackEmbedding(
      feedbackId: string,
      embedding: number[],
      metadata: object
    ) {
      const index = new Index({
        url: process.env.UPSTASH_VECTOR_REST_URL!,
        token: process.env.UPSTASH_VECTOR_REST_TOKEN!,
      });
      
      await index.upsert({
        id: feedbackId,
        vector: embedding,
        metadata: metadata,
      });
    }
    ```

#### Test Batch Processing
- [ ] **Manual test:**
  ```bash
  # In terminal
  cd dashboard
  node -e "
    const { generateEmbeddingsForFeedback } = require('./lib/vector.ts');
    const ids = ['test-id-1', 'test-id-2'];
    generateEmbeddingsForFeedback(ids).then(console.log);
  "
  ```

---

## Day 2: Similarity & Clustering Algorithm

### Morning (3-4 hours)

#### Implement Cosine Similarity
- [ ] **Open: `dashboard/lib/clustering.ts`**
  ```typescript
  function cosineSimilarity(a: number[], b: number[]): number {
    if (a.length !== b.length) {
      throw new Error('Vectors must have same dimension');
    }
    
    let dotProduct = 0;
    let magA = 0;
    let magB = 0;
    
    for (let i = 0; i < a.length; i++) {
      dotProduct += a[i] * b[i];
      magA += a[i] * a[i];
      magB += b[i] * b[i];
    }
    
    return dotProduct / (Math.sqrt(magA) * Math.sqrt(magB));
  }
  ```
- [ ] **Test similarity function:**
  ```typescript
  // dashboard/__tests__/lib/clustering.test.ts
  describe('cosineSimilarity', () => {
    it('should return 1.0 for identical vectors', () => {
      const v = [1, 0, 0];
      expect(cosineSimilarity(v, v)).toBeCloseTo(1.0);
    });
    
    it('should return 0.0 for orthogonal vectors', () => {
      expect(cosineSimilarity([1, 0], [0, 1])).toBeCloseTo(0.0);
    });
  });
  ```

#### Implement Clustering Algorithm
- [ ] **Choose algorithm:** DBSCAN (density-based) or hierarchical agglomerative
- [ ] **Add to `dashboard/lib/clustering.ts`:**
  ```typescript
  export async function clusterFeedback(
    feedbackIds: string[],
    similarityThreshold: number = 0.75,
    minClusterSize: number = 2
  ): Promise<Cluster[]> {
    // 1. Load embeddings for all feedback
    const embeddings = await getEmbeddings(feedbackIds);
    
    // 2. Build similarity matrix
    const similarities: Map<string, Map<string, number>> = new Map();
    for (const id1 of feedbackIds) {
      similarities.set(id1, new Map());
      for (const id2 of feedbackIds) {
        if (id1 !== id2) {
          const sim = cosineSimilarity(embeddings[id1], embeddings[id2]);
          if (sim >= similarityThreshold) {
            similarities.get(id1)!.set(id2, sim);
          }
        }
      }
    }
    
    // 3. Form clusters (simple connected components)
    const visited = new Set<string>();
    const clusters: Cluster[] = [];
    
    for (const feedbackId of feedbackIds) {
      if (visited.has(feedbackId)) continue;
      
      // BFS to find connected component
      const cluster = new Set<string>();
      const queue = [feedbackId];
      
      while (queue.length > 0) {
        const current = queue.shift()!;
        if (visited.has(current)) continue;
        
        visited.add(current);
        cluster.add(current);
        
        const neighbors = similarities.get(current) || new Map();
        for (const neighbor of neighbors.keys()) {
          if (!visited.has(neighbor)) {
            queue.push(neighbor);
          }
        }
      }
      
      // Only create cluster if meets min size
      if (cluster.size >= minClusterSize) {
        clusters.push(await createCluster(Array.from(cluster)));
      }
    }
    
    return clusters;
  }
  ```

### Afternoon (3-4 hours)

#### Create Cluster Data Structure
- [ ] **Open: `dashboard/types/index.ts`**
  ```typescript
  export interface Cluster {
    id: string;
    title: string;
    description: string;
    feedback_ids: string[];
    created_at: string;
    status: 'open' | 'fixing' | 'fixed';
    representative_text?: string;
    job_id?: string;
    pr_url?: string;
  }
  ```

#### Store Clusters in Redis
- [ ] **Add to `dashboard/lib/redis.ts` or `dashboard/lib/clustering.ts`:**
  ```typescript
  async function createCluster(feedbackIds: string[]): Promise<Cluster> {
    const clusterId = uuidv4();
    
    // Load feedback items to generate cluster summary
    const items = await Promise.all(
      feedbackIds.map(id => getFeedbackItem(id))
    );
    
    // Generate cluster title (use most common keywords or LLM)
    const title = await generateClusterTitle(items);
    const description = await generateClusterDescription(items);
    
    const cluster: Cluster = {
      id: clusterId,
      title,
      description,
      feedback_ids: feedbackIds,
      created_at: new Date().toISOString(),
      status: 'open',
      representative_text: items[0].raw_text, // First item as representative
    };
    
    // Store in Redis
    const redis = await getRedis();
    await redis.hset(`cluster:${clusterId}`, cluster);
    await redis.sadd('clusters:all', clusterId);
    
    // Update feedback items with cluster_id
    for (const feedbackId of feedbackIds) {
      await redis.hset(`feedback:${feedbackId}`, 'cluster_id', clusterId);
      await redis.srem('feedback:unclustered', feedbackId);
    }
    
    return cluster;
  }
  ```

#### Test Clustering
- [ ] **Create: `dashboard/__tests__/lib/clustering.test.ts`**
  ```typescript
  describe('clusterFeedback', () => {
    it('should group similar feedback items', async () => {
      // Create test feedback with similar text
      const id1 = await createTestFeedback("Division by zero error");
      const id2 = await createTestFeedback("ZeroDivisionError in divide");
      const id3 = await createTestFeedback("App crashes when dividing by 0");
      
      const clusters = await clusterFeedback([id1, id2, id3], 0.7, 2);
      
      expect(clusters.length).toBeGreaterThan(0);
      expect(clusters[0].feedback_ids.length).toBeGreaterThanOrEqual(2);
    });
  });
  ```

---

## Day 3: API Endpoints & Dashboard Integration

### Morning (3-4 hours)

#### Create Clustering API Route
- [ ] **Create: `dashboard/app/api/clusters/run/route.ts`**
  ```typescript
  export async function POST(req: Request) {
    try {
      // 1. Get unclustered feedback
      const unclusteredIds = await getUnclusteredFeedbackIds();
      
      if (unclusteredIds.length === 0) {
        return Response.json({ message: 'No unclustered feedback', clusters: [] });
      }
      
      // 2. Generate embeddings
      console.log(`Generating embeddings for ${unclusteredIds.length} items...`);
      const embeddings = await generateEmbeddingsForFeedback(unclusteredIds);
      
      // 3. Store embeddings
      for (const [id, embedding] of embeddings) {
        const item = await getFeedbackItem(id);
        await upsertFeedbackEmbedding(id, embedding, {
          source: item.source,
          created_at: item.created_at,
        });
      }
      
      // 4. Run clustering
      console.log('Running clustering algorithm...');
      const clusters = await clusterFeedback(unclusteredIds);
      
      console.log(`Created ${clusters.length} clusters`);
      
      return Response.json({
        message: `Created ${clusters.length} clusters from ${unclusteredIds.length} items`,
        clusters: clusters,
      });
      
    } catch (error) {
      console.error('Clustering error:', error);
      return Response.json({ error: error.message }, { status: 500 });
    }
  }
  ```

#### List Clusters Endpoint
- [ ] **Create: `dashboard/app/api/clusters/route.ts`**
  ```typescript
  export async function GET(req: Request) {
    const redis = await getRedis();
    const clusterIds = await redis.smembers('clusters:all');
    
    const clusters = await Promise.all(
      clusterIds.map(async (id) => {
        const data = await redis.hgetall(`cluster:${id}`);
        return {
          ...data,
          feedback_ids: JSON.parse(data.feedback_ids || '[]'),
        };
      })
    );
    
    // Sort by created_at descending
    clusters.sort((a, b) => 
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
    
    return Response.json({ clusters });
  }
  ```

### Afternoon (3-4 hours)

#### Update Dashboard UI
- [ ] **Open: `dashboard/app/clusters/page.tsx`**
  - [ ] Add "Run Clustering" button
  - [ ] Show clustering progress/status
  - [ ] Display created clusters
  - [ ] Add link to cluster detail page

- [ ] **Example UI:**
  ```tsx
  export default function ClustersPage() {
    const [clusters, setClusters] = useState([]);
    const [loading, setLoading] = useState(false);
    
    async function runClustering() {
      setLoading(true);
      try {
        const res = await fetch('/api/clusters/run', { method: 'POST' });
        const data = await res.json();
        setClusters(data.clusters);
      } finally {
        setLoading(false);
      }
    }
    
    return (
      <div>
        <button onClick={runClustering} disabled={loading}>
          {loading ? 'Clustering...' : 'Run Clustering'}
        </button>
        
        <div className="clusters-list">
          {clusters.map(cluster => (
            <ClusterCard key={cluster.id} cluster={cluster} />
          ))}
        </div>
      </div>
    );
  }
  ```

#### Manual Testing
- [ ] **Start servers:**
  ```bash
  # Backend (if needed)
  cd backend && uvicorn main:app --reload --port 8000
  
  # Dashboard
  cd dashboard && npm run dev
  ```

- [ ] **Test flow:**
  1. Go to http://localhost:3000/clusters
  2. Click "Run Clustering"
  3. Verify clusters appear
  4. Check Redis: `redis-cli SMEMBERS clusters:all`

---

## Day 4: Cluster Quality & Tuning

### Morning (3-4 hours)

#### Add Clustering Metrics
- [ ] **Create: `dashboard/lib/clustering_metrics.ts`**
  ```typescript
  export function calculateClusterQuality(cluster: Cluster): {
    coherence: number;
    separation: number;
    silhouette: number;
  } {
    // Implement silhouette score or other quality metrics
    // Return values 0-1 where higher is better
  }
  ```

#### Visualize Similarity
- [ ] **Add endpoint: `dashboard/app/api/clusters/[id]/similarity/route.ts`**
  ```typescript
  export async function GET(req: Request, { params }) {
    const clusterId = params.id;
    const cluster = await getCluster(clusterId);
    
    // Calculate pairwise similarities within cluster
    const similarities = [];
    for (let i = 0; i < cluster.feedback_ids.length; i++) {
      for (let j = i + 1; j < cluster.feedback_ids.length; j++) {
        const sim = await calculateSimilarity(
          cluster.feedback_ids[i],
          cluster.feedback_ids[j]
        );
        similarities.push({ i, j, similarity: sim });
      }
    }
    
    return Response.json({ similarities });
  }
  ```

### Afternoon (3-4 hours)

#### Tune Clustering Parameters
- [ ] **Create tuning script: `scripts/tune_clustering.ts`**
  ```typescript
  // Test different thresholds and min cluster sizes
  const thresholds = [0.6, 0.7, 0.75, 0.8, 0.85];
  const minSizes = [2, 3, 4, 5];
  
  for (const threshold of thresholds) {
    for (const minSize of minSizes) {
      const clusters = await clusterFeedback(feedbackIds, threshold, minSize);
      console.log(`Threshold=${threshold}, MinSize=${minSize}:`);
      console.log(`  Clusters: ${clusters.length}`);
      console.log(`  Avg size: ${avgClusterSize(clusters)}`);
      console.log(`  Quality: ${avgClusterQuality(clusters)}`);
    }
  }
  ```

- [ ] **Run tuning:** `npx tsx scripts/tune_clustering.ts`
- [ ] **Document optimal parameters** in `documentation/clustering_tuning.md`

#### Handle Edge Cases
- [ ] **Test with:**
  - [ ] 0 unclustered items (should return empty)
  - [ ] 1 item (should not create cluster)
  - [ ] All dissimilar items (no clusters)
  - [ ] All identical items (one large cluster)
  - [ ] Mixed languages/encodings

---

## Day 5: Documentation & PR

### Tasks

#### Update Documentation
- [ ] **Create: `documentation/clustering_algorithm.md`**
  - [ ] Explain similarity threshold
  - [ ] Explain min cluster size
  - [ ] Document cluster lifecycle
  - [ ] Add diagrams (Mermaid or ASCII)

- [ ] **Update: `documentation/db_design.md`**
  - [ ] Document `cluster:*` keys
  - [ ] Document `clusters:all` set
  - [ ] Document embedding storage (Upstash Vector keys)

#### Add Logging
- [ ] **Add to all clustering functions:**
  ```typescript
  console.log('[Clustering] Starting...', {
    unclustered_count: unclusteredIds.length,
    threshold: similarityThreshold,
    min_size: minClusterSize,
  });
  
  console.log('[Clustering] Complete', {
    clusters_created: clusters.length,
    items_clustered: totalItemsClustered,
    items_remaining_unclustered: remainingUnclustered,
    duration_ms: duration,
  });
  ```

#### Run Full Test Suite
- [ ] **Backend:**
  ```bash
  cd backend
  pytest tests/test_clustering.py -v
  ```

- [ ] **Dashboard:**
  ```bash
  cd dashboard
  npm run test -- clustering.test.ts vector.test.ts
  ```

- [ ] **Coverage check:**
  ```bash
  npm run test -- --coverage
  # Aim for >75% on new code
  ```

#### Manual Smoke Test
- [ ] Generate test data: `python scripts/generate_enhanced_test_data.py ...`
- [ ] Ingest issues: `curl -X POST .../ingest/github/repo/...`
- [ ] Run clustering: Dashboard UI or `curl -X POST .../api/clusters/run`
- [ ] Verify clusters: `curl .../api/clusters`
- [ ] Check Redis:
  ```bash
  redis-cli
  > SMEMBERS clusters:all
  > HGETALL cluster:{some-id}
  ```

#### Commit and PR
```bash
cd worktrees/system-readiness  # or main branch
git add -A
git commit -m "feat: implement clustering pipeline with embeddings

- Add embedding generation with Gemini/OpenAI
- Implement cosine similarity and clustering algorithm
- Create cluster API endpoints (run, list, detail)
- Store clusters in Redis with proper key structure
- Add clustering metrics and tuning scripts
- Update documentation with algorithm details

Refs: tasks/PHASE2_CLUSTERING_CHECKLIST.md"

git push origin phase2-clustering
# Create PR on GitHub
```

---

## Acceptance Criteria (Phase 2 Complete)

Before moving to Phase 3 (Coding Agent Integration), verify:

- ✅ **Embeddings generate successfully**
  - Test: Generate embeddings for 10 feedback items
  - Verify: All return vectors of correct dimension

- ✅ **Clustering creates meaningful groups**
  - Test: Run on test data with known bug clusters
  - Verify: Similar bugs cluster together, noise is separate

- ✅ **API endpoints work**
  - Test: `POST /api/clusters/run` returns clusters
  - Test: `GET /api/clusters` lists all clusters
  - Test: `GET /api/clusters/[id]` returns cluster details

- ✅ **Dashboard UI shows clusters**
  - Test: Click "Run Clustering" button
  - Verify: Clusters appear in UI
  - Verify: Can click through to cluster detail page

- ✅ **Redis keys are correct**
  - Test: Check `clusters:all` set exists
  - Test: Check `cluster:{id}` hashes have all fields
  - Test: Feedback items have `cluster_id` field
  - Test: Clustered items removed from `feedback:unclustered`

- ✅ **Tests pass**
  - Run: `npm run test --prefix dashboard`
  - Coverage: >75% on clustering code

- ✅ **Documentation complete**
  - `documentation/clustering_algorithm.md` exists
  - `documentation/db_design.md` updated with cluster keys

---

## Common Issues & Solutions

### Issue: "Embeddings are slow"
**Solution:** 
- Batch requests (5-10 at a time)
- Add caching (store embeddings in Redis)
- Use parallel processing where possible

### Issue: "Too many tiny clusters"
**Solution:**
- Increase `minClusterSize` (try 3 or 4)
- Increase `similarityThreshold` (try 0.8 or 0.85)
- Consider using hierarchical clustering with merge step

### Issue: "Everything clusters together"
**Solution:**
- Decrease `similarityThreshold` (try 0.65 or 0.7)
- Improve text normalization (remove stop words, etc.)
- Check embedding quality (are they all similar?)

### Issue: "Out of memory during clustering"
**Solution:**
- Process in batches (don't load all embeddings at once)
- Use sparse similarity matrix (only store edges > threshold)
- Stream results instead of holding in memory

---

## After Phase 2: Next Steps

1. **Phase 3: Coding Agent Integration**
   - Trigger agent from cluster detail page
   - Track job status in real-time
   - Display PR link when complete

2. **Optimize Clustering**
   - Add incremental clustering (process new items only)
   - Implement cluster merging (combine similar clusters)
   - Add user feedback loop (thumbs up/down on clusters)

3. **Analytics**
   - Track clustering accuracy over time
   - Measure which clusters convert to PRs
   - Identify patterns in noise vs signal
