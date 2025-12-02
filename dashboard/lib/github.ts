import { Octokit } from 'octokit';
import type { FeedbackItem, GitHubRepo } from '@/types';
import { getGitHubToken } from '@/lib/auth';

/**
 * Initialize Octokit with optional authentication
 * Using GITHUB_TOKEN provides higher rate limits (5000 req/hr vs 60 req/hr)
 */
async function getOctokit() {
  const token = await getGitHubToken();

  return new Octokit({
    auth: token,
    userAgent: 'FeedbackAgent/1.0',
  });
}

/**
 * Validate that a GitHub repository exists and is accessible
 * @throws Error if repo doesn't exist or is not accessible
 */
export async function validateRepo(owner: string, repo: string): Promise<boolean> {
  const octokit = await getOctokit();

  try {
    await octokit.rest.repos.get({ owner, repo });
    return true;
  } catch (error: any) {
    if (error.status === 404) {
      throw new Error(`Repository ${owner}/${repo} not found or not accessible`);
    }
    throw new Error(`Failed to validate repository: ${error.message}`);
  }
}

/**
 * Parse repo string into owner and repo parts
 * Accepts formats: "owner/repo" or "https://github.com/owner/repo"
 */
export function parseRepoString(repoString: string): { owner: string; repo: string } {
  // Handle GitHub URLs
  const urlMatch = repoString.match(/github\.com\/([^\/]+)\/([^\/\s]+)/);
  if (urlMatch) {
    return { owner: urlMatch[1], repo: urlMatch[2].replace(/\.git$/, '') };
  }

  // Handle "owner/repo" format
  const parts = repoString.trim().split('/');
  if (parts.length !== 2) {
    throw new Error('Invalid repo format. Use "owner/repo" or GitHub URL');
  }

  const [owner, repo] = parts;
  if (!owner || !repo) {
    throw new Error('Owner and repo name cannot be empty');
  }

  return { owner, repo };
}

/**
 * Fetch all open issues from a GitHub repository
 * Filters out pull requests (GitHub API returns PRs in issues endpoint)
 */
export async function fetchRepoIssues(
  owner: string,
  repo: string,
  since?: string
): Promise<any[]> {
  const octokit = await getOctokit();

  console.log(`[GitHub] Fetching issues for ${owner}/${repo}${since ? ` since ${since}` : ''}`);

  try {
    const options: any = {
      owner,
      repo,
      state: 'all', // Fetch both open and closed to track status changes
      per_page: 100,
      sort: 'updated',
      direction: 'desc',
    };

    // Only fetch issues updated since last sync for incremental updates
    if (since) {
      options.since = since;
    }

    const issues = await octokit.paginate(
      octokit.rest.issues.listForRepo,
      options
    );

    // Filter out pull requests
    const issuesOnly = issues.filter((issue: any) => !issue.pull_request);

    console.log(`[GitHub] Fetched ${issuesOnly.length} issues (filtered ${issues.length - issuesOnly.length} PRs)`);

    return issuesOnly;
  } catch (error: any) {
    console.error(`[GitHub] Error fetching issues for ${owner}/${repo}:`, error.message);
    throw new Error(`Failed to fetch issues: ${error.message}`);
  }
}

/**
 * Get current GitHub API rate limit status
 */
export async function getRateLimitStatus(): Promise<{
  limit: number;
  remaining: number;
  reset: Date;
  used: number;
}> {
  const octokit = await getOctokit();

  try {
    const { data } = await octokit.rest.rateLimit.get();
    const core = data.resources.core;

    return {
      limit: core.limit,
      remaining: core.remaining,
      reset: new Date(core.reset * 1000),
      used: core.used,
    };
  } catch (error: any) {
    console.error('[GitHub] Failed to fetch rate limit:', error.message);
    throw error;
  }
}

/**
 * Log current rate limit status
 */
export async function logRateLimit(): Promise<void> {
  try {
    const rateLimit = await getRateLimitStatus();
    console.log(
      `[GitHub] Rate limit: ${rateLimit.remaining}/${rateLimit.limit} remaining ` +
      `(resets at ${rateLimit.reset.toISOString()})`
    );
  } catch (error) {
    // Don't fail if we can't get rate limit
    console.warn('[GitHub] Could not fetch rate limit status');
  }
}

/**
 * Convert GitHub issue to FeedbackItem format
 */
export function issueToFeedbackItem(issue: any, repoFullName: string): FeedbackItem {
  const feedbackId = `github-${repoFullName}-${issue.number}`;

  return {
    id: feedbackId,
    source: 'github',
    external_id: issue.id.toString(),
    title: issue.title,
    body: issue.body || '',
    repo: repoFullName,
    github_issue_number: issue.number,
    github_issue_url: issue.html_url,
    status: issue.state as 'open' | 'closed',
    metadata: {
      labels: issue.labels?.map((l: any) => l.name) || [],
      state: issue.state,
      comments: issue.comments || 0,
      created_at: issue.created_at,
      updated_at: issue.updated_at,
      author: issue.user?.login || 'unknown',
      assignees: issue.assignees?.map((a: any) => a.login) || [],
      milestone: issue.milestone?.title || null,
    },
    created_at: issue.created_at,
  };
}

/**
 * Sync issues from a GitHub repository to Redis
 * Returns count of new, updated, and closed issues
 */
export async function syncRepoIssues(
  repoConfig: GitHubRepo
): Promise<{
  new_issues: number;
  updated_issues: number;
  closed_issues: number;
  total_issues: number;
}> {
  const { owner, repo, full_name, last_synced } = repoConfig;

  console.log(`[GitHub] Starting sync for ${full_name}`);

  // Log rate limit before sync
  await logRateLimit();

  // Fetch issues (incremental if last_synced exists)
  const issues = await fetchRepoIssues(owner, repo, last_synced);

  let newCount = 0;
  let updatedCount = 0;
  let closedCount = 0;

  // Process each issue
  for (const issue of issues) {
    const feedbackItem = issueToFeedbackItem(issue, full_name);

    // Track counts based on state
    if (issue.state === 'closed') {
      closedCount++;
    } else if (!last_synced) {
      // First sync - all open issues are "new"
      newCount++;
    } else {
      // Incremental sync - updated issues
      updatedCount++;
    }
  }

  console.log(
    `[GitHub] Sync complete for ${full_name}: ` +
    `${newCount} new, ${updatedCount} updated, ${closedCount} closed`
  );

  // Log rate limit after sync
  await logRateLimit();

  return {
    new_issues: newCount,
    updated_issues: updatedCount,
    closed_issues: closedCount,
    total_issues: issues.length,
  };
}
