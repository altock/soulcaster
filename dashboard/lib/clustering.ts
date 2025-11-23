import { pipeline, cos_sim } from '@xenova/transformers';
import type { FeedbackItem } from '@/types';

// Singleton model instance
let embeddingModel: any = null;

/**
 * Load the embedding model (cached after first load)
 */
async function getEmbeddingModel() {
  if (embeddingModel) return embeddingModel;

  console.log('[Clustering] Loading embedding model...');
  embeddingModel = await pipeline(
    'feature-extraction',
    'Xenova/all-MiniLM-L6-v2',
    { quantized: true }
  );
  console.log('[Clustering] Model loaded');

  return embeddingModel;
}

/**
 * Generate embedding for a piece of text
 */
async function generateEmbedding(text: string): Promise<number[]> {
  const model = await getEmbeddingModel();
  const result = await model(text, { pooling: 'mean', normalize: true });
  return Array.from(result.data);
}

/**
 * Calculate cosine similarity between two embeddings
 */
function cosineSimilarity(embedding1: number[], embedding2: number[]): number {
  return cos_sim(embedding1, embedding2);
}

/**
 * Calculate centroid (mean) of multiple embeddings
 */
function calculateCentroid(embeddings: number[][]): number[] {
  if (embeddings.length === 0) return [];
  if (embeddings.length === 1) return embeddings[0];

  const dimensions = embeddings[0].length;
  const centroid = new Array(dimensions).fill(0);

  for (const embedding of embeddings) {
    for (let i = 0; i < dimensions; i++) {
      centroid[i] += embedding[i];
    }
  }

  // Average
  for (let i = 0; i < dimensions; i++) {
    centroid[i] /= embeddings.length;
  }

  return centroid;
}

/**
 * Prepare text for embedding (combine title and body)
 */
function prepareTextForEmbedding(feedback: FeedbackItem): string {
  return `${feedback.title}\n${feedback.body}`.trim();
}

export interface ClusteringResult {
  clusterId: string;
  feedbackId: string;
  isNewCluster: boolean;
  similarity?: number;
}

export interface ClusterData {
  id: string;
  feedbackIds: string[];
  centroid: number[];
}

/**
 * Cluster a single feedback item against existing clusters
 * Returns which cluster it should belong to (or if it should create a new one)
 */
export async function clusterFeedback(
  feedback: FeedbackItem,
  existingClusters: ClusterData[],
  similarityThreshold: number = 0.80
): Promise<ClusteringResult> {
  const text = prepareTextForEmbedding(feedback);
  const embedding = await generateEmbedding(text);

  if (existingClusters.length === 0) {
    // First cluster
    const clusterId = `cluster-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    return {
      clusterId,
      feedbackId: feedback.id,
      isNewCluster: true,
    };
  }

  // Find most similar cluster
  let maxSimilarity = 0;
  let bestClusterId: string | null = null;

  for (const cluster of existingClusters) {
    if (cluster.centroid.length === 0) continue;

    const similarity = cosineSimilarity(embedding, cluster.centroid);
    if (similarity > maxSimilarity) {
      maxSimilarity = similarity;
      bestClusterId = cluster.id;
    }
  }

  // Check if similarity meets threshold
  if (maxSimilarity >= similarityThreshold && bestClusterId) {
    return {
      clusterId: bestClusterId,
      feedbackId: feedback.id,
      isNewCluster: false,
      similarity: maxSimilarity,
    };
  }

  // Create new cluster
  const clusterId = `cluster-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  return {
    clusterId,
    feedbackId: feedback.id,
    isNewCluster: true,
  };
}

/**
 * Batch cluster multiple feedback items
 */
export async function clusterFeedbackBatch(
  feedbackItems: FeedbackItem[],
  existingClusters: ClusterData[],
  similarityThreshold: number = 0.80
): Promise<{
  results: ClusteringResult[];
  updatedClusters: ClusterData[];
}> {
  const results: ClusteringResult[] = [];
  const clusters = [...existingClusters];

  // Generate embeddings for all feedback
  const embeddings = await Promise.all(
    feedbackItems.map(async (item) => {
      const text = prepareTextForEmbedding(item);
      return {
        feedbackId: item.id,
        embedding: await generateEmbedding(text),
      };
    })
  );

  // Cluster each feedback item
  for (const { feedbackId, embedding } of embeddings) {
    let maxSimilarity = 0;
    let bestClusterIndex: number | null = null;

    // Find best matching cluster
    for (let i = 0; i < clusters.length; i++) {
      if (clusters[i].centroid.length === 0) continue;

      const similarity = cosineSimilarity(embedding, clusters[i].centroid);
      if (similarity > maxSimilarity) {
        maxSimilarity = similarity;
        bestClusterIndex = i;
      }
    }

    // Assign to cluster or create new one
    if (maxSimilarity >= similarityThreshold && bestClusterIndex !== null) {
      const cluster = clusters[bestClusterIndex];
      cluster.feedbackIds.push(feedbackId);

      // Update centroid
      const clusterEmbeddings = embeddings
        .filter((e) => cluster.feedbackIds.includes(e.feedbackId))
        .map((e) => e.embedding);
      cluster.centroid = calculateCentroid(clusterEmbeddings);

      results.push({
        clusterId: cluster.id,
        feedbackId,
        isNewCluster: false,
        similarity: maxSimilarity,
      });
    } else {
      // Create new cluster
      const clusterId = `cluster-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      clusters.push({
        id: clusterId,
        feedbackIds: [feedbackId],
        centroid: embedding,
      });

      results.push({
        clusterId,
        feedbackId,
        isNewCluster: true,
      });
    }
  }

  return {
    results,
    updatedClusters: clusters,
  };
}

/**
 * Generate a summary for a cluster using the feedback items
 */
export async function generateClusterSummary(
  feedbackItems: FeedbackItem[]
): Promise<{ title: string; summary: string }> {
  if (feedbackItems.length === 0) {
    return { title: 'Empty cluster', summary: 'No feedback items' };
  }

  // For MVP: Use simple heuristics
  // In future: Call LLM API to generate better summaries

  // Title: Use most common words from titles
  const titles = feedbackItems.map((item) => item.title);
  const firstTitle = titles[0];

  // Extract key words (simple approach for MVP)
  const words = firstTitle
    .toLowerCase()
    .split(/\s+/)
    .filter((w) => w.length > 3);

  const title = firstTitle.substring(0, 80);

  // Summary: Combine first few feedback snippets
  const summaryParts = feedbackItems
    .slice(0, 3)
    .map((item) => item.body.substring(0, 100));

  const summary = `${feedbackItems.length} reports: ${summaryParts.join('; ')}`.substring(0, 300);

  return { title, summary };
}
