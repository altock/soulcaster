/**
 * Tests for Upstash Vector-based clustering
 *
 * TDD: These tests define the behavior we want from the vector store.
 * The implementation will be built to satisfy these tests.
 */

import type { FeedbackItem } from '@/types';

// Mock the Upstash Vector module
const mockUpsert = jest.fn();
const mockQuery = jest.fn();
const mockDelete = jest.fn();
const mockFetch = jest.fn();
const mockReset = jest.fn();

jest.mock('@upstash/vector', () => ({
  Index: jest.fn().mockImplementation(() => ({
    upsert: mockUpsert,
    query: mockQuery,
    delete: mockDelete,
    fetch: mockFetch,
    reset: mockReset,
  })),
}));

// Mock Gemini for embedding generation
// Must return 768 dimensions to match Upstash Vector index
jest.mock('@google/genai', () => ({
  GoogleGenAI: jest.fn().mockImplementation(() => ({
    models: {
      embedContent: jest.fn().mockResolvedValue({
        // Generate 768-dim embedding inline (jest hoists mocks before variable declarations)
        embeddings: [{ values: Array.from({ length: 768 }, (_, i) => i / 768) }],
      }),
      generateContent: jest.fn().mockResolvedValue({
        text: JSON.stringify({
          cluster_title: 'Test Cluster',
          cluster_description: 'Test description',
          issue_title: 'Test Issue',
          issue_description: 'Test issue description',
        }),
      }),
    },
  })),
}));

// Import after mocking
import {
  VectorStore,
  FeedbackVector,
  SimilarFeedback,
  ClusterAssignment,
} from '@/lib/vector';

