import { Redis } from '@upstash/redis';
import { randomUUID } from 'crypto';
import type { ClusterListItem, ClusterDetail, FeedbackItem, IssueCluster } from '@/types';

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

/**
 * Get all cluster IDs from Redis sorted by creation time (newest first)
 */
export async function getClusterIds(): Promise<string[]> {
  // Use clusters:all set to avoid KEYS command which blocks Redis
  const ids = await redis.smembers('clusters:all');
  return ids as string[];
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
    github_repo_url: data.github_repo_url as string | undefined,
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

      const item: ClusterListItem & { created_at: string } = {
        id: cluster.id,
        title: cluster.title,
        summary: cluster.summary,
        count: feedbackIds.length,
        status: cluster.status,
        sources: sources as ('reddit' | 'sentry' | 'manual')[],
        created_at: cluster.created_at,
        ...(cluster.github_pr_url && { github_pr_url: cluster.github_pr_url }),
      };
      return item;
    })
  );

  // Filter out nulls and sort by creation time (newest first)
  const validClusters = clusters.filter(
    (c): c is ClusterListItem & { created_at: string } => c !== null
  );

  // Sort by created_at timestamp (newest first)
  validClusters.sort((a, b) => {
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });

  // Remove created_at from return type to match ClusterListItem
  return validClusters.map(({ created_at, ...item }) => item);
}

/**
 * Get detailed cluster info including all feedback items
 */
export async function getClusterDetail(id: string): Promise<ClusterDetail | null> {
  const cluster = await getClusterHash(id);
  if (!cluster) return null;

  const feedbackIds = await getClusterFeedbackIds(id);
  const feedbackItems = await Promise.all(feedbackIds.map((fid) => getFeedbackItem(fid)));

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
  const items = await Promise.all(paginatedIds.map((id) => getFeedbackItem(id)));

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
  // Get total feedback count using ZCARD (more efficient than ZRANGE)
  const total_feedback = (await redis.zcard('feedback:created')) || 0;

  // Get counts by source using ZCARD (more efficient than ZRANGE)
  const redditCount = (await redis.zcard('feedback:source:reddit')) || 0;
  const sentryCount = (await redis.zcard('feedback:source:sentry')) || 0;
  const manualCount = (await redis.zcard('feedback:source:manual')) || 0;

  // Get total clusters count using SCARD on clusters:all set (avoids KEYS command)
  const total_clusters = (await redis.scard('clusters:all')) || 0;

  return {
    total_feedback,
    by_source: {
      reddit: redditCount,
      sentry: sentryCount,
      manual: manualCount,
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
  github_repo_url?: string;
  source?: 'reddit' | 'sentry' | 'manual';
  metadata?: Record<string, any>;
}): Promise<string> {
  const id = randomUUID();
  const timestamp = Date.now();
  const source = data.source || 'manual';

  // Store feedback hash
  await redis.hset(`feedback:${id}`, {
    id,
    source,
    title: data.title,
    body: data.body,
    ...(data.github_repo_url && { github_repo_url: data.github_repo_url }),
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

/**
 * Update a feedback item in Redis
 */
export async function updateFeedback(id: string, data: Partial<FeedbackItem>): Promise<void> {
  const key = `feedback:${id}`;
  const exists = await redis.exists(key);

  if (!exists) {
    throw new Error(`Feedback item ${id} not found`);
  }

  // Prepare update object
  const update: Record<string, any> = {};
  if (data.body !== undefined) update.body = data.body;
  if (data.github_repo_url !== undefined) update.github_repo_url = data.github_repo_url;

  // If we're updating metadata, we need to merge or replace. 
  // For simplicity, let's assume we might update specific fields if needed, 
  // but for this task we are primarily updating body and repo url.

  if (Object.keys(update).length > 0) {
    await redis.hset(key, update);
  }
}
