import { NextResponse } from 'next/server';
import { Redis } from '@upstash/redis';
import { fetchRepoIssues, issueToFeedbackItem, logRateLimit } from '@/lib/github';
import type { GitHubRepo } from '@/types';

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

/**
 * Synchronizes all enabled GitHub repositories stored in Redis and ingests their issues as feedback items.
 *
 * Processes each enabled repo found in the `github:repos` set: fetches new or updated issues (ignoring PRs),
 * stores or updates feedback records in Redis, updates clustering and auxiliary sorted/sets, and updates
 * per-repo metadata (last_synced and issue_count). Logs rate limit before and after processing and returns
 * a per-repo summary including counts of new, updated, and closed issues.
 *
 * @returns A JSON object describing the outcome. On success: `{ success: true, message: 'Sync completed', total_new, total_updated, total_closed, repos }`
 * where `repos` is an array of per-repo result objects (`{ repo, new, updated, closed, total, ignored_prs }`) or error entries for repos that failed. On failure: `{ success: false, error, detail }`.
 */
export async function POST() {
  try {
    console.log('[GitHub Sync] Starting sync for all repos');

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

    // Fetch repo configs
    const repos: GitHubRepo[] = [];
    for (const repoName of repoNames) {
      const repoData = await redis.hgetall(`github:repo:${repoName}`);
      if (repoData && repoData.enabled === 'true') {
        repos.push({
          owner: repoData.owner as string,
          repo: repoData.repo as string,
          full_name: repoName,
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

        let newCount = 0;
        let updatedCount = 0;
        let closedCount = 0;

        // Process each issue
        for (const issue of issues) {
          const feedbackItem = issueToFeedbackItem(issue, repo.full_name);

          // Check if issue already exists in Redis
          const existingFeedback = await redis.hgetall(`feedback:${feedbackItem.id}`);
          const exists = existingFeedback && Object.keys(existingFeedback).length > 0;

          // Store feedback item
          await redis.hset(`feedback:${feedbackItem.id}`, {
            id: feedbackItem.id,
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
          await redis.zadd('feedback:created', { score: timestamp, member: feedbackItem.id });

          // Add to source-specific sorted set for filtering
          await redis.zadd('feedback:source:github', { score: timestamp, member: feedbackItem.id });

          // Manage unclustered set based on issue status
          if (feedbackItem.status === 'closed') {
            // Remove closed issues from unclustered set
            await redis.srem('feedback:unclustered', feedbackItem.id);
            closedCount++;
          } else if (!exists) {
            // New open issue - add to unclustered
            await redis.sadd('feedback:unclustered', feedbackItem.id);
            newCount++;
          } else {
            // Existing open issue - updated
            updatedCount++;
          }
        }

        // Update repo metadata
        const now = new Date().toISOString();
        await redis.hset(`github:repo:${repo.full_name}`, {
          last_synced: now,
          issue_count: (repo.issue_count || 0) + newCount,
        });

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