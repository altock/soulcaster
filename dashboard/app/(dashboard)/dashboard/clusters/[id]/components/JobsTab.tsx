'use client';

import type { AgentJob } from '@/types';

interface JobsTabProps {
  jobs: AgentJob[];
  jobsError: string | null;
  onRefresh: () => void;
  onViewLogs: (job: AgentJob) => void;
}

export default function JobsTab({
  jobs,
  jobsError,
  onRefresh,
  onViewLogs,
}: JobsTabProps) {
  const getStatusLabel = (status: AgentJob['status']) => {
    switch (status) {
      case 'success':
        return 'Success';
      case 'failed':
        return 'Failed';
      case 'running':
        return 'Running';
      default:
        return 'Pending';
    }
  };

  const getStatusClass = (status: AgentJob['status']) => {
    switch (status) {
      case 'success':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      case 'failed':
        return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
      case 'running':
        return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
      default:
        return 'bg-slate-500/10 text-slate-400 border-slate-500/20';
    }
  };

  // Empty state
  if (jobs.length === 0) {
    return (
      <div className="rounded-3xl border border-white/10 bg-white/5 p-12 text-center">
        <div className="mx-auto w-16 h-16 bg-white/5 rounded-full flex items-center justify-center mb-6 border border-white/10">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-8 w-8 text-slate-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"
            />
          </svg>
        </div>
        <h2 className="text-xl font-medium text-white mb-3">No Fix Jobs Yet</h2>
        <p className="text-slate-400 max-w-md mx-auto leading-relaxed">
          Fix jobs will appear here once you generate a plan and start the
          automated fix process.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium text-white">Fix Jobs</h2>
        <button
          onClick={onRefresh}
          className="text-xs text-slate-400 hover:text-emerald-400 transition-colors flex items-center gap-1"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-3.5 w-3.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          Refresh
        </button>
      </div>

      {/* Error message */}
      {jobsError && (
        <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm">
          {jobsError}
        </div>
      )}

      {/* Jobs list */}
      <div className="space-y-3">
        {jobs.map((job) => (
          <div
            key={job.id}
            className="rounded-2xl border border-white/10 bg-black/30 p-5 transition-colors hover:border-white/20"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <span className="text-sm font-mono text-slate-300">
                    {job.id.slice(0, 8)}...
                  </span>
                  <span
                    className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium uppercase tracking-wider border ${getStatusClass(
                      job.status
                    )}`}
                  >
                    {job.status === 'running' && (
                      <span className="h-1.5 w-1.5 rounded-full bg-yellow-400 animate-pulse" />
                    )}
                    {getStatusLabel(job.status)}
                  </span>
                </div>
                <div className="text-xs text-slate-500">
                  Created {new Date(job.created_at).toLocaleString()}
                </div>
                {job.pr_url && (
                  <a
                    href={job.pr_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 mt-2 text-xs text-emerald-400 hover:text-emerald-300 transition-colors"
                  >
                    <svg
                      viewBox="0 0 24 24"
                      fill="currentColor"
                      className="w-3.5 h-3.5"
                    >
                      <path
                        fillRule="evenodd"
                        d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
                        clipRule="evenodd"
                      />
                    </svg>
                    View Pull Request
                  </a>
                )}
              </div>
              <button
                onClick={() => onViewLogs(job)}
                className="shrink-0 px-4 py-2 rounded-full text-xs font-medium border border-white/10 bg-white/5 text-slate-300 hover:bg-white/10 hover:text-white transition-colors"
              >
                View Logs
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
