'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import type { ClusterListItem } from '@/types';
import DashboardHeader from '@/components/DashboardHeader';

/**
 * Renders a client-side page that lists issue clusters and handles loading, error, and empty states.
 *
 * Fetches clusters from /api/clusters on mount and displays them in a table with title, summary,
 * count, source icons, status badges, and a link to view details.
 *
 * @returns The React element for the clusters list page.
 */
export default function ClustersListPage() {
  const [clusters, setClusters] = useState<ClusterListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchClusters();
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

  const getStatusBadgeClass = (status: ClusterListItem['status']) => {
    const baseClass = 'px-2 py-1 text-xs font-medium rounded-full';
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

  const getSourceIcon = (source: 'reddit' | 'sentry' | 'manual') => {
    switch (source) {
      case 'reddit':
        return '🗨️';
      case 'sentry':
        return '⚠️';
      case 'manual':
        return '✍️';
    }
  };

  if (loading) {
    return (
      <>
        <DashboardHeader activePage="clusters" className="mb-8" />
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-center py-12">
            <div className="text-gray-500">Loading clusters...</div>
          </div>
        </div>
      </>
    );
  }

  if (error) {
    return (
      <>
        <DashboardHeader activePage="clusters" className="mb-8" />
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
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
      </>
    );
  }

  if (clusters.length === 0) {
    return (
      <>
        <DashboardHeader activePage="clusters" className="mb-8" />
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center py-12 bg-purple-50 border border-purple-200 rounded-lg">
            <h3 className="text-lg font-medium text-purple-900 mb-2">🧠 Clustering Not Yet Implemented</h3>
            <p className="mt-2 text-sm text-purple-700 mb-4">
              The clustering feature will automatically group related feedback items using AI embeddings.
            </p>
            <p className="text-sm text-purple-700">
              For now, view all feedback in the{' '}
              <Link href="/feedback" className="font-semibold underline">
                Feedback tab
              </Link>
              . Clustering integration points are ready for implementation.
            </p>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <DashboardHeader activePage="clusters" className="mb-8" />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900">Issue Clusters</h2>
        <p className="mt-1 text-sm text-gray-500">
          Clustered feedback from Reddit and Sentry
        </p>
      </div>

      <div className="bg-white shadow-sm rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Title
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Summary
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Count
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Sources
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {clusters.map((cluster) => (
              <tr key={cluster.id} className="hover:bg-gray-50">
                <td className="px-6 py-4">
                  <Link
                    href={`/clusters/${cluster.id}`}
                    className="text-sm font-medium text-blue-600 hover:text-blue-800"
                  >
                    {cluster.title}
                  </Link>
                </td>
                <td className="px-6 py-4">
                  <div className="text-sm text-gray-900 line-clamp-2">
                    {cluster.summary}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="text-sm text-gray-900">{cluster.count}</div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex gap-1">
                    {Array.from(new Set(cluster.sources)).map((source) => (
                      <span key={source} title={source}>
                        {getSourceIcon(source)}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={getStatusBadgeClass(cluster.status)}>
                    {cluster.status.replace('_', ' ')}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm">
                  <Link
                    href={`/clusters/${cluster.id}`}
                    className="text-blue-600 hover:text-blue-800 font-medium"
                  >
                    View Details
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
    </>
  );
}
