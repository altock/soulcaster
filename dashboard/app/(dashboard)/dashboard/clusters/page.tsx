'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import type { ClusterListItem } from '@/types';

type ClusterJobStatus = {
  id: string;
  status: 'pending' | 'running' | 'succeeded' | 'failed';
  created_at?: string;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  stats?: Record<string, number>;
};

export default function ClustersListPage() {
  const [clusters, setClusters] = useState<ClusterListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [latestJob, setLatestJob] = useState<ClusterJobStatus | null>(null);

  const extractJobsFromPayload = (payload: unknown): ClusterJobStatus[] => {
    if (!payload) {
      return [];
    }
    if (Array.isArray(payload)) {
      return payload as ClusterJobStatus[];
    }
    if (typeof payload === 'object' && Array.isArray((payload as { jobs?: ClusterJobStatus[] }).jobs)) {
      return ((payload as { jobs?: ClusterJobStatus[] }).jobs ?? []).filter(Boolean) as ClusterJobStatus[];
    }
    return [];
  };

  const jobIsRunning = latestJob?.status === 'running';

  useEffect(() => {
    const loadData = async () => {
      await fetchClusters();
      // Parallelize with Promise.all since these fetches are independent
      await Promise.all([fetchLatestJob()]);
    };
    loadData();
  }, []);

  const fetchClusters = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch('/api/clusters');
      if (!response.ok) {
        throw new Error('Failed to fetch clusters');
      }
      const data = await response.json();
      setClusters(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const fetchLatestJob = async () => {
    try {
      const response = await fetch('/api/clusters/jobs?limit=1', {
        cache: 'no-store',
      });
      if (response.ok) {
        const data = await response.json();
        const jobs = extractJobsFromPayload(data);
        const newest = jobs.length > 0 ? jobs[0] : null;
        setLatestJob(newest);
        return newest;
      }
      console.error('Failed to fetch cluster jobs status');
    } catch (err) {
      console.error('Failed to fetch cluster jobs status:', err);
    }
    setLatestJob(null);
    return null;
  };

  const formatTimestamp = (value?: string | null) => {
    if (!value) return 'unknown time';
    try {
      return new Date(value).toLocaleString();
    } catch {
      return value;
    }
  };

  const jobStatusPill = () => {
    if (!latestJob) {
      return 'No clustering runs yet';
    }
    if (latestJob.status === 'running') {
      return `Job running since ${formatTimestamp(latestJob.started_at || latestJob.created_at)}`;
    }
    const finishedAt = latestJob.finished_at || latestJob.started_at || latestJob.created_at;
    return `Last job ${latestJob.status} @ ${formatTimestamp(finishedAt)}`;
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500"></div>
        </div>
      </div>
    );
  }

  if (error) {
    const getErrorDetails = (errorMsg: string) => {
      if (errorMsg.includes('fetch') || errorMsg.includes('network')) {
        return {
          title: 'Connection Error',
          description: 'Could not connect to the API server.',
          hint: 'Check that the backend is running on localhost:8000',
        };
      }
      if (errorMsg.includes('401') || errorMsg.includes('unauthorized')) {
        return {
          title: 'Authentication Error',
          description: 'Your session may have expired.',
          hint: 'Try signing out and back in',
        };
      }
      return {
        title: 'Error Loading Clusters',
        description: errorMsg,
        hint: 'If this persists, check the browser console for details',
      };
    };

    const errorDetails = getErrorDetails(error);

    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div
          className="rounded-xl bg-red-500/10 border border-red-500/30 p-6"
          role="alert"
          aria-live="polite"
        >
          <div className="flex items-start gap-3">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-6 w-6 text-red-400 flex-shrink-0 mt-0.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <div className="flex-1">
              <h3 className="text-sm font-medium text-red-400">
                {errorDetails.title}
              </h3>
              <p className="mt-1 text-sm text-red-300">
                {errorDetails.description}
              </p>
              <p className="mt-2 text-xs text-red-300/70">
                {errorDetails.hint}
              </p>
            </div>
          </div>
          <div className="mt-4 flex gap-3">
            <button
              onClick={fetchClusters}
              className="inline-flex items-center gap-2 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-300 rounded-lg border border-red-500/30 transition-colors text-sm font-medium"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-4 w-4"
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
              Try Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (clusters.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-emerald-950/20 rounded-3xl border border-white/10 backdrop-blur-sm p-16 text-center relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 via-transparent to-transparent pointer-events-none" />
          <div className="relative z-10">
            {jobIsRunning ? (
              <>
                <div className="mx-auto w-16 h-16 bg-emerald-500/10 rounded-full flex items-center justify-center mb-6 border border-emerald-500/30">
                  <svg
                    className="animate-spin h-8 w-8 text-emerald-400"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    ></circle>
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    ></path>
                  </svg>
                </div>
                <h2 className="text-xl font-medium text-white mb-3">Clustering in Progress</h2>
                <p className="text-slate-400 max-w-sm mx-auto leading-relaxed">
                  Your feedback is being analyzed and grouped into clusters. This may take a moment.
                </p>
              </>
            ) : (
              <>
                <div className="mx-auto w-16 h-16 bg-white/5 rounded-full flex items-center justify-center mb-6 border border-white/10">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className="h-8 w-8 text-emerald-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.5}
                      d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                    />
                  </svg>
                </div>
                <h2 className="text-xl font-medium text-white mb-3">No Clusters Yet</h2>
                <p className="text-slate-400 max-w-sm mx-auto leading-relaxed">
                  Clusters will appear here once you sync feedback sources.{' '}
                  <Link href="/dashboard/feedback" className="text-emerald-400 hover:text-emerald-300 underline">
                    Add sources in Feedback
                  </Link>{' '}
                  to get started.
                </p>
              </>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-matrix-black pb-12 pt-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-white tracking-tight">Issue Clusters</h1>
            <p className="mt-2 text-gray-400">
              Grouped feedback items ready for analysis and action.
            </p>
          </div>
        </div>
        <div className="animate-in delay-200 overflow-hidden sm:p-8 hover-card-effect group bg-gradient-to-br from-emerald-500/5 to-emerald-600/10 rounded-3xl pt-6 pr-6 pb-6 pl-6 relative shadow-[0_0_60px_rgba(16,185,129,0.1)] border border-white/10">
          <div className="pointer-events-none absolute inset-0 opacity-30">
            <div className="absolute right-0 top-0 h-96 w-96 -translate-y-10 translate-x-10 rounded-full bg-emerald-500/10 blur-3xl"></div>
          </div>

          <div className="relative flex flex-col gap-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-normal uppercase tracking-[0.12em] text-emerald-300/70">
                  Infrastructure Map
                </p>
                <h2 className="mt-1 text-2xl font-medium tracking-tight text-slate-50">
                  Active Clusters
                </h2>
              </div>
              <div className="flex flex-col gap-2 text-right sm:text-left">
                <span className="inline-flex items-center gap-2 rounded-full border border-emerald-900/60 bg-emerald-900/20 px-4 py-2 text-xs font-medium text-emerald-200">
                  Clustering runs automatically after feedback ingestion
                </span>
                <span className="text-xs font-medium uppercase tracking-wide text-emerald-200/80">
                  {jobStatusPill()}
                </span>
                {latestJob?.error && (
                  <span className="text-xs text-red-300">
                    Last error: {latestJob.error}
                  </span>
                )}
              </div>
            </div>

            <div className="overflow-hidden rounded-2xl border border-white/5 bg-black/40 backdrop-blur-sm">
              <table className="w-full text-left text-sm text-slate-400">
                <thead className="bg-white/5 text-xs uppercase text-slate-200">
                  <tr>
                    <th className="px-6 py-4 font-medium tracking-wider">Cluster Name</th>
                    <th className="px-6 py-4 font-medium tracking-wider">Repositories</th>
                    <th className="px-6 py-4 font-medium tracking-wider">Status</th>
                    <th className="px-6 py-4 font-medium tracking-wider">Feedback</th>
                    <th className="px-6 py-4 font-medium tracking-wider text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {clusters.map((cluster) => (
                      <tr key={cluster.id} className="group transition-colors hover:bg-white/5">
                        <td className="px-6 py-4">
                          <div className="flex flex-col gap-1">
                            <span className="font-medium text-slate-200 group-hover:text-emerald-300 transition-colors">
                              {cluster.issue_title || cluster.title || 'Untitled Cluster'}
                            </span>
                            <span className="text-xs text-slate-500 line-clamp-2">
                              {cluster.issue_description || cluster.summary}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          {cluster.repos && cluster.repos.length > 0 ? (
                            <div className="flex flex-wrap gap-1">
                              {cluster.repos.slice(0, 2).map((repo) => (
                                <span
                                  key={repo}
                                  className="inline-flex items-center gap-1 rounded-md border border-purple-900/50 bg-purple-900/20 px-2 py-0.5 text-[10px] font-medium text-purple-300"
                                >
                                  <svg viewBox="0 0 16 16" fill="currentColor" className="w-3 h-3">
                                    <path d="M2 2.5A2.5 2.5 0 014.5 0h8.75a.75.75 0 01.75.75v12.5a.75.75 0 01-.75.75h-2.5a.75.75 0 110-1.5h1.75v-2h-8a1 1 0 00-.714 1.7.75.75 0 01-1.072 1.05A2.495 2.495 0 012 11.5v-9zm10.5-1V9h-8c-.356 0-.694.074-1 .208V2.5a1 1 0 011-1h8zM5 12.25v3.25a.25.25 0 00.4.2l1.45-1.087a.25.25 0 01.3 0L8.6 15.7a.25.25 0 00.4-.2v-3.25a.25.25 0 00-.25-.25h-3.5a.25.25 0 00-.25.25z" />
                                  </svg>
                                  {repo}
                                </span>
                              ))}
                              {cluster.repos.length > 2 && (
                                <span className="inline-flex items-center rounded-md border border-purple-900/50 bg-purple-900/20 px-2 py-0.5 text-[10px] font-medium text-purple-300">
                                  +{cluster.repos.length - 2} more
                                </span>
                              )}
                            </div>
                          ) : (
                            <span className="text-xs text-slate-500">—</span>
                          )}
                        </td>
                        <td className="px-6 py-4">
                          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium border ${cluster.status === 'new' || cluster.status === 'pr_opened' || cluster.status === 'fixing'
                            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                            : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                            }`}>
                            <span className={`h-1.5 w-1.5 rounded-full ${cluster.status === 'new' || cluster.status === 'pr_opened' || cluster.status === 'fixing'
                              ? 'bg-emerald-400 animate-pulse'
                              : 'bg-rose-400'
                              }`}></span>
                            {cluster.status.replace('_', ' ')}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <span className="text-slate-200">{cluster.count}</span>
                            <span className="text-xs text-slate-500">items</span>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-right">
                          <Link
                            href={`/dashboard/clusters/${cluster.id}`}
                            className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-300 transition-all hover:bg-emerald-500 hover:text-black hover:border-emerald-500"
                          >
                            View Details
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M5 12h14"></path>
                              <path d="m12 5 7 7-7 7"></path>
                            </svg>
                          </Link>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
