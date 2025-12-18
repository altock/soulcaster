/**
 * Upstash Vector-based storage and clustering
 *
 * This module provides vector similarity search for feedback clustering.
 * Instead of storing centroids and doing O(n) comparisons, we use a vector DB
 * for efficient approximate nearest neighbor (ANN) search.
 */

import { Index } from '@upstash/vector';
import { GoogleGenAI } from '@google/genai';
import { randomUUID } from 'crypto';
import type { FeedbackItem } from '@/types';
import { cosineSimilarity } from './clustering';

// ============================================================================
// Types
// ============================================================================

export interface FeedbackVectorMetadata {
  title: string;
  source: 'reddit' | 'manual' | 'github' | 'sentry';
  clusterId: string | null;
  createdAt?: string;
  [key: string]: string | null | undefined; // Index signature for Upstash Vector Dict compatibility
}

export interface FeedbackVector {
  id: string;
  embedding: number[];
  metadata: FeedbackVectorMetadata;
}

export interface SimilarFeedback {
  id: string;
  score: number;
  metadata?: FeedbackVectorMetadata;
}

export interface ClusterAssignment {
  feedbackId: string;
  clusterId: string;
}

export interface ClusteringResult {
  feedbackId: string;
  clusterId: string;
  isNewCluster: boolean;
  similarity?: number;
  groupedFeedbackIds?: string[];
}

export interface ClusterCohesion {
  clusterId: string;
  avgSimilarity: number;
  minSimilarity: number;
  maxSimilarity: number;
  itemCount: number;
  quality: 'tight' | 'moderate' | 'loose';
}

/**
 * Calculate cohesion score for a cluster
 *
 * Cohesion = average pairwise similarity between all items in the cluster
 * Quality thresholds:
 *   - tight (>0.85): Items are very similar, clear cluster
 *   - moderate (0.70-0.85): Related items, good for triage
 *   - loose (<0.70): Broad grouping, consider splitting
 */
export function calculateClusterCohesion(
  embeddings: number[][],
  clusterId: string
): ClusterCohesion {
  if (embeddings.length <= 1) {
    return {
      clusterId,
      avgSimilarity: 1.0,
      minSimilarity: 1.0,
      maxSimilarity: 1.0,
      itemCount: embeddings.length,
      quality: 'tight',
    };
  }

  let totalSimilarity = 0;
  let pairCount = 0;
  let minSim = 1.0;
  let maxSim = 0.0;

  // Calculate pairwise similarities
  for (let i = 0; i < embeddings.length; i++) {
    for (let j = i + 1; j < embeddings.length; j++) {
      const sim = cosineSimilarity(embeddings[i], embeddings[j]);
      totalSimilarity += sim;
      pairCount++;
      minSim = Math.min(minSim, sim);
      maxSim = Math.max(maxSim, sim);
    }
  }

  const avgSimilarity = pairCount > 0 ? totalSimilarity / pairCount : 1.0;

  let quality: 'tight' | 'moderate' | 'loose';
  if (avgSimilarity >= 0.85) {
    quality = 'tight';
  } else if (avgSimilarity >= 0.70) {
    quality = 'moderate';
  } else {
    quality = 'loose';
  }

  return {
    clusterId,
    avgSimilarity,
    minSimilarity: minSim,
    maxSimilarity: maxSim,
    itemCount: embeddings.length,
    quality,
  };
}

// ============================================================================
// Vector Store Class
// ============================================================================

/**
 * VectorStore wraps Upstash Vector for feedback embedding storage and search.
 *
 * Key operations:
 * - Store feedback embeddings with metadata (clusterId, source, etc.)
 * - Find similar feedback items by embedding
 * - Update cluster assignments
 * - Query cluster membership
 */
export class VectorStore {
  private index: Index;

  constructor() {
    const url = process.env.UPSTASH_VECTOR_REST_URL;
    const token = process.env.UPSTASH_VECTOR_REST_TOKEN;

    if (!url || !token) {
      console.warn('[VectorStore] UPSTASH_VECTOR credentials not set, using mock');
    }

    this.index = new Index({
      url: url || 'https://mock-vector.upstash.io',
      token: token || 'mock-token',
    });
  }

  /**
   * Store a single feedback embedding
   */
  async upsertFeedback(
    feedbackId: string,
    embedding: number[],
    metadata: FeedbackVectorMetadata
  ): Promise<void> {
    await this.index.upsert({
      id: feedbackId,
      vector: embedding,
      metadata,
    });
  }

  /**
   * Store multiple feedback embeddings in batch
   */
  async upsertFeedbackBatch(items: FeedbackVector[]): Promise<void> {
    const vectors = items.map((item) => ({
      id: item.id,
      vector: item.embedding,
      metadata: item.metadata,
    }));

    await this.index.upsert(vectors);
  }

