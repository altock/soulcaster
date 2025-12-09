import { NextRequest, NextResponse } from 'next/server';
import { Redis } from '@upstash/redis';
import { fetchRepoIssues, issueToFeedbackItem, logRateLimit } from '@/lib/github';
import { getProjectId } from '@/lib/project';
import type { GitHubRepo } from '@/types';

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

// Project-scoped Redis key helpers (matching lib/redis.ts patterns)
const feedbackKey = (projectId: string, id: string) => `feedback:${projectId}:${id}`;
const feedbackCreatedKey = (projectId: string) => `feedback:created:${projectId}`;
const feedbackSourceKey = (projectId: string, source: string) => `feedback:source:${projectId}:${source}`;
const feedbackUnclusteredKey = (projectId: string) => `feedback:unclustered:${projectId}`;
const repoKey = (projectId: string, repoName: string) => `github:repo:${projectId}:${repoName}`;

/**
 * Syncs issues from the specified GitHub repository into Redis and updates repository metadata.
 *
 * @param params - An object with a URL-encoded `name` of the repository in the form "owner%2Frepo" (decoded to "owner/repo").
 * @returns A NextResponse whose JSON body reports the sync result. On success includes `success: true`, `message`, `repo`, `new_issues`, `updated_issues`, `closed_issues`, `total_issues`, and `ignored_prs`. On failure includes `success: false`, `error`, and `detail`.
 */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ name: string }> }
) {
  try {
    // Get project ID from authenticated session
    const projectId = await getProjectId(request);
    if (!projectId) {
      return NextResponse.json({ error: 'Authentication required' }, { status: 401 });
    }

    const { name } = await params;

    // Decode URL-encoded repo name
    const repoName = decodeURIComponent(name);

    console.log(`[GitHub Sync] Starting sync for ${repoName} (project: ${projectId})`);

    // Log initial rate limit
    await logRateLimit();

    // Get repo config
    const repoData = await redis.hgetall(repoKey(projectId, repoName));
    if (!repoData || Object.keys(repoData).length === 0) {
      return NextResponse.json(
        { error: 'Repository not found in configuration' },
        { status: 404 }
      );
    }

    if (repoData.enabled === 'false') {
      return NextResponse.json(
        { error: 'Repository is disabled' },
        { status: 400 }
      );
    }

    const repo: GitHubRepo = {
      owner: repoData.owner as string,
      repo: repoData.repo as string,
      full_name: repoName,
      last_synced: repoData.last_synced as string | undefined,
      issue_count: repoData.issue_count ? parseInt(repoData.issue_count as string) : 0,
      enabled: true,
    };

    // Fetch issues (incremental if last_synced exists)
    const { issues, prCount } = await fetchRepoIssues(repo.owner, repo.repo, repo.last_synced);

    let newCount = 0;
    let updatedCount = 0;
    let closedCount = 0;

    // Process each issue
    for (const issue of issues) {
      const feedbackItem = issueToFeedbackItem(issue, repo.full_name);

      // Check if issue already exists in Redis
      const existingFeedback = await redis.hgetall(feedbackKey(projectId, feedbackItem.id));
      const exists = existingFeedback && Object.keys(existingFeedback).length > 0;

      // Store feedback item
      await redis.hset(feedbackKey(projectId, feedbackItem.id), {
        id: feedbackItem.id,
        project_id: projectId,
        source: feedbackItem.source,
        external_id: feedbackItem.external_id || '',
        title: feedbackItem.title,
        body: feedbackItem.body,
        repo: feedbackItem.repo || '',
        github_issue_number: feedbackItem.github_issue_number?.toString() || '',
        github_issue_url: feedbackItem.github_issue_url || '',
        status: feedbackItem.status || 'open',
        metadata: JSON.stringify(feedbackItem.metadata),
        created_at: feedbackItem.created_at,
        clustered: exists ? (existingFeedback.clustered as string) : 'false', // Preserve clustering state
      });

      // Add to created sorted set (by timestamp)
      const timestamp = new Date(feedbackItem.created_at).getTime();
      await redis.zadd(feedbackCreatedKey(projectId), { score: timestamp, member: feedbackItem.id });

      // Add to source-specific sorted set for filtering
      await redis.zadd(feedbackSourceKey(projectId, 'github'), { score: timestamp, member: feedbackItem.id });

      // Manage unclustered set based on issue status
      if (feedbackItem.status === 'closed') {
        // Remove closed issues from unclustered set
        await redis.srem(feedbackUnclusteredKey(projectId), feedbackItem.id);
        closedCount++;
      } else if (!exists) {
        // New open issue - add to unclustered
        await redis.sadd(feedbackUnclusteredKey(projectId), feedbackItem.id);
        newCount++;
      } else {
        // Existing open issue - updated
        updatedCount++;
      }
    }

    // Update repo metadata
    const now = new Date().toISOString();
    await redis.hset(repoKey(projectId, repoName), {
      last_synced: now,
      issue_count: (repo.issue_count || 0) + newCount,
    });

    console.log(
      `[GitHub Sync] ${repoName}: ${newCount} new, ${updatedCount} updated, ${closedCount} closed`
    );

    // Log final rate limit
    await logRateLimit();

    return NextResponse.json({
      success: true,
      message: `Sync completed for ${repoName}`,
      repo: repoName,
      new_issues: newCount,
      updated_issues: updatedCount,
      closed_issues: closedCount,
      total_issues: issues.length,
      ignored_prs: prCount,
    });
  } catch (error) {
    console.error('[GitHub Sync] Error during sync:', error);
    return NextResponse.json(
      {
        success: false,
        error: 'Sync failed',
        detail: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}