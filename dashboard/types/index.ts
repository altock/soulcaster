// Shared TypeScript types for FeedbackAgent dashboard

export type FeedbackSource = 'reddit' | 'manual' | 'github';

export type ClusterStatus = 'new' | 'fixing' | 'pr_opened' | 'failed';

export type IssueStatus = 'open' | 'closed';

export interface FeedbackItem {
  id: string;
  source: FeedbackSource;
  external_id?: string | null;
  title: string;
  body: string;
  repo?: string; // Format: "owner/repo" (e.g., "anthropics/claude-code")
  github_repo_url?: string;
  github_issue_number?: number;
  github_issue_url?: string;
  status?: IssueStatus; // For GitHub issues
  metadata: Record<string, any>;
  created_at: string;
  embedding?: number[];
}

export interface FeedbackListResponse {
  items: FeedbackItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface StatsResponse {
  total_feedback: number;
  by_source: {
    reddit: number;
    manual: number;
    github: number;
  };
  total_clusters: number;
  active_clusters: number;
}

export interface IssueCluster {
  id: string;
  title: string;
  summary: string;
  feedback_ids: string[];
  repo?: string; // Repo association for repo-scoped clusters
  status: ClusterStatus;
  created_at: string;
  updated_at: string;
  embedding_centroid?: number[];
  github_branch?: string;
  github_pr_url?: string;
  error_message?: string;
  issue_title?: string;
  issue_description?: string;
  github_repo_url?: string;
}

export interface CodingPlan {
  id: string;
  cluster_id: string;
  title: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface ClusterListItem {
  id: string;
  title: string;
  summary: string;
  count: number;
  status: ClusterStatus;
  sources: FeedbackSource[];
  repos?: string[]; // Array of "owner/repo" strings for GitHub repos
  github_pr_url?: string;
  issue_title?: string;
  issue_description?: string;
  github_repo_url?: string;
}

export interface ClusterDetail extends IssueCluster {
  feedback_items: FeedbackItem[];
}

export interface GitHubRepo {
  owner: string;
  repo: string;
  full_name: string; // "owner/repo"
  last_synced?: string;
  issue_count?: number;
  enabled: boolean;
}

export type AgentJobStatus = 'pending' | 'running' | 'success' | 'failed';

export interface AgentJob {
  id: string;
  project_id: string;
  cluster_id: string;
  plan_id?: string | null;
  runner?: string | null;
  status: AgentJobStatus;
  pr_url?: string | null;
  created_at: string;
  updated_at: string;
}