  /**
   * Find similar feedback items by embedding
   *
   * @param embedding - Query embedding vector
   * @param topK - Maximum number of results to return
   * @param minScore - Minimum similarity score (0-1), default 0
   * @param excludeIds - IDs to exclude from results
   */
  async findSimilar(
    embedding: number[],
    topK: number = 10,
    minScore: number = 0,
    excludeIds: string[] = []
  ): Promise<SimilarFeedback[]> {
    const results = await this.index.query({
      vector: embedding,
      topK,
      includeMetadata: true,
      includeVectors: false,
    });

    // Filter by minScore and excludeIds
    const excludeSet = new Set(excludeIds);
    return results
      .filter((r) => r.score >= minScore && !excludeSet.has(r.id as string))
      .map((r) => ({
        id: r.id as string,
        score: r.score,
        metadata: r.metadata as unknown as FeedbackVectorMetadata | undefined,
      }));
  }

  /**
   * Find similar items within a specific cluster
   */
  async findSimilarInCluster(
    embedding: number[],
    clusterId: string,
    topK: number = 10
  ): Promise<SimilarFeedback[]> {
    // Query more items since we'll filter by cluster
    const results = await this.index.query({
      vector: embedding,
      topK: topK * 3,
      includeMetadata: true,
      includeVectors: false,
    });

    // Filter to only items in the specified cluster
    return results
      .filter((r) => (r.metadata as unknown as FeedbackVectorMetadata)?.clusterId === clusterId)
      .slice(0, topK)
      .map((r) => ({
        id: r.id as string,
        score: r.score,
        metadata: r.metadata as unknown as FeedbackVectorMetadata | undefined,
      }));
  }

  /**
   * Update the cluster assignment for a single feedback item
   */
  async updateClusterAssignment(feedbackId: string, clusterId: string): Promise<void> {
    // Fetch current vector and metadata
    const existing = await this.index.fetch([feedbackId]);

    if (existing.length === 0 || !existing[0]) {
      throw new Error(`Feedback ${feedbackId} not found in vector store`);
    }

    const item = existing[0];
    const oldMetadata =
      (item.metadata as unknown as FeedbackVectorMetadata) || ({} as FeedbackVectorMetadata);
    const newMetadata: FeedbackVectorMetadata = {
      ...oldMetadata,
      clusterId,
    };

    // Re-upsert with updated metadata
    await this.index.upsert({
      id: feedbackId,
      vector: item.vector as number[],
      metadata: newMetadata,
    });
  }

  /**
   * Batch update cluster assignments
   */
  async updateClusterAssignmentBatch(assignments: ClusterAssignment[]): Promise<void> {
    const feedbackIds = assignments.map((a) => a.feedbackId);
    const existing = await this.index.fetch(feedbackIds);

    const updates = existing
      .filter((item): item is NonNullable<typeof item> => item !== null)
      .map((item) => {
        const assignment = assignments.find((a) => a.feedbackId === item.id);
        const oldMetadata =
          (item.metadata as unknown as FeedbackVectorMetadata) || ({} as FeedbackVectorMetadata);
        const newMetadata: FeedbackVectorMetadata = {
          ...oldMetadata,
          clusterId: assignment?.clusterId || null,
        };
        return {
          id: item.id as string,
          vector: item.vector as number[],
          metadata: newMetadata,
        };
      });

    if (updates.length > 0) {
      await this.index.upsert(updates);
    }
  }

  /**
   * Get all feedback IDs belonging to a cluster
   *
   * Note: Upstash Vector doesn't support metadata-only queries efficiently,
   * so we use a workaround with a zero vector query and filter.
   * For production, consider maintaining a Redis set of cluster members.
   */
  async getClusterMembers(clusterId: string): Promise<string[]> {
    // Query with a generic vector to get items, then filter by cluster
    // This is a workaround - in production you'd maintain cluster membership in Redis
    const results = await this.index.query({
      vector: new Array(768).fill(0), // Gemini embedding dimension
      topK: 1000,
      includeMetadata: true,
      includeVectors: false,
    });

    return results
      .filter((r) => (r.metadata as unknown as FeedbackVectorMetadata)?.clusterId === clusterId)
      .map((r) => r.id as string);
  }

  /**
   * Delete a single feedback from the vector store
   */
  async deleteFeedback(feedbackId: string): Promise<void> {
    await this.index.delete(feedbackId);
  }

  /**
   * Delete multiple feedback items from the vector store
   */
  async deleteFeedbackBatch(feedbackIds: string[]): Promise<void> {
    await this.index.delete(feedbackIds);
  }

