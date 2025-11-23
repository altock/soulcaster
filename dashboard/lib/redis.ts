import { Redis } from '@upstash/redis';
import type { ClusterListItem, ClusterDetail, FeedbackItem, IssueCluster } from '@/types';

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

/**
 * Get all cluster IDs from Redis sorted by creation time (newest first)
 */
export async function getClusterIds(): Promise<string[]> {
  // Redis stores clusters as individual hashes with keys like cluster:{uuid}
  // We need to scan for all cluster keys
  const keys = await redis.keys('cluster:*');

  // Filter out cluster:items: keys, we only want cluster:{id} keys
  const clusterKeys = keys.filter((key) => !key.includes(':items:'));

  // Extract IDs from keys
  const ids = clusterKeys.map((key) => key.replace('cluster:', ''));

  return ids;
}

/**
 * Get cluster basic info from Redis hash
 */
async function getClusterHash(id: string): Promise<IssueCluster | null> {
  const data = await redis.hgetall(`cluster:${id}`);

  if (!data || Object.keys(data).length === 0) {
    return null;
  }

  return {
    id: data.id as string,
    title: data.title as string,
    summary: data.summary as string,
    feedback_ids: [], // Will be populated from separate set
    status: data.status as 'new' | 'fixing' | 'pr_opened' | 'failed',
    created_at: data.created_at as string,
    updated_at: data.updated_at as string,
    github_branch: data.github_branch as string | undefined,
    github_pr_url: data.github_pr_url as string | undefined,
    error_message: data.error_message as string | undefined,
  };
}

/**
 * Get feedback IDs that belong to a cluster
 */
async function getClusterFeedbackIds(clusterId: string): Promise<string[]> {
  const ids = await redis.smembers(`cluster:items:${clusterId}`);
  return ids as string[];
}

/**
 * Get a single feedback item by ID
 */
export async function getFeedbackItem(id: string): Promise<FeedbackItem | null> {
  const data = await redis.hgetall(`feedback:${id}`);

  if (!data || Object.keys(data).length === 0) {
    return null;
  }

  // Parse metadata JSON if it's a string
  let metadata = data.metadata;
  if (typeof metadata === 'string') {
    try {
      metadata = JSON.parse(metadata);
    } catch {
      metadata = {};
    }
  }

  return {
    id: data.id as string,
    source: data.source as 'reddit' | 'sentry' | 'manual',
    external_id: data.external_id as string | null | undefined,
    title: data.title as string,
    body: data.body as string,
    metadata: metadata as Record<string, any>,
    created_at: data.created_at as string,
  };
}

/**
 * Get all clusters with basic info for listing
 */
export async function getClusters(): Promise<ClusterListItem[]> {
  const clusterIds = await getClusterIds();

  const clusters = await Promise.all(
    clusterIds.map(async (id) => {
      const cluster = await getClusterHash(id);
      if (!cluster) return null;

      const feedbackIds = await getClusterFeedbackIds(id);

      // Get first few feedback items to determine sources
      const feedbackItems = await Promise.all(
        feedbackIds.slice(0, 10).map((fid) => getFeedbackItem(fid))
      );

      const validItems = feedbackItems.filter((item): item is FeedbackItem => item !== null);
      const sources = Array.from(new Set(validItems.map((item) => item.source)));

      const item: ClusterListItem = {
        id: cluster.id,
        title: cluster.title,
        summary: cluster.summary,
        count: feedbackIds.length,
        status: cluster.status,
        sources: sources as ('reddit' | 'sentry' | 'manual')[],
        ...(cluster.github_pr_url && { github_pr_url: cluster.github_pr_url }),
      };
      return item;
    })
  );

  // Filter out nulls and sort by creation time (newest first)
  const validClusters = clusters.filter((c): c is ClusterListItem => c !== null);

  return validClusters;
}

/**
 * Get detailed cluster info including all feedback items
 */
export async function getClusterDetail(id: string): Promise<ClusterDetail | null> {
  const cluster = await getClusterHash(id);
  if (!cluster) return null;

  const feedbackIds = await getClusterFeedbackIds(id);
  const feedbackItems = await Promise.all(
    feedbackIds.map((fid) => getFeedbackItem(fid))
  );

  const validItems = feedbackItems.filter((item): item is FeedbackItem => item !== null);

  return {
    ...cluster,
    feedback_ids: feedbackIds,
    feedback_items: validItems,
  };
}

