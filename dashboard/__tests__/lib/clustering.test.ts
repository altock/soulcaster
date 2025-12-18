/**
 * Tests for clustering logic
 *
 * These tests follow TDD principles - we write tests for the behavior we want,
 * then implement the optimizations to make them pass.
 */

import type { FeedbackItem } from '@/types';
import type { ClusterData } from '@/lib/clustering';

// Mock the Google GenAI module
jest.mock('@google/genai', () => ({
  GoogleGenAI: jest.fn().mockImplementation(() => ({
    models: {
      embedContent: jest.fn(),
      generateContent: jest.fn(),
    },
  })),
}));

// Import after mocking
import { cosineSimilarity, calculateCentroid, findBestCluster, ClusteringBatch } from '@/lib/clustering';

describe('Clustering Pure Functions', () => {
  describe('cosineSimilarity', () => {
    it('should return 1 for identical vectors', () => {
      const vec = [1, 2, 3, 4, 5];
      expect(cosineSimilarity(vec, vec)).toBeCloseTo(1.0);
    });

    it('should return 0 for orthogonal vectors', () => {
      const vec1 = [1, 0, 0];
      const vec2 = [0, 1, 0];
      expect(cosineSimilarity(vec1, vec2)).toBeCloseTo(0.0);
    });

    it('should return -1 for opposite vectors', () => {
      const vec1 = [1, 2, 3];
      const vec2 = [-1, -2, -3];
      expect(cosineSimilarity(vec1, vec2)).toBeCloseTo(-1.0);
    });

    it('should handle zero vectors gracefully', () => {
      const vec1 = [0, 0, 0];
      const vec2 = [1, 2, 3];
      expect(cosineSimilarity(vec1, vec2)).toBe(0);
    });

    it('should return 0 for mismatched dimensions', () => {
      const vec1 = [1, 2, 3];
      const vec2 = [1, 2];
      expect(cosineSimilarity(vec1, vec2)).toBe(0);
    });

    it('should handle normalized vectors correctly', () => {
      // Two normalized vectors at 60 degrees should have similarity ~0.5
      const vec1 = [1, 0];
      const vec2 = [0.5, Math.sqrt(3) / 2]; // 60 degrees from vec1
      expect(cosineSimilarity(vec1, vec2)).toBeCloseTo(0.5, 5);
    });
  });

  describe('calculateCentroid', () => {
    it('should return empty array for no embeddings', () => {
      expect(calculateCentroid([])).toEqual([]);
    });

    it('should return the same vector for single embedding', () => {
      const embedding = [1, 2, 3, 4, 5];
      expect(calculateCentroid([embedding])).toEqual(embedding);
    });

    it('should calculate mean of multiple embeddings', () => {
      const embeddings = [
        [1, 2, 3],
        [3, 4, 5],
        [5, 6, 7],
      ];
      // Mean: [(1+3+5)/3, (2+4+6)/3, (3+5+7)/3] = [3, 4, 5]
      expect(calculateCentroid(embeddings)).toEqual([3, 4, 5]);
    });

    it('should handle embeddings with negative values', () => {
      const embeddings = [
        [-1, 0, 1],
        [1, 0, -1],
      ];
      expect(calculateCentroid(embeddings)).toEqual([0, 0, 0]);
    });

    it('should skip embeddings with mismatched dimensions', () => {
      const embeddings = [
        [1, 2, 3],
        [4, 5], // Wrong dimension, should be skipped
        [7, 8, 9],
      ];
      // Should only average the first and third: [(1+7)/2, (2+8)/2, (3+9)/2] = [4, 5, 6]
      expect(calculateCentroid(embeddings)).toEqual([4, 5, 6]);
    });
  });

  describe('findBestCluster', () => {
    const createCluster = (id: string, centroid: number[]): ClusterData => ({
      id,
      feedbackIds: [],
      centroid,
    });

    it('should return null for empty clusters list', () => {
      const embedding = [1, 2, 3];
      const result = findBestCluster(embedding, [], 0.5);
      expect(result).toBeNull();
    });

    it('should return null when no cluster meets threshold', () => {
      const embedding = [1, 0, 0];
      const clusters = [
        createCluster('c1', [0, 1, 0]), // orthogonal, similarity = 0
        createCluster('c2', [0, 0, 1]), // orthogonal, similarity = 0
      ];
      const result = findBestCluster(embedding, clusters, 0.5);
      expect(result).toBeNull();
    });

    it('should return best matching cluster above threshold', () => {
      const embedding = [1, 0, 0];
      const clusters = [
        createCluster('c1', [0.9, 0.1, 0]), // similar to embedding
        createCluster('c2', [0, 1, 0]), // orthogonal
      ];
      const result = findBestCluster(embedding, clusters, 0.5);
      expect(result).not.toBeNull();
      expect(result!.clusterId).toBe('c1');
      expect(result!.similarity).toBeGreaterThan(0.5);
    });

    it('should skip clusters with empty centroids', () => {
      const embedding = [1, 2, 3];
      const clusters = [
        createCluster('c1', []), // empty centroid
        createCluster('c2', [1, 2, 3]), // valid
      ];
      const result = findBestCluster(embedding, clusters, 0.5);
      expect(result).not.toBeNull();
      expect(result!.clusterId).toBe('c2');
    });

    it('should return the cluster with highest similarity', () => {
      const embedding = [1, 0, 0];
      const clusters = [
        createCluster('c1', [0.8, 0.2, 0]), // ~0.97 similarity
        createCluster('c2', [0.9, 0.1, 0]), // ~0.99 similarity - best
        createCluster('c3', [0.7, 0.3, 0]), // ~0.92 similarity
      ];
      const result = findBestCluster(embedding, clusters, 0.5);
      expect(result!.clusterId).toBe('c2');
    });
  });
});

