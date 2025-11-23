import { GoogleGenAI } from '@google/genai';
import { randomUUID } from 'crypto';
import type { FeedbackItem } from '@/types';

// Initialize Gemini
// The client gets the API key from the environment variable `GEMINI_API_KEY` automatically if not provided,
// but we can also pass it explicitly if we want to support both or verify it.
const apiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_GENERATIVE_AI_API_KEY || '';

if (!apiKey) {
  console.error('[Clustering] GEMINI_API_KEY is missing!');
} else {
  console.log(`[Clustering] API Key found (starts with: ${apiKey.substring(0, 4)}...)`);
}

const ai = new GoogleGenAI({ apiKey });

/**
 * Generate embedding for a piece of text
 */
async function generateEmbedding(text: string): Promise<number[]> {
  try {
    const response = await ai.models.embedContent({
      model: 'gemini-embedding-001',
      // Correct usage for @google/genai (v0.1.0+):
      // It expects `contents` (plural) as an array of `Part` objects.
      contents: [{ parts: [{ text }] }],
    });

    // Check for embedding in response.embedding or response.embeddings
    // The error suggested 'embeddings', but let's be safe and check what's actually there if possible,
    // or just follow the error suggestion.
    // Actually, checking the error: "Property 'embedding' does not exist... Did you mean 'embeddings'?"
    // So it is likely 'embeddings'.
    // However, for a single content, it might still be 'embedding' in some versions, but let's try 'embeddings'.
    // Wait, if I pass a single content, I expect a single embedding.
    // Let's try to inspect the type or just go with 'embeddings' and take the first one.

    // NOTE: The SDK might return `embeddings` as an array if multiple contents are passed.
    // Since I passed `content` (singular) in my previous attempt and it failed with "Did you mean 'contents'?",
    // I should probably use `contents` and expect `embeddings`.

    /* 
      Correct usage for @google/genai (v0.1.0+):
      const result = await client.models.embedContent({
        model: '...',
        contents: [...]
      });
      result.embeddings[0].values
    */

    // Let's correct the call structure as well.

    // The new SDK response structure might be slightly different
    // Based on docs/examples, it usually returns embedding directly or in a structure
    // Let's assume standard response structure for now, but might need adjustment if SDK differs significantly
    // from previous one.
    // Actually, for @google/genai, it's likely: response.embeddings[0].values

    if (!response || !response.embeddings || response.embeddings.length === 0 || !response.embeddings[0].values) {
      throw new Error('Invalid embedding response');
    }

    return response.embeddings[0].values;
  } catch (error) {
    console.error('[Clustering] Error generating embedding:', error);
    throw error;
  }
}

/**
 * Calculate cosine similarity between two embeddings
 */
