import { NextRequest, NextResponse } from 'next/server';
import { Redis } from '@upstash/redis';
import { getGitHubToken } from '@/lib/auth';
import { getProjectId } from '@/lib/project';
import type { GitHubRepo } from '@/types';

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';

// Project-scoped Redis key helpers (matching lib/redis.ts patterns)
const repoKey = (projectId: string, repoName: string) => `github:repo:${projectId}:${repoName}`;
const projectReposKey = (projectId: string) => `github:repos:${projectId}`;
const legacyReposKey = 'github:repos';
const legacyRepoKey = (repoName: string) => `github:repo:${repoName}`;

async function migrateLegacyReposToProject(projectId: string, existing: string[] = []): Promise<string[]> {
  const legacyNames = (await redis.smembers(legacyReposKey)) as string[];
  if (!legacyNames || legacyNames.length === 0) return [];

  const existingSet = new Set(existing);
  const migrated: string[] = [];
  for (const name of legacyNames) {
    if (existingSet.has(name)) continue;
    const legacyData = await redis.hgetall(legacyRepoKey(name));
    if (legacyData && Object.keys(legacyData).length > 0) {
      await redis.hset(repoKey(projectId, name), {
        ...legacyData,
        enabled: legacyData.enabled ?? 'true',
      });
      migrated.push(name);
    }
  }

  if (migrated.length > 0) {
    const pipeline = redis.pipeline();
    migrated.forEach((name) => pipeline.sadd(projectReposKey(projectId), name));
    await pipeline.exec();
  }

  return migrated;
}

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

    const githubToken = await getGitHubToken();
    if (!githubToken) {
      return NextResponse.json(
        { error: 'GitHub authentication required. Please sign in with GitHub.' },
        { status: 401 }
      );
    }

    console.log(`[GitHub Sync] Starting sync for all repos (project: ${projectId})`);

    // Get all configured repos
    let repoNames = (await redis.smembers(projectReposKey(projectId))) as string[];
    const migrated = await migrateLegacyReposToProject(projectId, repoNames);
    if (migrated.length > 0) {
      const deduped = new Set<string>([...repoNames, ...migrated]);
      repoNames = Array.from(deduped);
    }
    console.log(`[GitHub Sync] Found ${repoNames.length} configured repos for project ${projectId}`);

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
    const repoConfigResults = (await repoConfigPipeline.exec()) as Array<Record<string, string> | null>;

    const repos: GitHubRepo[] = [];
    for (let i = 0; i < repoNames.length; i++) {
      const raw = repoConfigResults[i];
      let repoData: Record<string, string> | null =
        raw && Object.keys(raw).length > 0 ? (raw as Record<string, string>) : null;

      // Fallback to legacy repo hash if project-scoped hash is missing
      if (!repoData || Object.keys(repoData).length === 0) {
        const legacyData = (await redis.hgetall(legacyRepoKey(repoNames[i]))) as Record<string, string>;
        if (legacyData && Object.keys(legacyData).length > 0) {
          repoData = legacyData;
          // Persist into project scope for future runs
          await redis.hset(repoKey(projectId, repoNames[i]), {
            ...legacyData,
            enabled: legacyData.enabled ?? 'true',
          });
        }
      }

      const enabled = repoData ? repoData.enabled !== 'false' : false;

      if (repoData && enabled) {
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

    console.log(`[GitHub Sync] Syncing ${repos.length} enabled repos: ${repos.map(r => r.full_name).join(', ')}`);

    const results = [];
    let totalNew = 0;
    let totalUpdated = 0;
    let totalClosed = 0;

    // Sync each repo
    for (const repo of repos) {
      try {
        const url = `${backendUrl}/ingest/github/sync/${encodeURIComponent(
          repo.full_name
        )}?project_id=${projectId}`;

        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-GitHub-Token': githubToken,
          },
          signal: AbortSignal.timeout(60000), // allow large repos
        });

        if (!response.ok) {
          console.error(`[GitHub Sync] Backend returned ${response.status} for ${repo.full_name}`);
          results.push({
            repo: repo.full_name,
            error: 'Sync failed',
          });
          continue;
        }

        const data = await response.json();
        const newCount = data.new_issues ?? 0;
        const updatedCount = data.updated_issues ?? 0;
        const closedCount = data.closed_issues ?? 0;
        const ignoredPrs = data.ignored_prs ?? 0;
        const totalIssues = data.total_issues ?? 0;

        results.push({
          repo: repo.full_name,
          new: newCount,
          updated: updatedCount,
          closed: closedCount,
          total: totalIssues,
          ignored_prs: ignoredPrs,
        });

        totalNew += newCount;
        totalUpdated += updatedCount;
        totalClosed += closedCount;

        console.log(
          `[GitHub Sync] ${repo.full_name}: new=${newCount}, updated=${updatedCount}, closed=${closedCount}, total=${totalIssues}, ignored_prs=${ignoredPrs}`
        );
      } catch (error) {
        console.error(`[GitHub Sync] Error syncing ${repo.full_name}:`, error);
        results.push({
          repo: repo.full_name,
          error: error instanceof Error ? error.message : 'Unknown error',
        });
      }
    }

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