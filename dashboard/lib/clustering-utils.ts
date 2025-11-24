/**
 * Clustering Utility Functions
 *
 * Core mathematical and utility functions for optimized clustering
 */

/**
 * Calculate cosine similarity between two embeddings
 * Optimized implementation with early exit conditions
 *
 * @param embedding1 First embedding vector
 * @param embedding2 Second embedding vector
 * @returns Cosine similarity score between -1 and 1 (typically 0 to 1 for embeddings)
 */
export function cosineSimilarity(embedding1: number[], embedding2: number[]): number {
  // Handle dimension mismatch
  if (embedding1.length !== embedding2.length) {
    return 0;
  }

  if (embedding1.length === 0) {
    return 0;
  }

  let dotProduct = 0;
  let magnitude1 = 0;
  let magnitude2 = 0;

  // Single loop to calculate all values
  for (let i = 0; i < embedding1.length; i++) {
    const val1 = embedding1[i];
    const val2 = embedding2[i];

    dotProduct += val1 * val2;
    magnitude1 += val1 * val1;
    magnitude2 += val2 * val2;
  }

  // Handle zero vectors
  if (magnitude1 === 0 || magnitude2 === 0) {
    return 0;
  }

  magnitude1 = Math.sqrt(magnitude1);
  magnitude2 = Math.sqrt(magnitude2);

  return dotProduct / (magnitude1 * magnitude2);
}

/**
 * Calculate weighted centroid for incremental updates
 * This avoids re-averaging all embeddings in a cluster
 *
 * Formula: newCentroid = (oldCentroid * oldCount + newEmbedding) / (oldCount + 1)
 *
 * @param oldCentroid Current cluster centroid
 * @param oldCount Number of items currently in cluster
 * @param newEmbedding New embedding being added to cluster
 * @returns Updated centroid
 */
export function calculateWeightedCentroid(
  oldCentroid: number[],
  oldCount: number,
  newEmbedding: number[]
): number[] {
  // Handle first item in cluster
  if (oldCount === 0 || oldCentroid.length === 0) {
    return [...newEmbedding];
  }

  // Handle dimension mismatch (shouldn't happen but be safe)
  if (oldCentroid.length !== newEmbedding.length) {
    console.warn(
      `[ClusteringUtils] Dimension mismatch: centroid=${oldCentroid.length}, new=${newEmbedding.length}`
    );
    return [...newEmbedding];
  }

  const newCount = oldCount + 1;
  const newCentroid = new Array(oldCentroid.length);

  for (let i = 0; i < oldCentroid.length; i++) {
    newCentroid[i] = (oldCentroid[i] * oldCount + newEmbedding[i]) / newCount;
  }

  return newCentroid;
}

/**
 * Calculate centroid (mean) of multiple embeddings
 * Used for initial cluster creation or full recalculation
 *
 * @param embeddings Array of embedding vectors
 * @returns Centroid vector
 */
export function calculateCentroid(embeddings: number[][]): number[] {
  if (embeddings.length === 0) {
    return [];
  }

  if (embeddings.length === 1) {
    return [...embeddings[0]];
  }

  const dimensions = embeddings[0].length;
  const centroid = new Array(dimensions).fill(0);

  for (const embedding of embeddings) {
    // Handle potential dimension mismatch
    if (embedding.length !== dimensions) {
      console.warn(
        `[ClusteringUtils] Skipping embedding with mismatched dimensions: ${embedding.length} vs ${dimensions}`
      );
      continue;
    }

    for (let i = 0; i < dimensions; i++) {
      centroid[i] += embedding[i];
    }
  }

  // Calculate mean
  for (let i = 0; i < dimensions; i++) {
    centroid[i] /= embeddings.length;
  }

  return centroid;
}

/**
 * Find the best matching cluster for an embedding
 * Returns cluster index and similarity score
 *
 * @param embedding Embedding to match
 * @param clusters Array of cluster centroids
 * @returns Object with bestIndex (-1 if none) and maxSimilarity
 */
export function findBestCluster(
  embedding: number[],
  clusters: Array<{ id: string; centroid: number[] }>
): { clusterId: string | null; similarity: number } {
  let maxSimilarity = 0;
  let bestClusterId: string | null = null;

  for (const cluster of clusters) {
    if (cluster.centroid.length === 0) {
      continue;
    }

    const similarity = cosineSimilarity(embedding, cluster.centroid);

    if (similarity > maxSimilarity) {
      maxSimilarity = similarity;
      bestClusterId = cluster.id;
    }
  }

  return { clusterId: bestClusterId, similarity: maxSimilarity };
}

/**
 * Normalize an embedding to unit length
 * Useful for pre-processing before similarity calculations
 *
 * @param embedding Embedding vector
 * @returns Normalized embedding
 */
export function normalizeEmbedding(embedding: number[]): number[] {
  let magnitude = 0;

  for (const val of embedding) {
    magnitude += val * val;
  }

  magnitude = Math.sqrt(magnitude);

  if (magnitude === 0) {
    return new Array(embedding.length).fill(0);
  }

  return embedding.map((val) => val / magnitude);
}

/**
 * Calculate Euclidean distance between two embeddings
 * Alternative similarity metric (lower is more similar)
 *
 * @param embedding1 First embedding
 * @param embedding2 Second embedding
 * @returns Euclidean distance
 */
export function euclideanDistance(embedding1: number[], embedding2: number[]): number {
  if (embedding1.length !== embedding2.length) {
    return Infinity;
  }

  let sum = 0;
  for (let i = 0; i < embedding1.length; i++) {
    const diff = embedding1[i] - embedding2[i];
    sum += diff * diff;
  }

  return Math.sqrt(sum);
}
