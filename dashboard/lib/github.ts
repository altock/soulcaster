import { Octokit } from 'octokit';
import type { FeedbackItem, GitHubRepo } from '@/types';
import { getGitHubToken } from '@/lib/auth';

/**
 * Create an Octokit client configured with an optional GitHub token and a FeedbackAgent user agent.
 *
 * Using a token increases API rate limits (e.g., authenticated requests have higher limits than anonymous requests).
 *
 * @returns An Octokit client configured with `auth` (if a token is available) and `userAgent: 'FeedbackAgent/1.0'`.
 */
async function getOctokit() {
  const token = await getGitHubToken();

  return new Octokit({
    auth: token,
    userAgent: 'FeedbackAgent/1.0',
  });
}

/**
 * Verify that the specified GitHub repository exists and is accessible.
 *
 * @returns `true` if the repository exists and is accessible.
 * @throws Error if the repository is not found or not accessible (HTTP 404), or if validation fails for another reason.
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
 * Parse a repository identifier into its owner and repo components.
 *
 * Accepts "owner/repo" or a GitHub URL like "https://github.com/owner/repo" (optional trailing ".git").
 *
 * @param repoString - The repository string to parse.
 * @returns An object with `owner` and `repo` properties.
 * @throws Error if the format is not "owner/repo" or a valid GitHub URL, or if either part is empty.
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
 * Retrieve issues from a GitHub repository, excluding pull requests.
 *
 * Fetches both open and closed issues for the given repository and returns the list
 * with pull requests removed. Optionally restricts results to issues updated since
 * the provided timestamp.
 *
 * @param since - Optional ISO 8601 timestamp; when provided, only issues updated since this time are returned
 * @param maxIssues - Maximum number of issues to fetch (default: 200). Set to prevent timeouts on large repos.
 * @returns An object containing `issues` — an array of issue objects with pull requests removed, and `prCount` — the number of pull requests filtered out
 */
export async function fetchRepoIssues(
  owner: string,
  repo: string,
  since?: string,
  maxIssues: number = 200
): Promise<{ issues: any[]; prCount: number }> {
  const octokit = await getOctokit();
  const token = await getGitHubToken();

  console.log(`[GitHub] Fetching issues for ${owner}/${repo}${since ? ` since ${since}` : ''} (max: ${maxIssues})`);
  console.log(`[GitHub] Using token: ${token ? 'Yes' : 'No'}`);

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

    // Use paginate with a custom iterator to limit total issues fetched
    // This prevents timeouts on large repositories
    const issues: any[] = [];
    let prCount = 0;
    let limitReached = false;

    for await (const response of octokit.paginate.iterator(
      octokit.rest.issues.listForRepo,
      options
    )) {
      for (const issue of response.data) {
        if (issue.pull_request) {
          prCount++;
        } else {
          issues.push(issue);
          // Stop if we've hit the issue limit
          if (issues.length >= maxIssues) {
            console.log(`[GitHub] Reached max issues limit (${maxIssues}), stopping pagination`);
            limitReached = true;
            break;
          }
        }
      }
      
      if (limitReached) {
        break;
      }
    }

    console.log(`[GitHub] Fetched ${issues.length} issues (filtered ${prCount} PRs)`);

    return { issues, prCount };
  } catch (error: any) {
    console.error(`[GitHub] Error fetching issues for ${owner}/${repo}:`, error.message);
    throw new Error(`Failed to fetch issues: ${error.message}`);
  }
}

/**
 * Retrieve the current GitHub API core rate limit status.
 *
 * @returns An object with the core rate limit values: `limit` (maximum requests), `remaining` (requests left), `reset` (Date when the limit resets), and `used` (requests consumed)
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
 * Convert a GitHub issue object into a FeedbackItem suitable for internal storage and syncing.
 *
 * @param issue - GitHub issue object returned by the API
 * @param repoFullName - Repository full name in "owner/repo" format used to build the feedback id
 * @returns A FeedbackItem with mapped fields: id, source, external_id, title, body, repo, github_issue_number, github_issue_url, status, metadata (labels, state, comments, created_at, updated_at, author, assignees, milestone), and created_at
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
 * Synchronizes issues from a GitHub repository and returns counts of new, updated, and closed issues.
 *
 * @param repoConfig - Repository configuration with `owner`, `repo`, `full_name`, and optional `last_synced`. When `last_synced` is provided, the sync is incremental and only issues updated since that timestamp are fetched.
 * @returns An object with:
 *  - `new_issues`: number of issues considered new (all open issues on first sync),
 *  - `updated_issues`: number of issues updated since `last_synced` (zero on first sync),
 *  - `closed_issues`: number of issues that are closed in the fetched set,
 *  - `total_issues`: total number of issues fetched (excluding pull requests)
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
  const { issues } = await fetchRepoIssues(owner, repo, last_synced);

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