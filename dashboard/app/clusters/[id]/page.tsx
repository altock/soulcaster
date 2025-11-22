'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import type { ClusterDetail } from '@/types';

/**
 * Client React component that renders details for a single cluster, its feedback items, and actions related to generating fixes.
 *
 * Displays loading and error states, the cluster summary (timestamps, source counts, GitHub links/branch, and any error message), a list of feedback items, and an action to start fix generation. While a cluster is in the "fixing" status the component polls the API for updates.
 *
 * @returns The rendered JSX element for the cluster detail page
 */
export default function ClusterDetailPage() {
  const params = useParams();
  const router = useRouter();
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
    const baseClass = 'px-3 py-1 text-sm font-medium rounded-full';
    switch (status) {
      case 'new':
        return `${baseClass} bg-blue-100 text-blue-800`;
      case 'fixing':
        return `${baseClass} bg-yellow-100 text-yellow-800`;
      case 'pr_opened':
        return `${baseClass} bg-green-100 text-green-800`;
      case 'failed':
        return `${baseClass} bg-red-100 text-red-800`;
      default:
        return `${baseClass} bg-gray-100 text-gray-800`;
    }
  };

  const getSourceIcon = (source: 'reddit' | 'sentry') => {
    switch (source) {
      case 'reddit':
        return '🗨️ Reddit';
      case 'sentry':
        return '⚠️ Sentry';
    }
  };

  const canStartFix = cluster && ['new', 'failed'].includes(cluster.status);

  if (loading && !cluster) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-gray-500">Loading cluster details...</div>
      </div>
    );
  }

  if (error || !cluster) {
    return (
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
    );
  }

  // Count by source
  const sourceCounts = cluster.feedback_items.reduce((acc, item) => {
    acc[item.source] = (acc[item.source] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <Link href="/" className="text-sm text-blue-600 hover:text-blue-800 mb-2 inline-block">
          ← Back to all clusters
        </Link>
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <h2 className="text-2xl font-bold text-gray-900">{cluster.title}</h2>
            <div className="mt-2 flex items-center gap-3">
              <span className={getStatusBadgeClass(cluster.status)}>
                {cluster.status.replace('_', ' ')}
              </span>
              <span className="text-sm text-gray-500">
                {cluster.feedback_items.length} feedback items
              </span>
            </div>
          </div>
          <div className="flex gap-2">
            {cluster.github_pr_url && (
              <a
                href={cluster.github_pr_url}
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 bg-gray-900 text-white rounded-md hover:bg-gray-800 text-sm font-medium"
              >
                View PR on GitHub
              </a>
            )}
            {canStartFix && (
              <button
                onClick={handleStartFix}
                disabled={isFixing}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 text-sm font-medium"
              >
                {isFixing ? 'Starting...' : 'Generate Fix'}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Summary */}
      <div className="bg-white shadow-sm rounded-lg p-6 mb-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-3">Summary</h3>
        <p className="text-gray-700">{cluster.summary}</p>

        <div className="mt-4 grid grid-cols-3 gap-4">
          <div>
            <dt className="text-sm font-medium text-gray-500">Created</dt>
            <dd className="mt-1 text-sm text-gray-900">
              {new Date(cluster.created_at).toLocaleString()}
            </dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">Last Updated</dt>
            <dd className="mt-1 text-sm text-gray-900">
              {new Date(cluster.updated_at).toLocaleString()}
            </dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">Sources</dt>
            <dd className="mt-1 text-sm text-gray-900">
              {Object.entries(sourceCounts).map(([source, count]) => (
                <div key={source}>
                  {count} {source}
                </div>
              ))}
            </dd>
          </div>
        </div>

        {cluster.github_branch && (
          <div className="mt-4">
            <dt className="text-sm font-medium text-gray-500">GitHub Branch</dt>
            <dd className="mt-1 text-sm text-gray-900 font-mono">{cluster.github_branch}</dd>
          </div>
        )}

        {cluster.error_message && (
          <div className="mt-4 p-3 bg-red-50 rounded-md">
            <dt className="text-sm font-medium text-red-800">Error</dt>
            <dd className="mt-1 text-sm text-red-700 font-mono">{cluster.error_message}</dd>
          </div>
        )}
      </div>

      {/* Feedback Items */}
      <div className="bg-white shadow-sm rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Feedback Items</h3>
        <div className="space-y-4">
          {cluster.feedback_items.map((item) => (
            <div key={item.id} className="border border-gray-200 rounded-md p-4">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-900">
                    {getSourceIcon(item.source)}
                  </span>
                  {item.metadata?.permalink && (
                    <a
                      href={item.metadata.permalink}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-600 hover:text-blue-800"
                    >
                      View original →
                    </a>
                  )}
                </div>
                <span className="text-xs text-gray-500">
                  {new Date(item.created_at).toLocaleString()}
                </span>
              </div>
              <h4 className="text-sm font-medium text-gray-900 mb-1">{item.title}</h4>
              <p className="text-sm text-gray-700 whitespace-pre-wrap">{item.body}</p>
              {item.metadata?.subreddit && (
                <div className="mt-2 text-xs text-gray-500">
                  r/{item.metadata.subreddit}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}