describe('ClusteringBatch - Incremental Updates', () => {

  describe('updateCentroidIncremental', () => {
    it('should correctly update centroid with new embedding', () => {
      // Test the incremental centroid formula:
      // newCentroid = (oldCentroid * oldCount + newEmbedding) / (oldCount + 1)
      const oldCentroid = [2, 4, 6]; // from 2 items averaging [1,2,3] and [3,6,9]
      const newEmbedding = [5, 10, 15];
      const oldCount = 2;

      const batch = new ClusteringBatch();
      const newCentroid = batch.updateCentroidIncremental(oldCentroid, newEmbedding, oldCount);

      // Expected: ([2,4,6]*2 + [5,10,15]) / 3 = [4+5, 8+10, 12+15] / 3 = [3, 6, 9]
      expect(newCentroid[0]).toBeCloseTo(3);
      expect(newCentroid[1]).toBeCloseTo(6);
      expect(newCentroid[2]).toBeCloseTo(9);
    });

    it('should handle first item in cluster', () => {
      const oldCentroid: number[] = [];
      const newEmbedding = [1, 2, 3];
      const oldCount = 0;

      const batch = new ClusteringBatch();
      const newCentroid = batch.updateCentroidIncremental(oldCentroid, newEmbedding, oldCount);

      expect(newCentroid).toEqual([1, 2, 3]);
    });
  });

  describe('trackChangedClusters', () => {
    it('should track which clusters have been modified', () => {
      const batch = new ClusteringBatch();

      batch.markClusterChanged('cluster-1');
      batch.markClusterChanged('cluster-2');
      batch.markClusterChanged('cluster-1'); // duplicate

      const changed = batch.getChangedClusterIds();
      expect(changed).toHaveLength(2);
      expect(changed).toContain('cluster-1');
      expect(changed).toContain('cluster-2');
    });

    it('should track new clusters separately', () => {
      const batch = new ClusteringBatch();

      batch.markClusterNew('new-cluster-1');
      batch.markClusterChanged('existing-cluster');
      batch.markClusterNew('new-cluster-2');

      expect(batch.isNewCluster('new-cluster-1')).toBe(true);
      expect(batch.isNewCluster('existing-cluster')).toBe(false);
      expect(batch.getNewClusterIds()).toHaveLength(2);
    });

    it('should only regenerate summaries for changed clusters', () => {
      const batch = new ClusteringBatch();

      // Mark only some clusters as changed
      batch.markClusterChanged('changed-1');
      batch.markClusterNew('new-1');

      const allClusterIds = ['unchanged-1', 'unchanged-2', 'changed-1', 'new-1'];
      const needsSummary = batch.getClustersNeedingSummaryRegeneration(allClusterIds);

      expect(needsSummary).toContain('changed-1');
      expect(needsSummary).toContain('new-1');
      expect(needsSummary).not.toContain('unchanged-1');
      expect(needsSummary).not.toContain('unchanged-2');
      expect(needsSummary).toHaveLength(2);
    });
  });
});

describe('ClusteringBatch - Feedback Caching', () => {
  const createFeedback = (id: string): FeedbackItem => ({
    id,
    source: 'manual',
    title: `Title ${id}`,
    body: `Body ${id}`,
    metadata: {},
    created_at: new Date().toISOString(),
  });

  it('should cache feedback items to avoid re-fetching', () => {
    const batch = new ClusteringBatch();
    const feedback1 = createFeedback('f1');
    const feedback2 = createFeedback('f2');

    batch.cacheFeedbackItem(feedback1);
    batch.cacheFeedbackItem(feedback2);

    expect(batch.getCachedFeedbackItem('f1')).toEqual(feedback1);
    expect(batch.getCachedFeedbackItem('f2')).toEqual(feedback2);
    expect(batch.getCachedFeedbackItem('f3')).toBeUndefined();
  });

  it('should bulk cache feedback items', () => {
    const batch = new ClusteringBatch();
    const items = [createFeedback('f1'), createFeedback('f2'), createFeedback('f3')];

    batch.cacheFeedbackItems(items);

    expect(batch.getCachedFeedbackItem('f1')).toBeDefined();
    expect(batch.getCachedFeedbackItem('f2')).toBeDefined();
    expect(batch.getCachedFeedbackItem('f3')).toBeDefined();
  });

  it('should get multiple cached items at once', () => {
    const batch = new ClusteringBatch();
    const items = [createFeedback('f1'), createFeedback('f2'), createFeedback('f3')];
    batch.cacheFeedbackItems(items);

    const result = batch.getCachedFeedbackItems(['f1', 'f3', 'f4']);

    expect(result.found).toHaveLength(2);
    expect(result.missing).toEqual(['f4']);
  });
});

