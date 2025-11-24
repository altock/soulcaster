/**
 * Comprehensive test suite for clustering optimizations
 * Following TDD principles - these tests define the expected behavior
 */

import {
  clusterFeedbackBatch,
  generateClusterSummary,
  type ClusterData,
} from '@/lib/clustering';
import {
  getEmbedding,
  setEmbedding,
  hasEmbedding,
} from '@/lib/embedding-cache';
import { cosineSimilarity, calculateWeightedCentroid } from '@/lib/clustering-utils';
import type { FeedbackItem } from '@/types';

// Mock the Google GenAI
jest.mock('@google/genai', () => ({
  GoogleGenAI: jest.fn().mockImplementation(() => ({
    models: {
      embedContent: jest.fn(),
      generateContent: jest.fn(),
    },
  })),
}));

// Mock Redis with all necessary methods
jest.mock('@upstash/redis', () => {
  const mockPipelineMethods = {
    hget: jest.fn().mockReturnThis(),
    hset: jest.fn().mockReturnThis(),
    del: jest.fn().mockReturnThis(),
    sadd: jest.fn().mockReturnThis(),
    srem: jest.fn().mockReturnThis(),
    exec: jest.fn().mockResolvedValue([]),
  };

  return {
    Redis: jest.fn().mockImplementation(() => ({
      hget: jest.fn(),
      hset: jest.fn(),
      hexists: jest.fn(),
      exists: jest.fn(),
      pipeline: jest.fn().mockReturnValue(mockPipelineMethods),
    })),
  };
});

