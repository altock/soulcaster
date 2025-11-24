/**
 * Redis Batch Operations for Clustering
 *
 * Optimizes Redis operations by using pipelines for bulk updates.
 * This dramatically reduces round-trip time and improves throughput.
 */

import { Redis } from '@upstash/redis';
import type { IssueCluster } from '@/types';

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

export interface ClusterUpdate {
  clusterId: string;
  feedbackIds: string[];
  centroid: number[];
  isNew: boolean;
  title?: string;
  summary?: string;
  issueTitle?: string;
  issueDescription?: string;
  repoUrl?: string;
}

/**
 * Batch update multiple clusters using Redis pipeline
 * This is much more efficient than updating clusters one by one
 *
 * @param updates Array of cluster updates
 */
export async function batchUpdateClusters(updates: ClusterUpdate[]): Promise<void> {
  if (updates.length === 0) {
    return;
  }

  const timestamp = new Date().toISOString();
  const pipeline = redis.pipeline();

  for (const update of updates) {
    const {
      clusterId,
      feedbackIds,
      centroid,
      isNew,
      title,
      summary,
      issueTitle,
      issueDescription,
      repoUrl,
    } = update;

    if (isNew) {
      // Create new cluster
      const payload: Record<string, string> = {
        id: clusterId,
        title: title || 'Untitled Cluster',
        summary: summary || 'No summary available',
        status: 'new',
        created_at: timestamp,
        updated_at: timestamp,
        centroid: JSON.stringify(centroid),
      };

      if (issueTitle) payload.issue_title = issueTitle;
      if (issueDescription) payload.issue_description = issueDescription;
      if (repoUrl) payload.github_repo_url = repoUrl;

      pipeline.hset(`cluster:${clusterId}`, payload);
      pipeline.sadd('clusters:all', clusterId);
    } else {
      // Update existing cluster
      const updatePayload: Record<string, string> = {
        updated_at: timestamp,
        centroid: JSON.stringify(centroid),
      };

      if (summary) updatePayload.summary = summary;
      if (issueTitle) updatePayload.issue_title = issueTitle;
      if (issueDescription) updatePayload.issue_description = issueDescription;
      if (repoUrl) updatePayload.github_repo_url = repoUrl;

      pipeline.hset(`cluster:${clusterId}`, updatePayload);
    }

    // Update cluster items set
    // Delete old set and create new one
    pipeline.del(`cluster:items:${clusterId}`);
    if (feedbackIds.length > 0) {
      // Add all feedback IDs to the set
      for (const feedbackId of feedbackIds) {
        pipeline.sadd(`cluster:items:${clusterId}`, feedbackId);
      }
    }

    // Mark all feedback items as clustered
    for (const feedbackId of feedbackIds) {
      pipeline.hset(`feedback:${feedbackId}`, { clustered: 'true' });
    }
  }

  // Execute all operations in a single batch
  await pipeline.exec();

  console.log(`[ClusteringBatch] Updated ${updates.length} clusters in batch`);
}

/**
 * Batch mark feedback items as clustered
 *
 * @param feedbackIds Array of feedback item IDs
 */
export async function batchMarkClustered(feedbackIds: string[]): Promise<void> {
  if (feedbackIds.length === 0) {
    return;
  }

  const pipeline = redis.pipeline();

  for (const feedbackId of feedbackIds) {
    pipeline.hset(`feedback:${feedbackId}`, { clustered: 'true' });
    pipeline.srem('feedback:unclustered', feedbackId);
  }

  await pipeline.exec();

  console.log(`[ClusteringBatch] Marked ${feedbackIds.length} items as clustered`);
}

/**
 * Batch remove feedback items from unclustered set
 *
 * @param feedbackIds Array of feedback item IDs
 */
export async function batchRemoveFromUnclustered(feedbackIds: string[]): Promise<void> {
  if (feedbackIds.length === 0) {
    return;
  }

  const pipeline = redis.pipeline();

  for (const feedbackId of feedbackIds) {
    pipeline.srem('feedback:unclustered', feedbackId);
  }

  await pipeline.exec();
}

/**
 * Batch fetch cluster metadata
 *
 * @param clusterIds Array of cluster IDs
 * @returns Array of cluster objects (null for missing clusters)
 */
export async function batchGetClusters(
  clusterIds: string[]
): Promise<Array<IssueCluster | null>> {
  if (clusterIds.length === 0) {
    return [];
  }

  const pipeline = redis.pipeline();

  for (const clusterId of clusterIds) {
    pipeline.hgetall(`cluster:${clusterId}`);
  }

  const results = await pipeline.exec();

  return results.map((data: any) => {
    if (!data || Object.keys(data).length === 0) {
      return null;
    }

    return {
      id: data.id as string,
      title: data.title as string,
      summary: data.summary as string,
      feedback_ids: [],
      status: data.status as 'new' | 'fixing' | 'pr_opened' | 'failed',
      created_at: data.created_at as string,
      updated_at: data.updated_at as string,
      github_branch: data.github_branch as string | undefined,
      github_pr_url: data.github_pr_url as string | undefined,
      error_message: data.error_message as string | undefined,
      issue_title: data.issue_title as string | undefined,
      issue_description: data.issue_description as string | undefined,
      github_repo_url: data.github_repo_url as string | undefined,
    };
  });
}

/**
 * Batch fetch cluster item counts
 *
 * @param clusterIds Array of cluster IDs
 * @returns Array of counts
 */
export async function batchGetClusterCounts(clusterIds: string[]): Promise<number[]> {
  if (clusterIds.length === 0) {
    return [];
  }

  const pipeline = redis.pipeline();

  for (const clusterId of clusterIds) {
    pipeline.scard(`cluster:items:${clusterId}`);
  }

  const results = await pipeline.exec();

  return results.map((count) => (typeof count === 'number' ? count : 0));
}

/**
 * Batch fetch cluster feedback IDs
 *
 * @param clusterIds Array of cluster IDs
 * @returns Array of feedback ID arrays
 */
export async function batchGetClusterFeedbackIds(
  clusterIds: string[]
): Promise<Array<string[]>> {
  if (clusterIds.length === 0) {
    return [];
  }

  const pipeline = redis.pipeline();

  for (const clusterId of clusterIds) {
    pipeline.smembers(`cluster:items:${clusterId}`);
  }

  const results = await pipeline.exec();

  return results.map((ids) => (Array.isArray(ids) ? ids : []));
}
