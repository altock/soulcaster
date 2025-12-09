import { Redis } from '@upstash/redis';
import { randomUUID } from 'crypto';
import type { ClusterListItem, ClusterDetail, FeedbackItem, IssueCluster } from '@/types';

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

const feedbackKey = (projectId: string, id: string) => `feedback:${projectId}:${id}`;
const feedbackCreatedKey = (projectId: string) => `feedback:created:${projectId}`;
const feedbackSourceKey = (projectId: string, source: string) => `feedback:source:${projectId}:${source}`;
const feedbackUnclusteredKey = (projectId: string) => `feedback:unclustered:${projectId}`;
const clusterKey = (projectId: string, id: string) => `cluster:${projectId}:${id}`;
const clusterItemsKey = (projectId: string, clusterId: string) => `cluster:${projectId}:${clusterId}:items`;
const clusterAllKey = (projectId: string) => `clusters:${projectId}:all`;
const redditSubredditsKey = (projectId: string) => `config:reddit:subreddits:${projectId}`;

/**
 * Get all cluster IDs for a project from Redis (newest first).
 */
export async function getClusterIds(projectId: string): Promise<string[]> {
  const ids = await redis.smembers(clusterAllKey(projectId));
  return ids as string[];
}

/**
 * Get cluster basic info from Redis hash
 */
async function getClusterHash(projectId: string, id: string): Promise<IssueCluster | null> {
  const data = await redis.hgetall(clusterKey(projectId, id));

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
    issue_title: data.issue_title as string | undefined,
    issue_description: data.issue_description as string | undefined,
    github_repo_url: data.github_repo_url as string | undefined,
  };
}

/**
 * Get feedback IDs that belong to a cluster
 */
async function getClusterFeedbackIds(projectId: string, clusterId: string): Promise<string[]> {
  const ids = await redis.smembers(clusterItemsKey(projectId, clusterId));
  return ids as string[];
}

/**
 * Get a single feedback item by ID
 */
export async function getFeedbackItem(projectId: string, id: string): Promise<FeedbackItem | null> {
  const data = await redis.hgetall(feedbackKey(projectId, id));

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
    source: data.source as 'reddit' | 'manual' | 'github',
    external_id: data.external_id as string | null | undefined,
    title: data.title as string,
    body: data.body as string,
    repo: data.repo as string | undefined,
    github_repo_url: data.github_repo_url as string | undefined,
    github_issue_number: data.github_issue_number
      ? parseInt(data.github_issue_number as string)
      : undefined,
    github_issue_url: data.github_issue_url as string | undefined,
    status: data.status as 'open' | 'closed' | undefined,
    metadata: metadata as Record<string, any>,
    created_at: data.created_at as string,
  };
}

/**
 * Get all clusters with basic info for listing
 */