  /**
   * Reset the entire vector store (use with caution!)
   */
  async reset(): Promise<void> {
    await this.index.reset();
  }
}

// ============================================================================
// Embedding Generation
// ============================================================================

const apiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_GENERATIVE_AI_API_KEY || '';
const ai = new GoogleGenAI({ apiKey });

/**
 * Create a 768‑dimensional embedding vector for a feedback item.
 *
 * Builds input text from the feedback's title and body and requests an embedding
 * (model: `gemini-embedding-001`) configured for 768 dimensions.
 *
 * @param feedback - Feedback item whose title and body are used to build the input text
 * @returns A numeric array of length 768 representing the feedback embedding
 * @throws Error if the embedding response is missing or the returned vector length is not 768
 */
export async function generateFeedbackEmbedding(feedback: FeedbackItem): Promise<number[]> {
  const text = `Title: ${feedback.title || ''}\nBody: ${feedback.body || ''}`.trim();

  const response = await ai.models.embedContent({
    model: 'gemini-embedding-001',
    contents: [text],
    config: {
      outputDimensionality: 768,
    },
  });

  if (!response?.embeddings?.[0]?.values) {
    throw new Error('Failed to generate embedding');
  }

  const embedding = response.embeddings[0].values;

  // Verify dimension matches our index
  if (embedding.length !== 768) {
    console.error(`[Vector] Unexpected embedding dimension: ${embedding.length}, expected 768`);
    throw new Error(`Invalid embedding dimension: ${embedding.length}`);
  }

  return embedding;
}

/**
 * Generate embeddings for multiple feedback items in parallel
 */
export async function generateFeedbackEmbeddingBatch(
  feedbackItems: FeedbackItem[]
): Promise<Map<string, number[]>> {
  const results = await Promise.all(
    feedbackItems.map(async (item) => {
      try {
        const embedding = await generateFeedbackEmbedding(item);
        return { id: item.id, embedding };
      } catch (error) {
        console.error(`[Vector] Failed to generate embedding for ${item.id}:`, error);
        return { id: item.id, embedding: null };
      }
    })
  );

  const map = new Map<string, number[]>();
  for (const { id, embedding } of results) {
    if (embedding) {
      map.set(id, embedding);
    }
  }
  return map;
}

// ============================================================================
// Clustering Thresholds (Single Source of Truth)
// See /docs/DESIGN_DECISIONS.md for rationale
// ============================================================================

/**
 * Threshold for vector-based clustering (assigning feedback to clusters).
 * Higher = stricter matching, fewer items per cluster.
 * 0.72 balances grouping related issues while avoiding over-clustering.
 */
export const VECTOR_CLUSTERING_THRESHOLD = 0.72;

/**
 * Threshold for centroid-based cleanup (merging similar clusters).
 * Lower than clustering threshold because we're comparing cluster centroids,
 * which are averages and naturally have lower similarity than individual items.
 */
export const CLEANUP_MERGE_THRESHOLD = 0.65;

// ============================================================================
// Vector-Based Clustering
// ============================================================================

// Legacy alias for backwards compatibility
const DEFAULT_SIMILARITY_THRESHOLD = VECTOR_CLUSTERING_THRESHOLD;

/**
 * Cluster a single feedback item using vector similarity search
 *
 * Algorithm:
 * 1. Query vector DB for similar items
 * 2. If top match is above threshold AND is already clustered → join that cluster
 * 3. If top matches are above threshold but unclustered → create new cluster with them
 * 4. If no matches above threshold → create new single-item cluster
 */
export async function clusterWithVectorDB(
  feedback: FeedbackItem,
  embedding: number[],
  threshold: number = DEFAULT_SIMILARITY_THRESHOLD
): Promise<ClusteringResult> {
  const vectorStore = new VectorStore();

  // Find similar items (exclude self)
  const similar = await vectorStore.findSimilar(
    embedding,
    20, // Get top 20 to have options
    threshold,
    [feedback.id]
  );

  if (similar.length === 0) {
    // No similar items - create new cluster
    const clusterId = randomUUID();
    return {
      feedbackId: feedback.id,
      clusterId,
      isNewCluster: true,
      groupedFeedbackIds: [],
    };
  }

  // Check if any similar item is already clustered
  const clusteredItems = similar.filter((s) => s.metadata?.clusterId);

  if (clusteredItems.length > 0) {
    // Join the cluster of the most similar clustered item
    const bestMatch = clusteredItems[0];
    return {
      feedbackId: feedback.id,
      clusterId: bestMatch.metadata!.clusterId!,
      isNewCluster: false,
      similarity: bestMatch.score,
    };
  }

  // All similar items are unclustered - create new cluster and group them
  const clusterId = randomUUID();
  const groupedIds = similar.map((s) => s.id);

  return {
    feedbackId: feedback.id,
    clusterId,
    isNewCluster: true,
    groupedFeedbackIds: groupedIds,
  };
}

