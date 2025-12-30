'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import type { ClusterListItem } from '@/types';
import { Skeleton } from '@/components/ui/Skeleton';
import { useProject } from '@/contexts/ProjectContext';

type ClusterJobStatus = {
  id: string;
  status: 'pending' | 'running' | 'succeeded' | 'failed';
  created_at?: string;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  stats?: Record<string, number>;
};

/**
 * Render the Issue Clusters page, showing clustered feedback, job status, and controls to run clustering.
 *
 * Displays loading, empty, and error states; lists clusters with source links, status pills, and item counts;
 * provides a button to trigger a clustering job and shows the latest job status.
 *
 * @returns A React element rendering the Issue Clusters page UI.
 */
export default function ClustersListPage() {
  const router = useRouter();
  const { currentProjectId } = useProject();
  const [clusters, setClusters] = useState<ClusterListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [latestJob, setLatestJob] = useState<ClusterJobStatus | null>(null);
  const [isTriggering, setIsTriggering] = useState(false);

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

  const isValidHttpUrl = (url: string): boolean => {
    try {
      const parsed = new URL(url);
      return parsed.protocol === 'https:' || parsed.protocol === 'http:';
    } catch {
      return false;
    }
  };

  useEffect(() => {
    if (!currentProjectId) return;

    // Clear stale state immediately when project changes
    setClusters([]);
    setLatestJob(null);
    setLoading(true);
    setError(null);

    // Create AbortController to cancel requests on cleanup
    const abortController = new AbortController();

    const loadData = async () => {
      try {
        await Promise.all([
          fetchClusters(abortController.signal),
          fetchLatestJob(abortController.signal),
        ]);
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          // Request was cancelled - this is expected during project switch
          console.log('[ClustersPage] Request cancelled');
          return;
        }
        console.error('[ClustersPage] Error loading data:', err);
      }
    };

    loadData();

    // Cleanup: abort all pending requests when project changes or component unmounts
    return () => {
      abortController.abort();
    };
  }, [currentProjectId]);

  const fetchClusters = async (signal?: AbortSignal) => {
    if (!currentProjectId) return;
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`/api/clusters?project_id=${currentProjectId}`, {
        cache: 'no-store', // Prevent browser caching
        signal, // Allow request cancellation
      });
      if (!response.ok) {
        throw new Error('Failed to fetch clusters');
      }
      const data = await response.json();
      setClusters(data);
    } catch (err) {
      // Don't set error state if request was aborted
      if (err instanceof Error && err.name === 'AbortError') {
        throw err;
      }
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const fetchLatestJob = async (signal?: AbortSignal) => {
    if (!currentProjectId) return;
    try {
      const response = await fetch(`/api/clusters/jobs?project_id=${currentProjectId}&limit=1`, {
        cache: 'no-store',
        signal, // Allow request cancellation
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
      // Don't log error if request was aborted
      if (err instanceof Error && err.name === 'AbortError') {
        throw err;
      }
      console.error('Failed to fetch cluster jobs status:', err);
    }
    setLatestJob(null);
    return null;
  };

  const triggerClustering = async () => {
    if (!currentProjectId) return;
    try {
      setIsTriggering(true);
      const response = await fetch(`/api/clusters/jobs?project_id=${currentProjectId}`, {
        method: 'POST',
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || 'Failed to start clustering');
      }
      const data = await response.json();
      setLatestJob({
        id: data.job_id,
        status: data.status || 'pending',
        created_at: new Date().toISOString(),
      });
    } catch (err) {
      console.error('Failed to trigger clustering:', err);
      setError(err instanceof Error ? err.message : 'Failed to start clustering');
    } finally {
      setIsTriggering(false);
    }
  };

  const formatTimestamp = (value?: string | null) => {
    if (!value) return 'unknown time';
    try {
      const date = new Date(value);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);
      const diffDays = Math.floor(diffMs / 86400000);

      if (diffMins < 1) return 'just now';
      if (diffMins < 60) return `${diffMins} min ago`;
      if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
      if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
      return date.toLocaleDateString();
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
      <div className="min-h-screen bg-matrix-black pb-12 pt-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4 mb-6">
            <div>
              <Skeleton className="h-8 w-48 mb-2" />
              <Skeleton className="h-4 w-72 hidden sm:block" />
            </div>
            <Skeleton className="h-8 w-32 rounded-full" />
          </div>
          <div className="overflow-hidden rounded-2xl border border-white/10 bg-black/40">
            <table className="w-full table-fixed text-left text-sm">
              <thead className="bg-white/5">
                <tr>
                  <th className="w-[55%] sm:w-[45%] px-3 sm:px-4 py-3"><Skeleton className="h-3 w-12" /></th>
                  <th className="hidden sm:table-cell sm:w-[25%] px-4 py-3"><Skeleton className="h-3 w-12" /></th>
                  <th className="w-[25%] sm:w-[15%] px-2 sm:px-4 py-3"><Skeleton className="h-3 w-12" /></th>
                  <th className="w-[20%] sm:w-[15%] px-2 sm:px-4 py-3"><Skeleton className="h-3 w-8" /></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {[1, 2, 3, 4, 5].map((i) => (
                  <tr key={i}>
                    <td className="px-3 sm:px-4 py-4">
                      <Skeleton className="h-5 w-full max-w-[200px] mb-1" />
                      <Skeleton className="h-3 w-full max-w-[160px] hidden sm:block" />
                    </td>
                    <td className="hidden sm:table-cell px-4 py-4">
                      <Skeleton className="h-4 w-24" />
                    </td>
                    <td className="px-2 sm:px-4 py-4">
                      <Skeleton className="h-5 w-16 rounded-full" />
                    </td>
                    <td className="px-2 sm:px-4 py-4 text-center">
                      <Skeleton className="h-4 w-6 mx-auto" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    const getErrorDetails = (errorMsg: string) => {
      if (errorMsg.includes('timeout') || errorMsg.includes('timed out') || errorMsg.includes('503')) {
        return {
          title: 'Request Timeout',
          description: 'The server took too long to respond.',
          hint: 'Try refreshing the page. If this persists, the server may be overloaded.',
        };
      }
      if (errorMsg.includes('fetch') || errorMsg.includes('network')) {
        return {
          title: 'Service Unavailable',
          description: 'Soulcaster services are currently unavailable.',
          hint: 'Please check your internet connection and try again in a moment.',
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
              onClick={() => fetchClusters()}
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
                <p className="text-slate-400 max-w-sm mx-auto leading-relaxed mb-6">
                  Clusters will appear here once you sync feedback sources.{' '}
                  <Link href="/dashboard/feedback" className="text-emerald-400 hover:text-emerald-300 underline">
                    Add sources in Feedback
                  </Link>{' '}
                  to get started.
                </p>
                <div className="flex flex-col items-center gap-2">
                  <button
                    onClick={triggerClustering}
                    disabled={isTriggering || jobIsRunning}
                    className="inline-flex items-center gap-2 rounded-full border border-emerald-500/40 bg-emerald-500/10 hover:bg-emerald-500/20 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 text-sm font-medium text-emerald-300 transition-colors"
                  >
                    {isTriggering || jobIsRunning ? (
                      <>
                        <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Running...
                      </>
                    ) : (
                      <>
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        Run Clustering Now
                      </>
                    )}
                  </button>
                  {latestJob && (
                    <span className="text-xs text-slate-400">{jobStatusPill()}</span>
                  )}
                  {latestJob?.error && (
                    <span className="text-xs text-red-300">
                      Error: {latestJob.error}
                    </span>
                  )}
                </div>
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
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4 mb-6">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">Issue Clusters</h1>
            <p className="mt-1 text-sm text-gray-400 hidden sm:block">
              Grouped feedback items ready for analysis and action.
            </p>
          </div>
          <div className="flex items-center sm:items-end gap-3 sm:gap-2 sm:flex-col">
            <button
              onClick={triggerClustering}
              disabled={isTriggering || jobIsRunning}
              className="inline-flex items-center gap-2 rounded-full border border-emerald-500/40 bg-emerald-500/10 hover:bg-emerald-500/20 disabled:opacity-50 disabled:cursor-not-allowed px-3 py-1.5 text-xs font-medium text-emerald-300 transition-colors"
            >
              {isTriggering || jobIsRunning ? (
                <>
                  <svg className="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Running...
                </>
              ) : (
                <>
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Run Clustering
                </>
              )}
            </button>
            <span className="text-xs text-slate-400">{jobStatusPill()}</span>
            {latestJob?.error && (
              <span className="text-xs text-red-300 hidden sm:inline">
                Error: {latestJob.error}
              </span>
            )}
          </div>
        </div>
        <div className="animate-in delay-200 overflow-hidden hover-card-effect group bg-gradient-to-br from-emerald-500/5 to-emerald-600/10 rounded-2xl relative shadow-[0_0_60px_rgba(16,185,129,0.1)] border border-white/10">
          <div className="pointer-events-none absolute inset-0 opacity-30">
            <div className="absolute right-0 top-0 h-96 w-96 -translate-y-10 translate-x-10 rounded-full bg-emerald-500/10 blur-3xl"></div>
          </div>

          <div className="relative">
            <div className="overflow-hidden bg-black/40 backdrop-blur-sm">
              <table className="w-full table-fixed text-left text-sm text-slate-400">
                <thead className="bg-white/5 text-xs uppercase text-slate-200">
                  <tr>
                    <th className="w-[55%] sm:w-[45%] px-3 sm:px-4 py-3 font-medium tracking-wider">Name</th>
                    <th className="hidden sm:table-cell sm:w-[25%] px-4 py-3 font-medium tracking-wider">Source</th>
                    <th className="w-[25%] sm:w-[15%] px-2 sm:px-4 py-3 font-medium tracking-wider">Status</th>
                    <th className="w-[20%] sm:w-[15%] px-2 sm:px-4 py-3 font-medium tracking-wider">Items</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {clusters.map((cluster) => (
                      <tr
                        key={cluster.id}
                        onClick={() => router.push(`/dashboard/clusters/${cluster.id}`)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            router.push(`/dashboard/clusters/${cluster.id}`);
                          }
                        }}
                        tabIndex={0}
                        role="link"
                        aria-label={`View cluster: ${cluster.issue_title || cluster.title || 'Untitled Cluster'}`}
                        className="group cursor-pointer transition-colors hover:bg-white/5 focus:bg-white/5 focus:outline-none"
                      >
                        <td className="px-3 sm:px-4 py-3">
                          <div className="flex flex-col gap-0.5 min-w-0">
                            <span className="font-medium text-slate-200 group-hover:text-emerald-300 transition-colors truncate text-sm">
                              {cluster.issue_title || cluster.title || 'Untitled Cluster'}
                            </span>
                            <span className="text-xs text-slate-500 truncate hidden sm:block">
                              {cluster.issue_description || cluster.summary}
                            </span>
                          </div>
                        </td>
                        <td className="hidden sm:table-cell px-4 py-3">
                          <div className="flex flex-col gap-1 min-w-0">
                            {cluster.github_repo_url && isValidHttpUrl(cluster.github_repo_url) && (
                              <a
                                href={cluster.github_repo_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="inline-flex items-center gap-1 text-xs text-purple-300 hover:text-purple-200 truncate"
                              >
                                <svg viewBox="0 0 16 16" fill="currentColor" className="w-3 h-3 flex-shrink-0">
                                  <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
                                </svg>
                                <span className="truncate">{cluster.github_repo_url.replace('https://github.com/', '')}</span>
                              </a>
                            )}
                            {cluster.sources && cluster.sources.length > 0 && (
                              <div className="flex flex-wrap gap-1">
                                {cluster.sources.map((source: string) => (
                                  <span
                                    key={source}
                                    className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium ${
                                      source === 'github'
                                        ? 'bg-purple-900/30 text-purple-300'
                                        : source === 'reddit'
                                        ? 'bg-orange-900/30 text-orange-300'
                                        : 'bg-slate-700/50 text-slate-300'
                                    }`}
                                  >
                                    {source}
                                  </span>
                                ))}
                              </div>
                            )}
                            {!cluster.github_repo_url && (!cluster.sources || cluster.sources.length === 0) && (
                              <span className="text-xs text-slate-500">—</span>
                            )}
                          </div>
                        </td>
                        <td className="px-2 sm:px-4 py-3">
                          <span className={`inline-flex items-center gap-1 rounded-full px-1.5 sm:px-2 py-0.5 text-[10px] sm:text-xs font-medium border whitespace-nowrap ${cluster.status === 'new' || cluster.status === 'pr_opened' || cluster.status === 'fixing'
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
                        <td className="px-2 sm:px-4 py-3 text-center">
                          <span className="text-slate-200 text-sm">{cluster.count}</span>
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