/**
 * Get feedback items with pagination and optional source filter
 */
export async function getFeedback(
  limit: number = 100,
  offset: number = 0,
  source?: string
): Promise<{ items: FeedbackItem[]; total: number; limit: number; offset: number }> {
  let feedbackIds: string[];

  if (source) {
    // Get from source-specific sorted set
    const allIds = await redis.zrange(`feedback:source:${source}`, 0, -1, { rev: true });
    feedbackIds = allIds as string[];
  } else {
    // Get from global created sorted set
    const allIds = await redis.zrange('feedback:created', 0, -1, { rev: true });
    feedbackIds = allIds as string[];
  }

  const total = feedbackIds.length;

  // Apply pagination
  const paginatedIds = feedbackIds.slice(offset, offset + limit);

  // Fetch the actual feedback items
  const items = await Promise.all(
    paginatedIds.map((id) => getFeedbackItem(id))
  );

  const validItems = items.filter((item): item is FeedbackItem => item !== null);

  return {
    items: validItems,
    total,
    limit,
    offset,
  };
}

/**
 * Get stats about feedback and clusters
 */
export async function getStats(): Promise<{
  total_feedback: number;
  by_source: { reddit: number; sentry: number; manual: number };
  total_clusters: number;
}> {
  // Get total feedback count
  const allFeedbackIds = await redis.zrange('feedback:created', 0, -1);
  const total_feedback = allFeedbackIds.length;

  // Get counts by source
  const redditIds = await redis.zrange('feedback:source:reddit', 0, -1);
  const sentryIds = await redis.zrange('feedback:source:sentry', 0, -1);
  const manualIds = await redis.zrange('feedback:source:manual', 0, -1);

  // Get total clusters count
  const clusterKeys = await redis.keys('cluster:*');
  const clusterOnlyKeys = clusterKeys.filter((key) => !key.includes(':items:'));
  const total_clusters = clusterOnlyKeys.length;

  return {
    total_feedback,
    by_source: {
      reddit: redditIds.length,
      sentry: sentryIds.length,
      manual: manualIds.length,
    },
    total_clusters,
  };
}

/**
 * Get Reddit subreddits configuration from Redis
 */
export async function getRedditSubreddits(): Promise<string[]> {
  const data = await redis.get('config:reddit:subreddits');

  if (!data) {
    return [];
  }

  // Parse if it's a JSON string
  if (typeof data === 'string') {
    try {
      return JSON.parse(data);
    } catch {
      return [];
    }
  }

  // If it's already an array
  if (Array.isArray(data)) {
    return data;
  }

  return [];
}

/**
 * Set Reddit subreddits configuration in Redis
 */
export async function setRedditSubreddits(subreddits: string[]): Promise<void> {
  await redis.set('config:reddit:subreddits', JSON.stringify(subreddits));
}

/**
 * Create a new feedback item in Redis
 */
export async function createFeedback(data: {
  title: string;
  body: string;
  source?: 'reddit' | 'sentry' | 'manual';
  metadata?: Record<string, any>;
}): Promise<string> {
  const id = `feedback-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  const timestamp = Date.now();
  const source = data.source || 'manual';

  // Store feedback hash
  await redis.hset(`feedback:${id}`, {
    id,
    source,
    title: data.title,
    body: data.body,
    metadata: JSON.stringify(data.metadata || {}),
    created_at: new Date(timestamp).toISOString(),
    clustered: 'false', // Track if this has been clustered
  });

  // Add to sorted sets
  await redis.zadd('feedback:created', { score: timestamp / 1000, member: id });
  await redis.zadd(`feedback:source:${source}`, { score: timestamp / 1000, member: id });

  // Add to unclustered set
  await redis.sadd('feedback:unclustered', id);

  return id;
}

/**
 * Get count of unclustered feedback items
 */
export async function getUnclusteredCount(): Promise<number> {
  const count = await redis.scard('feedback:unclustered');
  return count || 0;
}

/**
 * Get all unclustered feedback IDs
 */
export async function getUnclusteredFeedbackIds(): Promise<string[]> {
  const ids = await redis.smembers('feedback:unclustered');
  return ids as string[];
}