/**
 * Process a new feedback item: generate embedding, cluster, and store
 *
 * This is the main entry point for real-time clustering on ingest.
 */
export async function processNewFeedbackWithVector(
  feedback: FeedbackItem,
  threshold: number = DEFAULT_SIMILARITY_THRESHOLD
): Promise<ClusteringResult> {
  // 1. Generate embedding
  const embedding = await generateFeedbackEmbedding(feedback);

  // 2. Cluster using vector similarity
  const result = await clusterWithVectorDB(feedback, embedding, threshold);

  // 3. Store in vector DB with cluster assignment
  const vectorStore = new VectorStore();
  await vectorStore.upsertFeedback(feedback.id, embedding, {
    title: feedback.title || '',
    source: feedback.source,
    clusterId: result.clusterId,
    createdAt: feedback.created_at,
  });

  // 4. If we grouped unclustered items, update their assignments too
  if (result.groupedFeedbackIds && result.groupedFeedbackIds.length > 0) {
    const assignments = result.groupedFeedbackIds.map((id) => ({
      feedbackId: id,
      clusterId: result.clusterId,
    }));
    await vectorStore.updateClusterAssignmentBatch(assignments);
  }

  return result;
}

/**
 * Batch process multiple feedback items
 *
 * More efficient than processing one at a time when you have many items.
 */
export async function processNewFeedbackBatchWithVector(
  feedbackItems: FeedbackItem[],
  threshold: number = DEFAULT_SIMILARITY_THRESHOLD
): Promise<ClusteringResult[]> {
  const vectorStore = new VectorStore();
  const results: ClusteringResult[] = [];

  // 1. Generate all embeddings in parallel
  const embeddingMap = await generateFeedbackEmbeddingBatch(feedbackItems);

  // 2. Process each item
  for (const feedback of feedbackItems) {
    const embedding = embeddingMap.get(feedback.id);
    if (!embedding) {
      console.warn(`[Vector] Skipping ${feedback.id} - no embedding generated`);
      continue;
    }

    // Cluster
    const result = await clusterWithVectorDB(feedback, embedding, threshold);
    results.push(result);

    // Store in vector DB
    await vectorStore.upsertFeedback(feedback.id, embedding, {
      title: feedback.title || '',
      source: feedback.source,
      clusterId: result.clusterId,
      createdAt: feedback.created_at,
    });

    // Update grouped items if any
    if (result.groupedFeedbackIds && result.groupedFeedbackIds.length > 0) {
      const assignments = result.groupedFeedbackIds.map((id) => ({
        feedbackId: id,
        clusterId: result.clusterId,
      }));
      await vectorStore.updateClusterAssignmentBatch(assignments);
    }
  }

  return results;
}

// ============================================================================
// Cluster Management
// ============================================================================

/**
 * Find clusters that should potentially be merged based on centroid similarity
 *
 * This is useful for cleanup/maintenance - finding clusters that have drifted
 * close to each other over time.
 *
 * Uses direct centroid-to-centroid comparison instead of vector DB queries,
 * since the vector DB stores feedback embeddings, not cluster centroids.
 */
export function findSimilarClusters(
  clusterCentroids: Map<string, number[]>,
  threshold: number = 0.75
): Array<{ cluster1: string; cluster2: string; similarity: number }> {
  const mergeCandidates: Array<{ cluster1: string; cluster2: string; similarity: number }> = [];

  const clusterIds = Array.from(clusterCentroids.keys());

  // Compare all pairs of cluster centroids directly
  for (let i = 0; i < clusterIds.length; i++) {
    const id1 = clusterIds[i];
    const centroid1 = clusterCentroids.get(id1)!;
    if (centroid1.length === 0) continue;

    for (let j = i + 1; j < clusterIds.length; j++) {
      const id2 = clusterIds[j];
      const centroid2 = clusterCentroids.get(id2)!;
      if (centroid2.length === 0) continue;

      const similarity = cosineSimilarity(centroid1, centroid2);
      if (similarity >= threshold) {
        mergeCandidates.push({ cluster1: id1, cluster2: id2, similarity });
      }
    }
  }

  return mergeCandidates;
}

// Export singleton instance for convenience
let vectorStoreInstance: VectorStore | null = null;

export function getVectorStore(): VectorStore {
  if (!vectorStoreInstance) {
    vectorStoreInstance = new VectorStore();
  }
  return vectorStoreInstance;
}