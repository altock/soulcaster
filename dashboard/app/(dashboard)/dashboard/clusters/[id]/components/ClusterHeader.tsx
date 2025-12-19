'use client';

import type { ClusterDetail, FeedbackSource } from '@/types';

interface ClusterHeaderProps {
  cluster: ClusterDetail;
  selectedRepo: string | null;
  onRepoSelect: (repo: string | null) => void;
}

export default function ClusterHeader({
  cluster,
  selectedRepo,
  onRepoSelect,
}: ClusterHeaderProps) {
  const getStatusBadgeClass = (status: ClusterDetail['status']) => {
    const baseClass =
      'px-3 py-1 text-xs font-bold rounded-md uppercase tracking-wider border';
    switch (status) {
      case 'new':
        return `${baseClass} bg-blue-900/20 text-blue-400 border-blue-900/50`;
      case 'fixing':
        return `${baseClass} bg-yellow-900/20 text-yellow-400 border-yellow-900/50`;
      case 'pr_opened':
        return `${baseClass} bg-emerald-900/20 text-emerald-400 border-emerald-900/50`;
      case 'failed':
        return `${baseClass} bg-red-900/20 text-red-400 border-red-900/50`;
      default:
        return `${baseClass} bg-gray-900/50 text-gray-400 border-gray-800`;
    }
  };

  // Calculate source counts
  const sourceCounts = cluster.feedback_items.reduce(
    (acc, item) => {
      acc[item.source] = (acc[item.source] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  // Calculate repo counts
  const repoCounts = cluster.feedback_items.reduce(
    (acc, item) => {
      if (item.repo) {
        acc[item.repo] = (acc[item.repo] || 0) + 1;
      }
      return acc;
    },
    {} as Record<string, number>
  );

  const filteredCount = selectedRepo
    ? cluster.feedback_items.filter((item) => item.repo === selectedRepo).length
    : cluster.feedback_items.length;

  return (
    <div className="bg-[#0A0A0A] shadow-lg rounded-2xl overflow-hidden border border-white/10 mb-6">
      <div className="px-6 py-6">
        {/* Title and Status */}
        <div className="flex flex-wrap items-start gap-3 mb-4">
          <h1 className="text-2xl font-bold text-white tracking-tight flex-1 min-w-0">
            {cluster.issue_title || cluster.title || 'Untitled Cluster'}
          </h1>
          <span className={getStatusBadgeClass(cluster.status)}>
            {cluster.status.replace('_', ' ')}
          </span>
        </div>

        {/* Description */}
        <p className="text-slate-400 leading-relaxed mb-6">
          {cluster.issue_description || cluster.summary}
        </p>

        {/* Metadata Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm border-t border-white/10 pt-5">
          <div>
            <dt className="text-xs font-medium text-emerald-400 uppercase tracking-wider mb-1">
              Created
            </dt>
            <dd className="text-slate-300 font-mono text-xs">
              {new Date(cluster.created_at).toLocaleDateString()}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-emerald-400 uppercase tracking-wider mb-1">
              Updated
            </dt>
            <dd className="text-slate-300 font-mono text-xs">
              {new Date(cluster.updated_at).toLocaleDateString()}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-emerald-400 uppercase tracking-wider mb-1">
              Sources
            </dt>
            <dd className="text-slate-300 text-xs">
              {Object.entries(sourceCounts).map(([source, count]) => (
                <span key={source} className="mr-2">
                  {count} {source}
                </span>
              ))}
            </dd>
          </div>
          {cluster.github_repo_url && (
            <div>
              <dt className="text-xs font-medium text-emerald-400 uppercase tracking-wider mb-1">
                Target Repo
              </dt>
              <dd>
                <a
                  href={cluster.github_repo_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-emerald-400 hover:text-emerald-300 text-xs break-all"
                >
                  {cluster.github_repo_url.replace('https://github.com/', '')}
                </a>
              </dd>
            </div>
          )}
        </div>

        {/* Repository Filter */}
        {Object.keys(repoCounts).length > 0 && (
          <div className="mt-5 pt-5 border-t border-white/10">
            <dt className="text-xs font-medium text-purple-400 uppercase tracking-wider mb-3">
              Filter by Repository
            </dt>
            <div className="flex flex-wrap gap-2">
              {Object.entries(repoCounts).map(([repo, count]) => (
                <button
                  key={repo}
                  onClick={() =>
                    onRepoSelect(selectedRepo === repo ? null : repo)
                  }
                  className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium transition-all ${
                    selectedRepo === repo
                      ? 'border-purple-500/50 bg-purple-500/20 text-purple-200'
                      : 'border-purple-900/50 bg-purple-900/20 text-purple-300 hover:bg-purple-900/30'
                  }`}
                >
                  <svg
                    viewBox="0 0 16 16"
                    fill="currentColor"
                    className="w-3.5 h-3.5"
                  >
                    <path d="M2 2.5A2.5 2.5 0 014.5 0h8.75a.75.75 0 01.75.75v12.5a.75.75 0 01-.75.75h-2.5a.75.75 0 110-1.5h1.75v-2h-8a1 1 0 00-.714 1.7.75.75 0 01-1.072 1.05A2.495 2.495 0 012 11.5v-9zm10.5-1V9h-8c-.356 0-.694.074-1 .208V2.5a1 1 0 011-1h8zM5 12.25v3.25a.25.25 0 00.4.2l1.45-1.087a.25.25 0 01.3 0L8.6 15.7a.25.25 0 00.4-.2v-3.25a.25.25 0 00-.25-.25h-3.5a.25.25 0 00-.25.25z" />
                  </svg>
                  <span>{repo}</span>
                  <span className="rounded-full bg-purple-500/30 px-1.5 py-0.5 text-[10px]">
                    {count}
                  </span>
                </button>
              ))}
            </div>
            {selectedRepo && (
              <div className="mt-3 text-xs text-purple-300">
                Showing {filteredCount}{' '}
                {filteredCount === 1 ? 'item' : 'items'} from{' '}
                <span className="font-semibold">{selectedRepo}</span>
                <button
                  onClick={() => onRepoSelect(null)}
                  className="ml-2 text-purple-400 hover:text-purple-200 underline"
                >
                  Clear filter
                </button>
              </div>
            )}
          </div>
        )}

        {/* Error message */}
        {cluster.error_message && (
          <div className="mt-5 p-3 bg-red-900/20 rounded-lg border border-red-900/50">
            <dt className="text-xs font-bold text-red-400 uppercase tracking-wider mb-1">
              Error
            </dt>
            <dd className="text-red-300 font-mono text-xs">
              {cluster.error_message}
            </dd>
          </div>
        )}
      </div>
    </div>
  );
}
