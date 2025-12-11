import { NextRequest, NextResponse } from 'next/server';
import { Redis } from '@upstash/redis';
import { fetchRepoIssues, issueToFeedbackItem, logRateLimit } from '@/lib/github';
import { getProjectId } from '@/lib/project';
import type { GitHubRepo, FeedbackItem } from '@/types';

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
 * Synchronizes all enabled GitHub repositories stored in Redis and ingests their issues as feedback items.
 *
 * Uses Redis pipelining to batch operations for better performance:
 * - Batch fetches repo configs in a single pipeline
 * - Batch checks for existing issues in a single pipeline  
 * - Batch writes all issue data in a single pipeline per repo
 *
 * @returns A JSON object describing the outcome. On success: `{ success: true, message: 'Sync completed', total_new, total_updated, total_closed, repos }`
 * where `repos` is an array of per-repo result objects (`{ repo, new, updated, closed, total, ignored_prs }`) or error entries for repos that failed. On failure: `{ success: false, error, detail }`.
 */
export async function POST(request: NextRequest) {
  try {
    // Get project ID from authenticated session
    const projectId = await getProjectId(request);
    if (!projectId) {
      return NextResponse.json({ error: 'Authentication required' }, { status: 401 });
    }

    console.log(`[GitHub Sync] Starting sync for all repos (project: ${projectId})`);

    // Log initial rate limit
    await logRateLimit();

    // Get all configured repos
    const repoNames = (await redis.smembers('github:repos')) as string[];
    console.log(`[GitHub Sync] Found ${repoNames.length} configured repos`);

    if (repoNames.length === 0) {
      return NextResponse.json({
        success: true,
        message: 'No repositories configured',
        synced: [],
      });
    }

    // OPTIMIZATION: Batch fetch all repo configs in a single pipeline
    const repoConfigPipeline = redis.pipeline();
    for (const repoName of repoNames) {
      repoConfigPipeline.hgetall(repoKey(projectId, repoName));
    }
    const repoConfigResults = await repoConfigPipeline.exec();

    const repos: GitHubRepo[] = [];
    for (let i = 0; i < repoNames.length; i++) {
      const repoData = repoConfigResults[i] as Record<string, string> | null;
      if (repoData && repoData.enabled === 'true') {
        repos.push({
          owner: repoData.owner as string,
          repo: repoData.repo as string,
          full_name: repoNames[i],
          last_synced: repoData.last_synced as string | undefined,
          issue_count: repoData.issue_count ? parseInt(repoData.issue_count as string) : 0,
          enabled: true,
        });
      }
    }

    console.log(`[GitHub Sync] Syncing ${repos.length} enabled repos`);

    const results = [];
    let totalNew = 0;
    let totalUpdated = 0;
    let totalClosed = 0;

    // Sync each repo
    for (const repo of repos) {
      try {
        console.log(`[GitHub Sync] Syncing ${repo.full_name}...`);

        // Fetch issues (incremental if last_synced exists)
        const { issues, prCount } = await fetchRepoIssues(repo.owner, repo.repo, repo.last_synced);

        if (issues.length === 0) {
          results.push({
            repo: repo.full_name,
            new: 0,
            updated: 0,
            closed: 0,
            total: 0,
            ignored_prs: prCount,
          });
          continue;
        }

        // Convert issues to feedback items
        const feedbackItems: FeedbackItem[] = issues.map((issue) =>
          issueToFeedbackItem(issue, repo.full_name)
        );

        // OPTIMIZATION: Batch check for existing issues in a single pipeline
        const existsCheckPipeline = redis.pipeline();
        for (const item of feedbackItems) {
          existsCheckPipeline.hget(feedbackKey(projectId, item.id), 'clustered');
        }
        const existsResults = await existsCheckPipeline.exec();

        // Prepare batch write pipeline
        const writePipeline = redis.pipeline();
        let newCount = 0;
        let updatedCount = 0;
        let closedCount = 0;

        for (let i = 0; i < feedbackItems.length; i++) {
          const feedbackItem = feedbackItems[i];
          const existingClusteredValue = existsResults[i] as string | null;
          const exists = existingClusteredValue !== null;

          // Store feedback item
          writePipeline.hset(feedbackKey(projectId, feedbackItem.id), {
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
            clustered: exists ? existingClusteredValue : 'false', // Preserve clustering state
          });

          // Add to created sorted set (by timestamp)
          const timestamp = new Date(feedbackItem.created_at).getTime();
          writePipeline.zadd(feedbackCreatedKey(projectId), { score: timestamp, member: feedbackItem.id });

          // Add to source-specific sorted set for filtering
          writePipeline.zadd(feedbackSourceKey(projectId, 'github'), {
            score: timestamp,
            member: feedbackItem.id,
          });

          // Manage unclustered set based on issue status
          if (feedbackItem.status === 'closed') {
            // Remove closed issues from unclustered set
            writePipeline.srem(feedbackUnclusteredKey(projectId), feedbackItem.id);
            closedCount++;
          } else if (!exists) {
            // New open issue - add to unclustered
            writePipeline.sadd(feedbackUnclusteredKey(projectId), feedbackItem.id);
            newCount++;
          } else {
            // Existing open issue - updated
            updatedCount++;
          }
        }

        // Update repo metadata
        const now = new Date().toISOString();
        writePipeline.hset(repoKey(projectId, repo.full_name), {
          last_synced: now,
          issue_count: (repo.issue_count || 0) + newCount,
        });

        // Execute all writes in a single batch
        await writePipeline.exec();

        results.push({
          repo: repo.full_name,
          new: newCount,
          updated: updatedCount,
          closed: closedCount,
          total: issues.length,
          ignored_prs: prCount,
        });

        totalNew += newCount;
        totalUpdated += updatedCount;
        totalClosed += closedCount;

        console.log(
          `[GitHub Sync] ${repo.full_name}: ${newCount} new, ${updatedCount} updated, ${closedCount} closed`
        );
      } catch (error) {
        console.error(`[GitHub Sync] Error syncing ${repo.full_name}:`, error);
        results.push({
          repo: repo.full_name,
          error: error instanceof Error ? error.message : 'Unknown error',
        });
      }
    }

    // Log final rate limit
    await logRateLimit();

    console.log('[GitHub Sync] Sync complete');

    return NextResponse.json({
      success: true,
      message: 'Sync completed',
      total_new: totalNew,
      total_updated: totalUpdated,
      total_closed: totalClosed,
      repos: results,
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