/**
 * Embedding Cache Layer
 *
 * Optimizes clustering by storing embeddings in Redis to avoid regeneration.
 * This dramatically reduces API calls and improves performance.
 */

import { Redis } from '@upstash/redis';

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

/**
 * Get cached embedding for a feedback item
 * @param feedbackId The feedback item ID
 * @returns The cached embedding or null if not found
 */
export async function getEmbedding(feedbackId: string): Promise<number[] | null> {
  try {
    const embeddingStr = await redis.hget(`feedback:${feedbackId}`, 'embedding');

    if (!embeddingStr || typeof embeddingStr !== 'string') {
      return null;
    }

    return JSON.parse(embeddingStr);
  } catch (error) {
    console.error(`[EmbeddingCache] Error fetching embedding for ${feedbackId}:`, error);
    return null;
  }
}

/**
 * Store embedding in cache
 * @param feedbackId The feedback item ID
 * @param embedding The embedding vector to cache
 */
export async function setEmbedding(feedbackId: string, embedding: number[]): Promise<void> {
  try {
    await redis.hset(`feedback:${feedbackId}`, {
      embedding: JSON.stringify(embedding),
    });
  } catch (error) {
    console.error(`[EmbeddingCache] Error storing embedding for ${feedbackId}:`, error);
    throw error;
  }
}

/**
 * Check if embedding exists for a feedback item
 * @param feedbackId The feedback item ID
 * @returns True if embedding exists, false otherwise
 */
export async function hasEmbedding(feedbackId: string): Promise<boolean> {
  try {
    const result = await redis.hexists(`feedback:${feedbackId}`, 'embedding');
    return result === 1;
  } catch (error) {
    console.error(`[EmbeddingCache] Error checking embedding for ${feedbackId}:`, error);
    return false;
  }
}

/**
 * Batch fetch embeddings for multiple feedback items using Redis pipeline
 * This is significantly faster than individual fetches
 *
 * @param feedbackIds Array of feedback item IDs
 * @returns Array of embeddings (null for items without cached embeddings)
 */
export async function batchGetEmbeddings(feedbackIds: string[]): Promise<(number[] | null)[]> {
  if (feedbackIds.length === 0) {
    return [];
  }

  try {
    const pipeline = redis.pipeline();

    for (const id of feedbackIds) {
      pipeline.hget(`feedback:${id}`, 'embedding');
    }

    const results = await pipeline.exec();

    return results.map((result) => {
      if (!result || typeof result !== 'string') {
        return null;
      }

      try {
        return JSON.parse(result);
      } catch {
        return null;
      }
    });
  } catch (error) {
    console.error('[EmbeddingCache] Error batch fetching embeddings:', error);
    // Fallback to individual fetches
    return Promise.all(feedbackIds.map((id) => getEmbedding(id)));
  }
}

/**
 * Batch store embeddings using Redis pipeline
 *
 * @param items Array of {feedbackId, embedding} pairs
 */
export async function batchSetEmbeddings(
  items: Array<{ feedbackId: string; embedding: number[] }>
): Promise<void> {
  if (items.length === 0) {
    return;
  }

  try {
    const pipeline = redis.pipeline();

    for (const { feedbackId, embedding } of items) {
      pipeline.hset(`feedback:${feedbackId}`, {
        embedding: JSON.stringify(embedding),
      });
    }

    await pipeline.exec();
  } catch (error) {
    console.error('[EmbeddingCache] Error batch storing embeddings:', error);
    throw error;
  }
}

/**
 * Delete cached embedding for a feedback item
 * @param feedbackId The feedback item ID
 */
export async function deleteEmbedding(feedbackId: string): Promise<void> {
  try {
    await redis.hdel(`feedback:${feedbackId}`, 'embedding');
  } catch (error) {
    console.error(`[EmbeddingCache] Error deleting embedding for ${feedbackId}:`, error);
  }
}

/**
 * Clear all cached embeddings (use with caution)
 */
export async function clearAllEmbeddings(): Promise<void> {
  console.warn('[EmbeddingCache] Clearing all embeddings - this operation cannot be undone');
  // This would require iterating through all feedback items
  // For now, we'll just log a warning as this should be a rare operation
  throw new Error('clearAllEmbeddings not implemented - use Redis CLI if needed');
}