describe('VectorStore', () => {
  let vectorStore: VectorStore;

  beforeEach(() => {
    jest.clearAllMocks();
    vectorStore = new VectorStore();
  });

  describe('upsertFeedback', () => {
    it('should store a feedback item with its embedding', async () => {
      const feedbackId = 'feedback-1';
      const embedding = [0.1, 0.2, 0.3, 0.4, 0.5];
      const metadata = {
        title: 'Bug report',
        source: 'reddit' as const,
        clusterId: null,
      };

      mockUpsert.mockResolvedValueOnce({ upsertedCount: 1 });

      await vectorStore.upsertFeedback(feedbackId, embedding, metadata);

      expect(mockUpsert).toHaveBeenCalledWith({
        id: feedbackId,
        vector: embedding,
        metadata: expect.objectContaining({
          title: 'Bug report',
          source: 'reddit',
        }),
      });
    });

    it('should batch upsert multiple feedback items', async () => {
      const items: FeedbackVector[] = [
        {
          id: 'f1',
          embedding: [0.1, 0.2, 0.3],
          metadata: { title: 'Bug 1', source: 'reddit', clusterId: null },
        },
        {
          id: 'f2',
          embedding: [0.4, 0.5, 0.6],
          metadata: { title: 'Bug 2', source: 'manual', clusterId: null },
        },
      ];

      mockUpsert.mockResolvedValueOnce({ upsertedCount: 2 });

      await vectorStore.upsertFeedbackBatch(items);

      expect(mockUpsert).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({ id: 'f1' }),
          expect.objectContaining({ id: 'f2' }),
        ])
      );
    });
  });

  describe('findSimilar', () => {
    it('should find similar feedback items by embedding', async () => {
      const queryEmbedding = [0.1, 0.2, 0.3, 0.4, 0.5];

      mockQuery.mockResolvedValueOnce([
        { id: 'f1', score: 0.95, metadata: { title: 'Similar bug', clusterId: 'c1' } },
        { id: 'f2', score: 0.87, metadata: { title: 'Another bug', clusterId: 'c1' } },
      ]);

      const results = await vectorStore.findSimilar(queryEmbedding, 10);

      expect(mockQuery).toHaveBeenCalledWith({
        vector: queryEmbedding,
        topK: 10,
        includeMetadata: true,
        includeVectors: false,
      });
      expect(results).toHaveLength(2);
      expect(results[0].id).toBe('f1');
      expect(results[0].score).toBe(0.95);
    });

    it('should filter by minimum similarity threshold', async () => {
      const queryEmbedding = [0.1, 0.2, 0.3];

      mockQuery.mockResolvedValueOnce([
        { id: 'f1', score: 0.95, metadata: { clusterId: 'c1' } },
        { id: 'f2', score: 0.70, metadata: { clusterId: 'c2' } },
        { id: 'f3', score: 0.50, metadata: { clusterId: null } },
      ]);

      const results = await vectorStore.findSimilar(queryEmbedding, 10, 0.75);

      // Should only return items above 0.75 threshold
      expect(results).toHaveLength(1);
      expect(results[0].id).toBe('f1');
    });

    it('should exclude specified IDs from results', async () => {
      const queryEmbedding = [0.1, 0.2, 0.3];

      mockQuery.mockResolvedValueOnce([
        { id: 'f1', score: 0.95, metadata: { clusterId: 'c1' } },
        { id: 'f2', score: 0.87, metadata: { clusterId: 'c1' } },
      ]);

      const results = await vectorStore.findSimilar(queryEmbedding, 10, 0, ['f1']);

      expect(results).toHaveLength(1);
      expect(results[0].id).toBe('f2');
    });
  });

  describe('findSimilarInCluster', () => {
    it('should find items similar to query within a specific cluster', async () => {
      const queryEmbedding = [0.1, 0.2, 0.3];

      mockQuery.mockResolvedValueOnce([
        { id: 'f1', score: 0.95, metadata: { clusterId: 'cluster-1' } },
        { id: 'f2', score: 0.87, metadata: { clusterId: 'cluster-2' } },
        { id: 'f3', score: 0.80, metadata: { clusterId: 'cluster-1' } },
      ]);

      const results = await vectorStore.findSimilarInCluster(
        queryEmbedding,
        'cluster-1',
        10
      );

      // Should only return items from cluster-1
      expect(results).toHaveLength(2);
      expect(results.every((r) => r.metadata?.clusterId === 'cluster-1')).toBe(true);
    });
  });

  describe('updateClusterAssignment', () => {
    it('should update the cluster assignment for a feedback item', async () => {
      mockFetch.mockResolvedValueOnce([
        {
          id: 'f1',
          vector: [0.1, 0.2, 0.3],
          metadata: { title: 'Bug', clusterId: null },
        },
      ]);
      mockUpsert.mockResolvedValueOnce({ upsertedCount: 1 });

      await vectorStore.updateClusterAssignment('f1', 'cluster-1');

      expect(mockUpsert).toHaveBeenCalledWith(
        expect.objectContaining({
          id: 'f1',
          metadata: expect.objectContaining({ clusterId: 'cluster-1' }),
        })
      );
    });

    it('should batch update cluster assignments', async () => {
      const assignments: ClusterAssignment[] = [
        { feedbackId: 'f1', clusterId: 'c1' },
        { feedbackId: 'f2', clusterId: 'c1' },
        { feedbackId: 'f3', clusterId: 'c2' },
      ];

      mockFetch.mockResolvedValueOnce([
        { id: 'f1', vector: [0.1], metadata: { title: 'Bug 1' } },
        { id: 'f2', vector: [0.2], metadata: { title: 'Bug 2' } },
        { id: 'f3', vector: [0.3], metadata: { title: 'Bug 3' } },
      ]);
      mockUpsert.mockResolvedValueOnce({ upsertedCount: 3 });

      await vectorStore.updateClusterAssignmentBatch(assignments);

      expect(mockUpsert).toHaveBeenCalled();
    });
  });

  describe('getClusterMembers', () => {
    it('should return all feedback IDs belonging to a cluster', async () => {
      // This would use a metadata filter query
      mockQuery.mockResolvedValueOnce([
        { id: 'f1', score: 1.0, metadata: { clusterId: 'cluster-1' } },
        { id: 'f2', score: 1.0, metadata: { clusterId: 'cluster-1' } },
      ]);

      const members = await vectorStore.getClusterMembers('cluster-1');

      expect(members).toContain('f1');
      expect(members).toContain('f2');
      expect(members).toHaveLength(2);
    });
  });

  describe('deleteFeedback', () => {
    it('should delete a feedback item from the vector store', async () => {
      mockDelete.mockResolvedValueOnce({ deleted: 1 });

      await vectorStore.deleteFeedback('f1');

      expect(mockDelete).toHaveBeenCalledWith('f1');
    });

    it('should batch delete multiple feedback items', async () => {
      mockDelete.mockResolvedValueOnce({ deleted: 3 });

      await vectorStore.deleteFeedbackBatch(['f1', 'f2', 'f3']);

      expect(mockDelete).toHaveBeenCalledWith(['f1', 'f2', 'f3']);
    });
  });
});