describe('ClusteringBatch - Redis Operation Batching', () => {
  it('should queue Redis operations for batch execution', () => {
    const batch = new ClusteringBatch();

    batch.queueRedisOperation({ type: 'sadd', key: 'set1', values: ['a', 'b'] });
    batch.queueRedisOperation({ type: 'srem', key: 'set2', values: ['c'] });
    batch.queueRedisOperation({ type: 'hset', key: 'hash1', fields: { x: '1' } });

    const operations = batch.getQueuedOperations();
    expect(operations).toHaveLength(3);
  });

  it('should merge compatible operations on same key', () => {
    const batch = new ClusteringBatch();

    // Multiple sadd operations on same key should merge
    batch.queueRedisOperation({ type: 'sadd', key: 'set1', values: ['a'] });
    batch.queueRedisOperation({ type: 'sadd', key: 'set1', values: ['b', 'c'] });

    const operations = batch.getQueuedOperations();

    // Should be merged into single operation
    const set1Ops = operations.filter((op) => op.key === 'set1' && op.type === 'sadd');
    expect(set1Ops).toHaveLength(1);
    expect(set1Ops[0].values).toContain('a');
    expect(set1Ops[0].values).toContain('b');
    expect(set1Ops[0].values).toContain('c');
  });

  it('should not merge operations on different keys', () => {
    const batch = new ClusteringBatch();

    batch.queueRedisOperation({ type: 'sadd', key: 'set1', values: ['a'] });
    batch.queueRedisOperation({ type: 'sadd', key: 'set2', values: ['b'] });

    const operations = batch.getQueuedOperations();
    expect(operations).toHaveLength(2);
  });

  it('should clear operations after getting them', () => {
    const batch = new ClusteringBatch();

    batch.queueRedisOperation({ type: 'sadd', key: 'set1', values: ['a'] });
    batch.getQueuedOperations();

    expect(batch.getQueuedOperations()).toHaveLength(0);
  });
});

describe('Performance: Cluster Assignment', () => {
  const createCluster = (id: string, centroid: number[]): ClusterData => ({
    id,
    feedbackIds: [],
    centroid,
  });

  it('should assign to correct clusters in batch', () => {
    // Create clusters with distinct centroids
    const clusters = [
      createCluster('tech', [1, 0, 0]), // tech-related
      createCluster('billing', [0, 1, 0]), // billing-related
      createCluster('support', [0, 0, 1]), // support-related
    ];

    // Embeddings that should match each cluster
    const embeddings = [
      { id: 'f1', embedding: [0.9, 0.1, 0] }, // Should match tech
      { id: 'f2', embedding: [0.1, 0.9, 0] }, // Should match billing
      { id: 'f3', embedding: [0.1, 0, 0.9] }, // Should match support
      { id: 'f4', embedding: [0.33, 0.33, 0.33] }, // Ambiguous - may create new cluster
    ];

    const batch = new ClusteringBatch();
    const results = batch.assignToClusters(embeddings, clusters, 0.7);

    // First three should match existing clusters
    const techAssignment = results.find((r) => r.feedbackId === 'f1');
    expect(techAssignment?.clusterId).toBe('tech');
    expect(techAssignment?.isNewCluster).toBe(false);

    const billingAssignment = results.find((r) => r.feedbackId === 'f2');
    expect(billingAssignment?.clusterId).toBe('billing');

    const supportAssignment = results.find((r) => r.feedbackId === 'f3');
    expect(supportAssignment?.clusterId).toBe('support');

    // Fourth might create new cluster due to low similarity
    const ambiguousAssignment = results.find((r) => r.feedbackId === 'f4');
    expect(ambiguousAssignment).toBeDefined();
  });

  it('should maintain cluster state across assignments', () => {
    const clusters = [createCluster('c1', [1, 0, 0])];

    const batch = new ClusteringBatch();

    // First batch of embeddings
    const embeddings1 = [
      { id: 'f1', embedding: [0.95, 0.05, 0] },
      { id: 'f2', embedding: [0, 1, 0] }, // Creates new cluster
    ];

    const results1 = batch.assignToClusters(embeddings1, clusters, 0.8);

    // Find the new cluster created for f2
    const f2Result = results1.find((r) => r.feedbackId === 'f2');
    expect(f2Result?.isNewCluster).toBe(true);

    // Second batch should see the updated cluster state
    const updatedClusters = batch.getUpdatedClusters();
    expect(updatedClusters.length).toBe(2); // original + new
  });
});
