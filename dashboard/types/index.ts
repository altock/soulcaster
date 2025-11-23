// Shared TypeScript types for FeedbackAgent dashboard

export type FeedbackSource = 'reddit' | 'sentry' | 'manual';

export type ClusterStatus = 'new' | 'fixing' | 'pr_opened' | 'failed';

export interface FeedbackItem {
  id: string;
  source: FeedbackSource;
  external_id?: string | null;
  title: string;
  body: string;
  github_repo_url?: string;
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
    sentry: number;
    manual: number;
  };
  total_clusters: number;
  active_clusters: number;
}

export interface IssueCluster {
  id: string;
  title: string;
  summary: string;
  feedback_ids: string[];
  status: ClusterStatus;
  created_at: string;
  updated_at: string;
  embedding_centroid?: number[];
  github_branch?: string;
  github_pr_url?: string;
  error_message?: string;
}

export interface ClusterListItem {
  id: string;
  title: string;
  summary: string;
  count: number;
  status: ClusterStatus;
  sources: FeedbackSource[];
  github_pr_url?: string;
}

export interface ClusterDetail extends IssueCluster {
  feedback_items: FeedbackItem[];
}
