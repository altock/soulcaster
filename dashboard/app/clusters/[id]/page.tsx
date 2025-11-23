'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import type { ClusterDetail, FeedbackSource } from '@/types';
import FeedbackCard from '@/components/FeedbackCard';

/**
 * Client React component that renders details for a single cluster, its feedback items, and actions related to generating fixes.
 *
 * Displays loading and error states, the cluster summary (timestamps, source counts, GitHub links/branch, and any error message), a list of feedback items, and an action to start fix generation. While a cluster is in the "fixing" status the component polls the API for updates.
 *
 * @returns The rendered JSX element for the cluster detail page
 */
export default function ClusterDetailPage() {
  const params = useParams();
  const clusterId = params.id as string;

  const [cluster, setCluster] = useState<ClusterDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isFixing, setIsFixing] = useState(false);

  useEffect(() => {
    fetchCluster();
  }, [clusterId]);

  useEffect(() => {
    if (cluster?.status === 'fixing' && !isFixing) {
      // Poll for updates while fixing
      const interval = setInterval(fetchCluster, 3000);
      return () => clearInterval(interval);
    }
  }, [cluster?.status, isFixing]);

  const fetchCluster = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`/api/clusters/${clusterId}`);
      if (!response.ok) {
        throw new Error('Failed to fetch cluster');
      }
      const data = await response.json();
      setCluster(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handleStartFix = async () => {
    try {
      setIsFixing(true);
      const response = await fetch(`/api/clusters/${clusterId}/start_fix`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error('Failed to start fix');
      }
      await fetchCluster();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to start fix');
    } finally {
      setIsFixing(false);
    }
  };

  const getStatusBadgeClass = (status: ClusterDetail['status']) => {
    const baseClass = 'px-3 py-1 text-xs font-bold rounded-md uppercase tracking-wider border';
    switch (status) {
      case 'new':
        return `${baseClass} bg-blue-900/20 text-blue-400 border-blue-900/50`;
      case 'fixing':
        return `${baseClass} bg-yellow-900/20 text-yellow-400 border-yellow-900/50`;
      case 'pr_opened':
        return `${baseClass} bg-matrix-green-dim text-matrix-green border-matrix-green/30`;
      case 'failed':
        return `${baseClass} bg-red-900/20 text-red-400 border-red-900/50`;
      default:
        return `${baseClass} bg-gray-900/50 text-gray-400 border-gray-800`;
    }
  };

  const getSourceIcon = (source: FeedbackSource) => {
    switch (source) {
      case 'reddit':
        return '🗨️ Reddit';
      case 'sentry':
        return '⚠️ Sentry';
      case 'manual':
        return '✍️ Manual';
    }
  };

  const canStartFix = cluster && ['new', 'failed'].includes(cluster.status);

  if (loading && !cluster) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-center py-12">
          <div className="text-gray-500">Loading cluster details...</div>
        </div>
      </div>
    );
  }

  if (error || !cluster) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="rounded-md bg-red-50 p-4">
          <div className="flex">
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Error loading cluster</h3>
              <div className="mt-2 text-sm text-red-700">{error || 'Cluster not found'}</div>
              <div className="mt-4 flex gap-3">
                <button
                  onClick={fetchCluster}
                  className="text-sm font-medium text-red-800 hover:text-red-900"
                >
                  Try again
                </button>
                <Link href="/" className="text-sm font-medium text-red-800 hover:text-red-900">
                  Back to clusters
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Count by source
  const sourceCounts = cluster.feedback_items.reduce(
    (acc, item) => {
      acc[item.source] = (acc[item.source] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <div className="min-h-screen bg-matrix-black pb-12 pt-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-6">
          <Link
            href="/clusters"
            className="text-sm font-medium text-gray-400 hover:text-matrix-green transition-colors flex items-center gap-1 uppercase tracking-wide"
          >
            ← Back to all clusters
          </Link>
        </div>

        <div className="bg-matrix-card shadow-lg rounded-2xl overflow-hidden border border-matrix-border mb-8">
          <div className="px-6 py-8 border-b border-matrix-border">
            <div className="flex justify-between items-start">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-4">
                  <h1 className="text-2xl font-bold text-white tracking-tight">
                    {cluster.title || 'Untitled Cluster'}
                  </h1>
                  <span className={getStatusBadgeClass(cluster.status)}>
                    {cluster.status.replace('_', ' ')}
                  </span>
                </div>
                <p className="text-gray-400 text-lg leading-relaxed">{cluster.summary}</p>
              </div>
              <div className="ml-6 flex flex-col gap-3">
                {cluster.github_pr_url && (
                  <a
                    href={cluster.github_pr_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center px-4 py-2 border border-matrix-border shadow-sm text-sm font-bold rounded-full text-white bg-matrix-black hover:bg-matrix-border focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-matrix-green transition-all uppercase tracking-wide"
                  >
                    View PR on GitHub
                  </a>
                )}
                {canStartFix && (
                  <button
                    onClick={handleStartFix}
                    disabled={isFixing}
                    className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-bold rounded-full shadow-neon-green text-black bg-matrix-green hover:bg-green-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-matrix-green disabled:opacity-50 disabled:cursor-not-allowed transition-all uppercase tracking-wide"
                  >
                    {isFixing ? 'Starting...' : 'Generate Fix'}
                  </button>
                )}
              </div>
            </div>

            <div className="mt-6 grid grid-cols-3 gap-6 text-sm text-gray-500 font-mono border-t border-matrix-border pt-6">
              <div>
                <dt className="text-xs font-bold text-matrix-green uppercase tracking-wider mb-1">Created</dt>
                <dd className="text-gray-300">{new Date(cluster.created_at).toLocaleString()}</dd>
              </div>
              <div>
                <dt className="text-xs font-bold text-matrix-green uppercase tracking-wider mb-1">Last Updated</dt>
                <dd className="text-gray-300">{new Date(cluster.updated_at).toLocaleString()}</dd>
              </div>
              <div>
                <dt className="text-xs font-bold text-matrix-green uppercase tracking-wider mb-1">Sources</dt>
                <dd className="text-gray-300">
                  {Object.entries(sourceCounts).map(([source, count]) => (
                    <span key={source} className="mr-2">
                      {count} {source}
                    </span>
                  ))}
                </dd>
              </div>
            </div>

            {cluster.github_branch && (
              <div className="mt-4 pt-4 border-t border-matrix-border">
                <dt className="text-xs font-bold text-matrix-green uppercase tracking-wider mb-1">GitHub Branch</dt>
                <dd className="text-gray-300 font-mono">{cluster.github_branch}</dd>
              </div>
            )}

            {cluster.error_message && (
              <div className="mt-4 p-3 bg-red-900/20 rounded-md border border-red-900/50">
                <dt className="text-xs font-bold text-red-400 uppercase tracking-wider mb-1">Error</dt>
                <dd className="text-red-300 font-mono">{cluster.error_message}</dd>
              </div>
            )}
          </div>
        </div>

        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-medium tracking-tight text-slate-50 flex items-center gap-2">
              <span className="inline-block h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
              Live Feed
            </h2>
            <div className="flex gap-2">
              <span className="px-2 py-1 rounded-md bg-white/5 border border-white/10 text-[10px] text-slate-400">Real-time</span>
              <span className="px-2 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-[10px] text-emerald-400">Connected</span>
            </div>
          </div>

          <div className="space-y-4">
            {cluster.feedback_items.map((item) => (
              <FeedbackCard key={item.id} item={item} />
            ))}
            {cluster.feedback_items.length === 0 && (
              <div className="text-center py-12 rounded-3xl border border-white/10 bg-white/5 border-dashed">
                <p className="text-slate-400">No feedback items found for this cluster.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