export async function getClusters(projectId: string): Promise<ClusterListItem[]> {
  const clusterIds = await getClusterIds(projectId);

  const clusters = await Promise.all(
    clusterIds.map(async (id) => {
      const cluster = await getClusterHash(projectId, id);
      if (!cluster) return null;

      const feedbackIds = await getClusterFeedbackIds(projectId, id);

      // Get ALL feedback items to determine sources and repos accurately
      const feedbackItems = await Promise.all(
        feedbackIds.map((fid) => getFeedbackItem(projectId, fid))
      );

      const validItems = feedbackItems.filter((item): item is FeedbackItem => item !== null);
      const sources = Array.from(new Set(validItems.map((item) => item.source)));
      const repos = Array.from(
        new Set(validItems.map((item) => item.repo).filter((repo): repo is string => !!repo))
      );

      const item: ClusterListItem & { created_at: string } = {
        id: cluster.id,
        title: cluster.title,
        summary: cluster.summary,
        count: feedbackIds.length,
        status: cluster.status,
        sources: sources as ('reddit' | 'manual' | 'github')[],
        repos: repos.length > 0 ? repos : undefined,
        created_at: cluster.created_at,
        ...(cluster.github_pr_url && { github_pr_url: cluster.github_pr_url }),
        ...(cluster.issue_title && { issue_title: cluster.issue_title }),
        ...(cluster.issue_description && { issue_description: cluster.issue_description }),
        ...(cluster.github_repo_url && { github_repo_url: cluster.github_repo_url }),
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
export async function getClusterDetail(projectId: string, id: string): Promise<ClusterDetail | null> {
  const cluster = await getClusterHash(projectId, id);
  if (!cluster) return null;

  const feedbackIds = await getClusterFeedbackIds(projectId, id);
  const feedbackItems = await Promise.all(feedbackIds.map((fid) => getFeedbackItem(projectId, fid)));

  const validItems = feedbackItems.filter((item): item is FeedbackItem => item !== null);

  return {
    ...cluster,
    feedback_ids: feedbackIds,
    feedback_items: validItems,
  };
}

/**
 * Get feedback items with pagination and optional source/repo filters
 */
export async function getFeedback(
  projectId: string,
  limit: number = 100,
  offset: number = 0,
  source?: string,
  repo?: string
): Promise<{ items: FeedbackItem[]; total: number; limit: number; offset: number }> {
  let feedbackIds: string[];

  if (source) {
    // Get from source-specific sorted set
    const allIds = await redis.zrange(feedbackSourceKey(projectId, source), 0, -1, { rev: true });
    feedbackIds = allIds as string[];
  } else {
    // Get from global created sorted set
    const allIds = await redis.zrange(feedbackCreatedKey(projectId), 0, -1, { rev: true });
    feedbackIds = allIds as string[];
  }

  // Apply repo filter if specified
  let filteredItems: FeedbackItem[] | undefined;
  if (repo) {
    // Fetch all items and filter by repo
    const allItems = await Promise.all(feedbackIds.map((id) => getFeedbackItem(projectId, id)));
    filteredItems = allItems.filter(
      (item): item is FeedbackItem => item !== null && item.repo === repo
    );
    const filteredIds = filteredItems.map((item) => item.id);
    feedbackIds = filteredIds;
  }

  const total = feedbackIds.length;

  // Apply pagination
  const paginatedIds = feedbackIds.slice(offset, offset + limit);

  // Fetch the actual feedback items (if not already fetched for repo filtering)
  let items: (FeedbackItem | null)[];
  if (repo) {
    // Already fetched during repo filtering, just paginate the filtered items
    items = (filteredItems ?? []).slice(offset, offset + limit);
  } else {
    items = await Promise.all(paginatedIds.map((id) => getFeedbackItem(projectId, id)));
  }

  const validItems = items.filter((item): item is FeedbackItem => item !== null);

  return {
    items: validItems,
    total,
    limit,
    offset,
  };
}

/**
 * Get stats about feedback and clusters for a project.
 */
export async function getStats(projectId: string): Promise<{
  total_feedback: number;
  by_source: { reddit: number; manual: number; github: number };
  total_clusters: number;
}> {
  // Get total feedback count using ZCARD (more efficient than ZRANGE)
  const total_feedback = (await redis.zcard(feedbackCreatedKey(projectId))) || 0;

  // Get counts by source using ZCARD (more efficient than ZRANGE)
  const redditCount = (await redis.zcard(feedbackSourceKey(projectId, 'reddit'))) || 0;
  const manualCount = (await redis.zcard(feedbackSourceKey(projectId, 'manual'))) || 0;
  const githubCount = (await redis.zcard(feedbackSourceKey(projectId, 'github'))) || 0;

  // Get total clusters count using SCARD on clusters:all set (avoids KEYS command)
  const total_clusters = (await redis.scard(clusterAllKey(projectId))) || 0;

  return {
    total_feedback,
    by_source: {
      reddit: redditCount,
      manual: manualCount,
      github: githubCount,
    },
    total_clusters,
  };
}

/**
 * Get Reddit subreddits configuration from Redis
 */
export async function getRedditSubreddits(projectId: string): Promise<string[]> {
  const data = await redis.get(redditSubredditsKey(projectId));

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
export async function setRedditSubreddits(projectId: string, subreddits: string[]): Promise<void> {
  await redis.set(redditSubredditsKey(projectId), JSON.stringify(subreddits));
}

/**
 * Create a new feedback item in Redis
 */
export async function createFeedback(data: {
  project_id: string;
  title: string;
  body: string;
  github_repo_url?: string;
  source?: 'reddit' | 'manual';
  metadata?: Record<string, any>;
}): Promise<string> {
  const { project_id: projectId } = data;
  const id = randomUUID();
  const timestamp = Date.now();
  const source = data.source || 'manual';

  // Store feedback hash
  await redis.hset(feedbackKey(projectId, id), {
    id,
    project_id: projectId,
    source,
    title: data.title,
    body: data.body,
    ...(data.github_repo_url && { github_repo_url: data.github_repo_url }),
    metadata: JSON.stringify(data.metadata || {}),
    created_at: new Date(timestamp).toISOString(),
    clustered: 'false', // Track if this has been clustered
  });

  // Add to sorted sets
  await redis.zadd(feedbackCreatedKey(projectId), { score: timestamp / 1000, member: id });
  await redis.zadd(feedbackSourceKey(projectId, source), { score: timestamp / 1000, member: id });

  // Add to unclustered set
  await redis.sadd(feedbackUnclusteredKey(projectId), id);

  return id;
}

/**
 * Get count of unclustered feedback items
 */
export async function getUnclusteredCount(projectId: string): Promise<number> {
  const count = await redis.scard(feedbackUnclusteredKey(projectId));
  return count || 0;
}

/**
 * Get all unclustered feedback IDs
 */
export async function getUnclusteredFeedbackIds(projectId: string): Promise<string[]> {
  const ids = await redis.smembers(feedbackUnclusteredKey(projectId));
  return ids as string[];
}

/**
 * Update a feedback item in Redis
 */
export async function updateFeedback(projectId: string, id: string, data: Partial<FeedbackItem>): Promise<void> {
  const key = feedbackKey(projectId, id);
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