describe('Vector-Based Clustering', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Import after mocks are set up
  const { clusterWithVectorDB } = require('@/lib/vector');

  describe('clusterWithVectorDB', () => {
    it('should assign feedback to existing cluster when similarity is high', async () => {
      // Mock finding a similar item that's already clustered
      mockQuery.mockResolvedValueOnce([
        {
          id: 'existing-1',
          score: 0.92,
          metadata: { clusterId: 'cluster-1', title: 'Similar bug' },
        },
      ]);

      const feedback: FeedbackItem = {
        id: 'new-feedback',
        source: 'reddit',
        title: 'Bug report',
        body: 'Something is broken',
        metadata: {},
        created_at: new Date().toISOString(),
      };

      const result = await clusterWithVectorDB(feedback, [0.1, 0.2, 0.3], 0.82);

      expect(result.clusterId).toBe('cluster-1');
      expect(result.isNewCluster).toBe(false);
      expect(result.similarity).toBeGreaterThanOrEqual(0.82);
    });

    it('should create new cluster when no similar items exist', async () => {
      // Mock finding no similar items above threshold
      mockQuery.mockResolvedValueOnce([
        { id: 'existing-1', score: 0.50, metadata: { clusterId: 'cluster-1' } },
      ]);

      const feedback: FeedbackItem = {
        id: 'new-feedback',
        source: 'reddit',
        title: 'Unique bug',
        body: 'Never seen before',
        metadata: {},
        created_at: new Date().toISOString(),
      };

      const result = await clusterWithVectorDB(feedback, [0.9, 0.9, 0.9], 0.82);

      expect(result.isNewCluster).toBe(true);
      expect(result.clusterId).toBeDefined();
    });

    it('should create new cluster when similar items are unclustered', async () => {
      // Mock finding similar items that aren't assigned to any cluster
      mockQuery.mockResolvedValueOnce([
        { id: 'existing-1', score: 0.90, metadata: { clusterId: null } },
        { id: 'existing-2', score: 0.88, metadata: { clusterId: null } },
      ]);

      const feedback: FeedbackItem = {
        id: 'new-feedback',
        source: 'reddit',
        title: 'Bug report',
        body: 'Something broken',
        metadata: {},
        created_at: new Date().toISOString(),
      };

      const result = await clusterWithVectorDB(feedback, [0.1, 0.2, 0.3], 0.82);

      // Should create a new cluster and group the similar unclustered items
      expect(result.isNewCluster).toBe(true);
      expect(result.groupedFeedbackIds).toContain('existing-1');
      expect(result.groupedFeedbackIds).toContain('existing-2');
    });
  });
});

describe('Integration: Vector Store with Clustering Flow', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should handle the full clustering flow for new feedback', async () => {
    // This test verifies the complete flow:
    // 1. Generate embedding for new feedback
    // 2. Query vector DB for similar items
    // 3. Either assign to existing cluster or create new one
    // 4. Store the feedback with its embedding and cluster assignment in Vector DB

    const { processNewFeedbackWithVector } = require('@/lib/vector');

    const feedback: FeedbackItem = {
      id: 'test-feedback',
      source: 'reddit',
      title: 'Test Bug',
      body: 'This is a test bug report',
      metadata: {},
      created_at: new Date().toISOString(),
    };

    // Mock: No similar items found
    mockQuery.mockResolvedValueOnce([]);
    mockUpsert.mockResolvedValueOnce({ upsertedCount: 1 });

    const result = await processNewFeedbackWithVector(feedback);

    expect(result.feedbackId).toBe('test-feedback');
    expect(result.clusterId).toBeDefined();
    expect(mockUpsert).toHaveBeenCalled();
  });
});