describe('Clustering Optimizations', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Embedding Cache', () => {
    it('should retrieve cached embedding when available', async () => {
      const feedbackId = 'test-id-123';
      const cachedEmbedding = [0.1, 0.2, 0.3];

      // Mock the module and its Redis instance
      jest.isolateModules(() => {
        jest.doMock('@upstash/redis', () => ({
          Redis: jest.fn().mockImplementation(() => ({
            hget: jest.fn().mockResolvedValue(JSON.stringify(cachedEmbedding)),
          })),
        }));
      });

      const result = await getEmbedding(feedbackId);

      expect(result).toEqual(cachedEmbedding);
    });

    it('should return null when no cached embedding exists', async () => {
      const feedbackId = 'test-id-456';

      const { Redis } = require('@upstash/redis');
      const mockRedis = new Redis();
      mockRedis.hget.mockResolvedValueOnce(null);

      const result = await getEmbedding(feedbackId);

      expect(result).toBeNull();
    });

    it('should store embedding in cache', async () => {
      const feedbackId = 'test-id-789';
      const embedding = [0.4, 0.5, 0.6];

      const { Redis } = require('@upstash/redis');
      const mockRedis = new Redis();
      mockRedis.hset.mockResolvedValueOnce(1);

      await setEmbedding(feedbackId, embedding);

      expect(mockRedis.hset).toHaveBeenCalledWith(
        `feedback:${feedbackId}`,
        { embedding: JSON.stringify(embedding) }
      );
    });

    it('should check if embedding exists without fetching', async () => {
      const feedbackId = 'test-id-check';

      const { Redis } = require('@upstash/redis');
      const mockRedis = new Redis();
      mockRedis.exists.mockResolvedValueOnce(1);

      const result = await hasEmbedding(feedbackId);

      expect(result).toBe(true);
    });

    it('should batch fetch multiple embeddings efficiently', async () => {
      const feedbackIds = ['id-1', 'id-2', 'id-3'];
      const embeddings = [
        [0.1, 0.2],
        [0.3, 0.4],
        [0.5, 0.6],
      ];

      const { Redis } = require('@upstash/redis');
      const mockRedis = new Redis();
      const mockPipeline = mockRedis.pipeline();

      mockPipeline.exec.mockResolvedValueOnce(
        embeddings.map((e) => JSON.stringify(e))
      );

      // This will be implemented in the actual code
      const { batchGetEmbeddings } = require('@/lib/embedding-cache');
      const results = await batchGetEmbeddings(feedbackIds);

      expect(results).toHaveLength(3);
      expect(mockPipeline.hget).toHaveBeenCalledTimes(3);
      expect(mockPipeline.exec).toHaveBeenCalledTimes(1);
    });
  });

  describe('Incremental Centroid Updates', () => {
    it('should calculate weighted centroid correctly', () => {
      const oldCentroid = [1.0, 2.0, 3.0];
      const oldCount = 5;
      const newEmbedding = [2.0, 4.0, 6.0];

      const result = calculateWeightedCentroid(oldCentroid, oldCount, newEmbedding);

      // Expected: ((1*5 + 2) / 6, (2*5 + 4) / 6, (3*5 + 6) / 6)
      // = (7/6, 14/6, 21/6) = (1.167, 2.333, 3.5)
      expect(result).toHaveLength(3);
      expect(result[0]).toBeCloseTo(1.167, 2);
      expect(result[1]).toBeCloseTo(2.333, 2);
      expect(result[2]).toBeCloseTo(3.5, 2);
    });

    it('should handle first item in cluster correctly', () => {
      const oldCentroid: number[] = [];
      const oldCount = 0;
      const newEmbedding = [1.0, 2.0, 3.0];

      const result = calculateWeightedCentroid(oldCentroid, oldCount, newEmbedding);

      expect(result).toEqual(newEmbedding);
    });

    it('should maintain dimension consistency', () => {
      const oldCentroid = [1.0, 2.0];
      const oldCount = 3;
      const newEmbedding = [2.0, 4.0];

      const result = calculateWeightedCentroid(oldCentroid, oldCount, newEmbedding);

      expect(result).toHaveLength(2);
    });
  });

  describe('Cosine Similarity Optimization', () => {
    it('should calculate similarity between normalized vectors', () => {
      const vec1 = [1.0, 0.0, 0.0];
      const vec2 = [1.0, 0.0, 0.0];

      const similarity = cosineSimilarity(vec1, vec2);

      expect(similarity).toBeCloseTo(1.0, 5);
    });

    it('should return 0 for orthogonal vectors', () => {
      const vec1 = [1.0, 0.0];
      const vec2 = [0.0, 1.0];

      const similarity = cosineSimilarity(vec1, vec2);

      expect(similarity).toBeCloseTo(0.0, 5);
    });

    it('should handle dimension mismatch gracefully', () => {
      const vec1 = [1.0, 2.0, 3.0];
      const vec2 = [1.0, 2.0];

      const similarity = cosineSimilarity(vec1, vec2);

      expect(similarity).toBe(0);
    });

    it('should handle zero vectors', () => {
      const vec1 = [0.0, 0.0, 0.0];
      const vec2 = [1.0, 2.0, 3.0];

      const similarity = cosineSimilarity(vec1, vec2);

      expect(similarity).toBe(0);
    });
  });

  describe('Smart Summary Regeneration', () => {
    it('should not regenerate summary for clusters with minimal changes', async () => {
      const feedbackItems: FeedbackItem[] = [
        {
          id: '1',
          title: 'Bug in login',
          body: 'Cannot login',
          source: 'manual',
          created_at: new Date().toISOString(),
        },
      ];

      const { GoogleGenAI } = require('@google/genai');
      const mockAI = new GoogleGenAI();

      // This should determine no summary regeneration is needed
      const shouldRegenerate = await shouldRegenerateSummary('cluster-id', 1, 1);

      expect(shouldRegenerate).toBe(false);
    });

    it('should regenerate summary when cluster size increases significantly', async () => {
      // Adding 3 new items to a cluster of 2 items = 150% growth
      const shouldRegenerate = await shouldRegenerateSummary('cluster-id', 2, 5);

      expect(shouldRegenerate).toBe(true);
    });

    it('should regenerate summary for new clusters', async () => {
      const shouldRegenerate = await shouldRegenerateSummary('cluster-id', 0, 1);

      expect(shouldRegenerate).toBe(true);
    });

    it('should use cached summary when appropriate', async () => {
      const feedbackItems: FeedbackItem[] = [
        {
          id: '1',
          title: 'Bug',
          body: 'Test',
          source: 'manual',
          created_at: new Date().toISOString(),
        },
      ];

      // Mock existing summary
      const existingSummary = {
        title: 'Cached Title',
        summary: 'Cached Summary',
        issueTitle: 'Issue Title',
        issueDescription: 'Issue Desc',
      };

      const result = await generateClusterSummary(feedbackItems, {
        existingSummary,
        oldCount: 1,
        newCount: 1,
      });

      expect(result.title).toBe('Cached Title');
    });
  });

  describe('Batch Clustering Performance', () => {
    it('should reuse embeddings from cache during batch clustering', async () => {
      const feedbackItems: FeedbackItem[] = [
        {
          id: 'cached-1',
          title: 'Bug 1',
          body: 'Test bug 1',
          source: 'manual',
          created_at: new Date().toISOString(),
        },
        {
          id: 'cached-2',
          title: 'Bug 2',
          body: 'Test bug 2',
          source: 'manual',
          created_at: new Date().toISOString(),
        },
      ];

      const existingClusters: ClusterData[] = [];

      // Mock embeddings as cached
      const { Redis } = require('@upstash/redis');
      const mockRedis = new Redis();
      mockRedis.hget
        .mockResolvedValueOnce(JSON.stringify([0.1, 0.2, 0.3]))
        .mockResolvedValueOnce(JSON.stringify([0.2, 0.3, 0.4]));

      const { GoogleGenAI } = require('@google/genai');
      const mockAI = new GoogleGenAI();

      // Clustering should use cached embeddings, not call AI
      await clusterFeedbackBatch(feedbackItems, existingClusters, 0.75);

      // Should fetch from cache, not generate new embeddings
      expect(mockRedis.hget).toHaveBeenCalled();
      expect(mockAI.models.embedContent).not.toHaveBeenCalled();
    });

    it('should generate embeddings only for uncached items', async () => {
      const feedbackItems: FeedbackItem[] = [
        {
          id: 'cached-1',
          title: 'Bug 1',
          body: 'Cached item',
          source: 'manual',
          created_at: new Date().toISOString(),
        },
        {
          id: 'new-1',
          title: 'Bug 2',
          body: 'New item',
          source: 'manual',
          created_at: new Date().toISOString(),
        },
      ];

      const { Redis } = require('@upstash/redis');
      const mockRedis = new Redis();

      // First is cached, second is not
      mockRedis.hget
        .mockResolvedValueOnce(JSON.stringify([0.1, 0.2, 0.3]))
        .mockResolvedValueOnce(null);

      const { GoogleGenAI } = require('@google/genai');
      const mockAI = new GoogleGenAI();
      mockAI.models.embedContent.mockResolvedValueOnce({
        embeddings: [{ values: [0.2, 0.3, 0.4] }],
      });

      const existingClusters: ClusterData[] = [];
      await clusterFeedbackBatch(feedbackItems, existingClusters, 0.75);

      // Should only call AI once for the uncached item
      expect(mockAI.models.embedContent).toHaveBeenCalledTimes(1);
    });
  });

  describe('Redis Pipeline Batching', () => {
    it('should use pipeline for batch cluster updates', async () => {
      const { Redis } = require('@upstash/redis');
      const mockRedis = new Redis();
      const mockPipeline = mockRedis.pipeline();

      const clusterUpdates = [
        { clusterId: 'c1', feedbackIds: ['f1', 'f2'] },
        { clusterId: 'c2', feedbackIds: ['f3', 'f4'] },
        { clusterId: 'c3', feedbackIds: ['f5', 'f6'] },
      ];

      const { batchUpdateClusters } = require('@/lib/clustering-batch');
      await batchUpdateClusters(clusterUpdates);

      // Should use single pipeline exec, not individual operations
      expect(mockPipeline.exec).toHaveBeenCalledTimes(1);
    });

    it('should batch mark feedback as clustered', async () => {
      const { Redis } = require('@upstash/redis');
      const mockRedis = new Redis();
      const mockPipeline = mockRedis.pipeline();

      const feedbackIds = ['f1', 'f2', 'f3', 'f4', 'f5'];

      const { batchMarkClustered } = require('@/lib/clustering-batch');
      await batchMarkClustered(feedbackIds);

      // Should use pipeline, not loop
      expect(mockPipeline.exec).toHaveBeenCalled();
    });
  });

  describe('End-to-End Clustering Optimization', () => {
    it('should complete clustering with minimal API calls', async () => {
      const feedbackItems: FeedbackItem[] = Array.from({ length: 10 }, (_, i) => ({
        id: `item-${i}`,
        title: `Bug ${i}`,
        body: `Description ${i}`,
        source: 'manual' as const,
        created_at: new Date().toISOString(),
      }));

      const existingClusters: ClusterData[] = [
        {
          id: 'cluster-1',
          feedbackIds: ['old-1', 'old-2'],
          centroid: [0.5, 0.5, 0.5],
        },
      ];

      const { GoogleGenAI } = require('@google/genai');
      const mockAI = new GoogleGenAI();

      // Mock all embeddings as cached
      const { Redis } = require('@upstash/redis');
      const mockRedis = new Redis();
      mockRedis.hget.mockImplementation(() =>
        Promise.resolve(JSON.stringify([0.1, 0.2, 0.3]))
      );

      await clusterFeedbackBatch(feedbackItems, existingClusters, 0.75);

      // Should use cached embeddings, no new embedding generation
      expect(mockAI.models.embedContent).not.toHaveBeenCalled();
    });
  });
});

// Helper function that will be implemented
async function shouldRegenerateSummary(
  clusterId: string,
  oldCount: number,
  newCount: number
): Promise<boolean> {
  // Will be implemented in actual code
  if (oldCount === 0) return true; // New cluster
  const growthRate = (newCount - oldCount) / oldCount;
  return growthRate > 0.5; // Regenerate if >50% growth
}