function cosineSimilarity(embedding1: number[], embedding2: number[]): number {
  if (embedding1.length !== embedding2.length) {
    // Handle mismatch if necessary, or just return 0
    return 0;
  }

  let dotProduct = 0;
  let magnitude1 = 0;
  let magnitude2 = 0;

  for (let i = 0; i < embedding1.length; i++) {
    dotProduct += embedding1[i] * embedding2[i];
    magnitude1 += embedding1[i] * embedding1[i];
    magnitude2 += embedding2[i] * embedding2[i];
  }

  magnitude1 = Math.sqrt(magnitude1);
  magnitude2 = Math.sqrt(magnitude2);

  if (magnitude1 === 0 || magnitude2 === 0) return 0;

  return dotProduct / (magnitude1 * magnitude2);
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
    // Handle potential dimension mismatch if models changed
    if (embedding.length !== dimensions) continue;

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
  const title = feedback.title || '';
  const body = feedback.body || '';
  return `Title: ${title}\nBody: ${body}`.trim();
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
  similarityThreshold: number = 0.75 // Slightly lower threshold for Gemini embeddings usually works better
): Promise<ClusteringResult> {
  const text = prepareTextForEmbedding(feedback);
  const embedding = await generateEmbedding(text);

  if (existingClusters.length === 0) {
    // First cluster
    const clusterId = randomUUID();
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
  const clusterId = randomUUID();
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
  similarityThreshold: number = 0.75
): Promise<{
  results: ClusteringResult[];
  updatedClusters: ClusterData[];
}> {
  const results: ClusteringResult[] = [];
  const clusters = [...existingClusters];

  // Generate embeddings for all feedback
  // Note: Gemini has rate limits, so we might need to throttle if batch is large
  // For now, we'll do it sequentially or in small chunks if needed, but Promise.all is fine for small batches
  const embeddings = await Promise.all(
    feedbackItems.map(async (item) => {
      const text = prepareTextForEmbedding(item);
      try {
        return {
          feedbackId: item.id,
          embedding: await generateEmbedding(text),
        };
      } catch (e) {
        console.error(`Failed to generate embedding for ${item.id}`, e);
        return null;
      }
    })
  );

  const validEmbeddings = embeddings.filter((e): e is { feedbackId: string; embedding: number[] } => e !== null);

  // Cluster each feedback item
  for (const { feedbackId, embedding } of validEmbeddings) {
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
      console.log(
        `[Clustering] Adding feedback ${feedbackId} to existing cluster ${cluster.id} (similarity: ${maxSimilarity.toFixed(3)})`
      );
      cluster.feedbackIds.push(feedbackId);

      // Update centroid
      const clusterEmbeddings = validEmbeddings
        .filter((e) => cluster.feedbackIds.includes(e.feedbackId))
        .map((e) => e.embedding);

      // Also include embeddings from existing cluster if we had them stored... 
      // But here we only have centroids. 
      // Weighted average update for centroid:
      // newCentroid = (oldCentroid * oldCount + newEmbedding) / (oldCount + 1)
      // But we don't track old count easily here without looking up.
      // For simplicity in this in-memory version, we'll just re-average the current batch's contribution 
      // or better, just average the new embedding with the old centroid (approximate)
      // A better approach for the future: store count in ClusterData

      // Simple moving average for now to keep it simple
      const n = cluster.feedbackIds.length;
      const newCentroid = cluster.centroid.map((val, i) =>
        (val * (n - 1) + embedding[i]) / n
      );
      cluster.centroid = newCentroid;

      results.push({
        clusterId: cluster.id,
        feedbackId,
        isNewCluster: false,
        similarity: maxSimilarity,
      });
    } else {
      // Create new cluster
      console.log(
        `[Clustering] Creating new cluster for feedback ${feedbackId} (max similarity: ${maxSimilarity.toFixed(3)}, threshold: ${similarityThreshold})`
      );
      const clusterId = randomUUID();
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

  const feedbackTexts = feedbackItems
    .map((item) => {
      const title = item.title || 'No Title';
      const body = item.body || '';
      return `- ${title}: ${body.substring(0, 200)}`;
    })
    .join('\n');

  const prompt = `
    Analyze the following user feedback items and generate a concise title and a summary.
    
    Feedback Items:
    ${feedbackTexts}
    
    Output format (JSON):
    {
      "title": "Short descriptive title (max 50 chars)",
      "summary": "Concise summary of the common issue or theme (max 300 chars)"
    }
  `;

  try {
    const response = await ai.models.generateContent({
      model: 'gemini-3-pro-preview',
      contents: [{
        role: 'user',
        parts: [{ text: prompt }]
      }],
      config: {
        responseMimeType: 'application/json',
      }
    });

    // In @google/genai, response.text is a getter/property, not a function?
    // The error said: "Type 'String' has no call signatures." implying response.text IS a string (or String object).
    // So we should access it directly.
    const text = response.text;

    if (!text) {
      throw new Error('Empty response from Gemini');
    }

    // Clean up markdown code blocks if present (though responseMimeType should handle it mostly)
    const jsonStr = text.replace(/```json/g, '').replace(/```/g, '').trim();
    const data = JSON.parse(jsonStr);

    return {
      title: data.title || 'Cluster Summary',
      summary: data.summary || 'No summary available',
    };
  } catch (error) {
    console.error('[Clustering] Error generating summary with Gemini:', error);

    // Fallback to simple heuristic
    const titles = feedbackItems.map((item) => item.title || 'No Title');
    const firstBody = feedbackItems[0]?.body || '';
    return {
      title: titles[0].substring(0, 50),
      summary: `${feedbackItems.length} reports. First: ${firstBody.substring(0, 100)}...`,
    };
  }
}
