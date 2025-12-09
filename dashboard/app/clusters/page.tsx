'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import type { ClusterListItem } from '@/types';
import SourceConfig from '@/components/SourceConfig';

/**
 * Display the Issue Clusters page and manage its loading, error, empty, and populated states.
 *
 * On mount the component loads cluster data and the count of unclustered items, automatically
 * triggering a silent clustering run when unclustered items exist. The UI lets users manually
 * run clustering, toggle source configuration, and browse clusters in a table that shows title,
 * summary, repositories, status, feedback count, and a link to cluster details.
 *
 * @returns The React element for the Issue Clusters page
 */
export default function ClustersListPage() {
  const [clusters, setClusters] = useState<ClusterListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unclusteredCount, setUnclusteredCount] = useState(0);
  const [isClustering, setIsClustering] = useState(false);
  const [showConfig, setShowConfig] = useState(false);

  useEffect(() => {
    loadClustersAndAutoCluster();
  }, []);

  const loadClustersAndAutoCluster = async () => {
    // First fetch existing clusters
    await fetchClusters();

    // Check if there are unclustered items
    const count = await fetchUnclusteredCount();

    // Auto-run clustering if there are unclustered items (silent mode)
    if (count > 0) {
      await runClustering(true);
    }
  };

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

  const fetchUnclusteredCount = async (): Promise<number> => {
    try {
      const response = await fetch('/api/clusters/unclustered');
      if (response.ok) {
        const data = await response.json();
        setUnclusteredCount(data.count);
        return data.count;
      }
    } catch (err) {
      console.error('Failed to fetch unclustered count:', err);
    }
    return 0;
  };

  const runClustering = async (silent: boolean = false) => {
    try {
      setIsClustering(true);
      const response = await fetch('/api/clusters/run', {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to run clustering');
      }

      const result = await response.json();

      // Refresh clusters and unclustered count
      await fetchClusters();
      await fetchUnclusteredCount();

      // Show success message only if not silent (manual trigger)
      if (!silent) {
        alert(
          `Clustering complete!\n` +
          `- Processed: ${result.clustered} items\n` +
          `- New clusters: ${result.newClusters}\n` +
          `- Updated clusters: ${result.updatedClusters || 0}`
        );
      }
    } catch (err) {
      if (!silent) {
        alert(
          'Failed to run clustering: ' + (err instanceof Error ? err.message : 'Unknown error')
        );
      } else {
        console.error('Auto-clustering failed:', err);
      }
    } finally {
      setIsClustering(false);
    }
  };

  const triggerClustering = async () => {
    await runClustering(false);
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-center py-12">
          <div className="text-gray-500">Loading clusters...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="rounded-md bg-red-50 p-4">
          <div className="flex">
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Error loading clusters</h3>
              <div className="mt-2 text-sm text-red-700">{error}</div>
              <button
                onClick={fetchClusters}
                className="mt-3 text-sm font-medium text-red-800 hover:text-red-900"
              >
                Try again
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (clusters.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center py-12 bg-purple-50 border border-purple-200 rounded-lg">
          <h3 className="text-lg font-medium text-purple-900 mb-2">🔍 No clusters found</h3>
          <p className="mt-2 text-sm text-purple-700 mb-4">
            We didn&apos;t receive any clusters from the backend. Ensure the ingestion API is
            running and BACKEND_URL points at it.
          </p>
          <p className="text-sm text-purple-700">
            You can still browse individual feedback in the{' '}
            <Link href="/feedback" className="font-semibold underline">
              Feedback tab
            </Link>
            .
          </p>
          <p className="mt-4 text-sm text-purple-700">
            {unclusteredCount > 0
              ? `${unclusteredCount} unclustered feedback item${unclusteredCount === 1 ? '' : 's'} ready to group.`
              : 'No unclustered feedback detected yet.'}
          </p>
          <div className="mt-6 flex flex-col sm:flex-row items-center justify-center gap-3">
            <button
              onClick={triggerClustering}
              disabled={isClustering}
              className={`w-full sm:w-auto px-6 py-3 border border-transparent text-sm font-bold rounded-full shadow-neon-green text-black bg-matrix-green hover:bg-green-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-matrix-green disabled:opacity-50 disabled:cursor-not-allowed transition-all uppercase tracking-wide ${isClustering ? 'animate-pulse' : ''
                }`}
            >
              {isClustering ? 'Running AI Clustering...' : 'Run Clustering'}
            </button>
            <button
              onClick={() => setShowConfig(!showConfig)}
              className={`w-full sm:w-auto px-6 py-3 border border-purple-200 text-sm font-semibold rounded-full text-purple-900 bg-white hover:bg-purple-50 transition-all ${showConfig ? 'ring-2 ring-purple-200' : ''
                }`}
            >
              {showConfig ? 'Hide Source Settings' : 'Configure Sources'}
            </button>
          </div>
          {showConfig && (
            <div className="mt-6 text-left">
              <SourceConfig />
            </div>
          )}
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
          <div className="flex gap-3">
            <button
              onClick={() => setShowConfig(!showConfig)}
              className={`px-4 py-3 border border-white/10 text-sm font-medium rounded-full text-slate-300 hover:bg-white/5 transition-all ${showConfig ? 'bg-white/10 text-white' : ''}`}
            >
              {showConfig ? 'Hide Sources' : 'Configure Sources'}
            </button>
            <button
              onClick={triggerClustering}
              disabled={isClustering}
              className={`px-6 py-3 border border-transparent text-sm font-bold rounded-full shadow-neon-green text-black bg-matrix-green hover:bg-green-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-matrix-green disabled:opacity-50 disabled:cursor-not-allowed transition-all uppercase tracking-wide ${isClustering ? 'animate-pulse' : ''
                }`}
            >
              {isClustering ? 'Running AI Clustering...' : 'Run Clustering'}
            </button>
          </div>
        </div>

        {showConfig && (
          <div className="mb-8 animate-in slide-in-from-top-4 fade-in duration-300">
            <SourceConfig />
          </div>
        )}

        {error && (
          <div className="rounded-lg bg-red-900/20 p-4 mb-6 border border-red-900/50">
            <div className="flex">
              <div className="ml-3">
                <h3 className="text-sm font-medium text-red-400">Error</h3>
                <div className="mt-2 text-sm text-red-300">{error}</div>
              </div>
            </div>
          </div>
        )}

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
              <div className="flex gap-2">
                <button className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs font-medium text-slate-300 transition-colors hover:bg-white/10">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path>
                    <path d="M3 3v5h5"></path>
                    <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"></path>
                    <path d="M16 16h5v5"></path>
                  </svg>
                  Refresh
                </button>
                <button className="inline-flex items-center gap-2 rounded-full bg-emerald-500 px-4 py-2 text-xs font-medium text-black transition-colors hover:bg-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.3)]">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M5 12h14"></path>
                    <path d="M12 5v14"></path>
                  </svg>
                  Add Cluster
                </button>
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
                  {clusters.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                        No clusters found. Run clustering to group feedback items.
                      </td>
                    </tr>
                  ) : (
                    clusters.map((cluster) => (
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
                            href={`/clusters/${cluster.id}`}
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
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}