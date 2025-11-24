/**
 * Unit tests for clustering utility functions
 * These are pure functions that don't require mocking
 */

import {
  cosineSimilarity,
  calculateWeightedCentroid,
  calculateCentroid,
  findBestCluster,
  normalizeEmbedding,
  euclideanDistance,
} from '@/lib/clustering-utils';

describe('Clustering Utils', () => {
  describe('cosineSimilarity', () => {
    it('should return 1.0 for identical vectors', () => {
      const vec1 = [1.0, 2.0, 3.0];
      const vec2 = [1.0, 2.0, 3.0];

      const similarity = cosineSimilarity(vec1, vec2);

      expect(similarity).toBeCloseTo(1.0, 5);
    });

    it('should return 0.0 for orthogonal vectors', () => {
      const vec1 = [1.0, 0.0];
      const vec2 = [0.0, 1.0];

      const similarity = cosineSimilarity(vec1, vec2);

      expect(similarity).toBeCloseTo(0.0, 5);
    });

    it('should return positive similarity for similar vectors', () => {
      const vec1 = [1.0, 2.0, 3.0];
      const vec2 = [1.5, 2.5, 3.5];

      const similarity = cosineSimilarity(vec1, vec2);

      expect(similarity).toBeGreaterThan(0.99);
      expect(similarity).toBeLessThanOrEqual(1.0);
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

    it('should handle empty vectors', () => {
      const vec1: number[] = [];
      const vec2: number[] = [];

      const similarity = cosineSimilarity(vec1, vec2);

      expect(similarity).toBe(0);
    });
  });

  describe('calculateWeightedCentroid', () => {
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
      expect(result[0]).toBeCloseTo(1.25, 2);
      expect(result[1]).toBeCloseTo(2.5, 2);
    });

    it('should handle large clusters efficiently', () => {
      const oldCentroid = [5.0, 10.0, 15.0];
      const oldCount = 1000;
      const newEmbedding = [6.0, 11.0, 16.0];

      const result = calculateWeightedCentroid(oldCentroid, oldCount, newEmbedding);

      // New value should be very close to old centroid since it's averaged with 1000 items
      expect(result[0]).toBeCloseTo(5.001, 2);
      expect(result[1]).toBeCloseTo(10.001, 2);
      expect(result[2]).toBeCloseTo(15.001, 2);
    });
  });

  describe('calculateCentroid', () => {
    it('should calculate mean of multiple embeddings', () => {
      const embeddings = [
        [1.0, 2.0, 3.0],
        [2.0, 4.0, 6.0],
        [3.0, 6.0, 9.0],
      ];

      const result = calculateCentroid(embeddings);

      expect(result).toHaveLength(3);
      expect(result[0]).toBeCloseTo(2.0, 5);
      expect(result[1]).toBeCloseTo(4.0, 5);
      expect(result[2]).toBeCloseTo(6.0, 5);
    });

    it('should return empty array for no embeddings', () => {
      const embeddings: number[][] = [];

      const result = calculateCentroid(embeddings);

      expect(result).toEqual([]);
    });

    it('should return copy of single embedding', () => {
      const embeddings = [[1.0, 2.0, 3.0]];

      const result = calculateCentroid(embeddings);

      expect(result).toEqual([1.0, 2.0, 3.0]);
      // Should be a copy, not the same reference
      expect(result).not.toBe(embeddings[0]);
    });

    it('should handle dimension mismatches gracefully', () => {
      const embeddings = [
        [1.0, 2.0, 3.0],
        [2.0, 4.0], // Different dimension
        [3.0, 6.0, 9.0],
      ];

      const result = calculateCentroid(embeddings);

      // Should calculate based on matching dimensions
      expect(result).toHaveLength(3);
    });
  });

  describe('findBestCluster', () => {
    it('should find cluster with highest similarity', () => {
      const embedding = [1.0, 0.0, 0.0];
      const clusters = [
        { id: 'cluster-1', centroid: [0.0, 1.0, 0.0] }, // Orthogonal
        { id: 'cluster-2', centroid: [0.9, 0.1, 0.0] }, // Similar
        { id: 'cluster-3', centroid: [0.0, 0.0, 1.0] }, // Orthogonal
      ];

      const result = findBestCluster(embedding, clusters);

      expect(result.clusterId).toBe('cluster-2');
      expect(result.similarity).toBeGreaterThan(0.8);
    });

    it('should return null when no clusters exist', () => {
      const embedding = [1.0, 0.0, 0.0];
      const clusters: Array<{ id: string; centroid: number[] }> = [];

      const result = findBestCluster(embedding, clusters);

      expect(result.clusterId).toBeNull();
      expect(result.similarity).toBe(0);
    });

    it('should skip clusters with empty centroids', () => {
      const embedding = [1.0, 0.0, 0.0];
      const clusters = [
        { id: 'cluster-1', centroid: [] },
        { id: 'cluster-2', centroid: [0.9, 0.1, 0.0] },
      ];

      const result = findBestCluster(embedding, clusters);

      expect(result.clusterId).toBe('cluster-2');
    });
  });

  describe('normalizeEmbedding', () => {
    it('should normalize vector to unit length', () => {
      const embedding = [3.0, 4.0];

      const result = normalizeEmbedding(embedding);

      expect(result).toHaveLength(2);
      expect(result[0]).toBeCloseTo(0.6, 5);
      expect(result[1]).toBeCloseTo(0.8, 5);

      // Check magnitude is 1
      const magnitude = Math.sqrt(result[0] ** 2 + result[1] ** 2);
      expect(magnitude).toBeCloseTo(1.0, 5);
    });

    it('should handle zero vector', () => {
      const embedding = [0.0, 0.0, 0.0];

      const result = normalizeEmbedding(embedding);

      expect(result).toEqual([0.0, 0.0, 0.0]);
    });

    it('should not modify already normalized vector', () => {
      const embedding = [1.0, 0.0, 0.0];

      const result = normalizeEmbedding(embedding);

      expect(result).toEqual([1.0, 0.0, 0.0]);
    });
  });

  describe('euclideanDistance', () => {
    it('should calculate distance between vectors', () => {
      const vec1 = [0.0, 0.0];
      const vec2 = [3.0, 4.0];

      const distance = euclideanDistance(vec1, vec2);

      expect(distance).toBeCloseTo(5.0, 5);
    });

    it('should return 0 for identical vectors', () => {
      const vec1 = [1.0, 2.0, 3.0];
      const vec2 = [1.0, 2.0, 3.0];

      const distance = euclideanDistance(vec1, vec2);

      expect(distance).toBeCloseTo(0.0, 5);
    });

    it('should return Infinity for dimension mismatch', () => {
      const vec1 = [1.0, 2.0, 3.0];
      const vec2 = [1.0, 2.0];

      const distance = euclideanDistance(vec1, vec2);

      expect(distance).toBe(Infinity);
    });
  });

  describe('Performance Characteristics', () => {
    it('should calculate weighted centroid faster than full recalculation', () => {
      const largeEmbedding = new Array(768).fill(0.5); // Typical embedding size
      const oldCentroid = new Array(768).fill(0.4);
      const oldCount = 100;

      const start1 = performance.now();
      for (let i = 0; i < 1000; i++) {
        calculateWeightedCentroid(oldCentroid, oldCount, largeEmbedding);
      }
      const time1 = performance.now() - start1;

      // For comparison: full recalculation would require averaging all embeddings
      const allEmbeddings = new Array(101).fill(largeEmbedding);
      const start2 = performance.now();
      for (let i = 0; i < 1000; i++) {
        calculateCentroid(allEmbeddings);
      }
      const time2 = performance.now() - start2;

      console.log(`Weighted centroid: ${time1.toFixed(2)}ms`);
      console.log(`Full recalculation: ${time2.toFixed(2)}ms`);
      console.log(`Speedup: ${(time2 / time1).toFixed(2)}x`);

      // Weighted centroid should be significantly faster
      expect(time1).toBeLessThan(time2);
    });

    it('should handle high-dimensional embeddings efficiently', () => {
      const vec1 = new Array(1536).fill(0.5); // GPT-3 embedding size
      const vec2 = new Array(1536).fill(0.4);

      const start = performance.now();
      for (let i = 0; i < 10000; i++) {
        cosineSimilarity(vec1, vec2);
      }
      const time = performance.now() - start;

      console.log(`10000 similarity calculations (1536-dim): ${time.toFixed(2)}ms`);

      // Should complete in reasonable time (< 1 second for 10k calculations)
      expect(time).toBeLessThan(1000);
    });
  });
});
