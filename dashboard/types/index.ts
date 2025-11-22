// Shared TypeScript types for FeedbackAgent dashboard

export type FeedbackSource = 'reddit' | 'sentry';

export type ClusterStatus = 'new' | 'fixing' | 'pr_opened' | 'failed';

export interface FeedbackItem {
  id: string;
  source: FeedbackSource;
  external_id: string;
  title: string;
  body: string;
  metadata: Record<string, any>;
  created_at: string;
  embedding?: number[];
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
