'use client';

import { useEffect, useState } from 'react';
import FeedbackCard from './FeedbackCard';
import type { FeedbackItem, FeedbackSource, GitHubRepo } from '@/types';

interface FeedbackListProps {
  refreshTrigger?: number;
  onRequestShowSources?: () => void;
}

/**
 * Render a filterable feedback list with source tabs, optional repository filter, loading state, and empty-state handling.
 *
 * @param refreshTrigger - Optional external numeric trigger; changing this value forces the list to re-fetch feedback.
 * @returns The component's rendered JSX containing filters, a loading indicator, an empty-state message, or a grid of feedback cards.
 */
export default function FeedbackList({ refreshTrigger, onRequestShowSources }: FeedbackListProps) {
  const [items, setItems] = useState<FeedbackItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [sourceFilter, setSourceFilter] = useState<FeedbackSource | 'all'>('all');
  const [repoFilter, setRepoFilter] = useState<string>('all');
  const [repos, setRepos] = useState<GitHubRepo[]>([]);

  useEffect(() => {
    fetchRepos();
  }, []);

  useEffect(() => {
    fetchFeedback();
  }, [sourceFilter, repoFilter, refreshTrigger]);

  const fetchRepos = async () => {
    try {
      const response = await fetch('/api/config/github/repos');
      if (response.ok) {
        const data = await response.json();
        setRepos(data.repos || []);
      }
    } catch (err) {
      console.error('Failed to fetch repos:', err);
    }
  };

  // Disable Reddit in UI while keeping type support in code paths
  const sourceFilters: Array<{
    id: FeedbackSource | 'all';
    label: string;
    enabled: boolean;
  }> = [
    { id: 'all', label: 'All', enabled: true },
    { id: 'reddit', label: 'Reddit', enabled: false },
    { id: 'github', label: 'GitHub', enabled: true },
    { id: 'manual', label: 'Manual', enabled: true },
  ];

  // Ensure we never stay on a disabled filter
  useEffect(() => {
    const current = sourceFilters.find((f) => f.id === sourceFilter);
    if (current && !current.enabled) {
      setSourceFilter('all');
    }
  }, [sourceFilter]);

  const fetchFeedback = async () => {
    try {
      setLoading(true);
      const queryParams = new URLSearchParams({ limit: '50' });
      if (sourceFilter !== 'all') {
        queryParams.append('source', sourceFilter);
      }
      if (repoFilter !== 'all') {
        queryParams.append('repo', repoFilter);
      }
      const response = await fetch(`/api/feedback?${queryParams}`);
      if (!response.ok) {
        // Handle gracefully - show empty state instead of error for expected cases
        // like missing project_id or no data
        console.warn('Failed to fetch feedback:', response.status);
        setItems([]);
        return;
      }
      const data = await response.json();
      setItems(data.items || []);
    } catch (err) {
      console.error('Error fetching feedback:', err);
      // Show empty state instead of error for better UX
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-gray-500">Loading feedback...</div>
      </div>
    );
  }

  return (
    <div>
      {/* Filter tabs */}
      <div className="flex gap-2 mb-6 border-b border-white/10 pb-1">
        {sourceFilters.map((filter) => (
          <button
            key={filter.id}
            type="button"
            disabled={!filter.enabled}
            onClick={() => {
              if (filter.enabled) setSourceFilter(filter.id);
            }}
            className={`px-4 py-2 text-sm font-medium transition-all uppercase tracking-wider rounded-t-lg relative top-[1px] ${
              sourceFilter === filter.id && filter.enabled
                ? 'border-b-2 border-emerald-500 text-emerald-400 drop-shadow-[0_0_5px_rgba(16,185,129,0.5)]'
                : 'text-slate-500 hover:text-emerald-300'
            } ${!filter.enabled ? 'opacity-50 cursor-not-allowed hover:text-slate-500' : ''}`}
          >
            <span className="flex items-center gap-2">
              {filter.label}
              {!filter.enabled && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/10 text-slate-300 border border-white/10">
                  Coming soon
                </span>
              )}
            </span>
          </button>
        ))}
      </div>

      {/* Repo filter dropdown - only show when GitHub source is selected or 'all' */}
      {repos.length > 0 && (sourceFilter === 'github' || sourceFilter === 'all') && (
        <div className="mb-6 flex items-center gap-3">
          <label htmlFor="repo-filter" className="text-sm font-medium text-slate-300">
            Filter by repository:
          </label>
          <select
            id="repo-filter"
            value={repoFilter}
            onChange={(e) => setRepoFilter(e.target.value)}
            className="rounded-lg border border-white/10 bg-emerald-950/30 px-4 py-2 text-sm text-slate-200 backdrop-blur-sm transition-all hover:border-emerald-500/30 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
          >
            <option value="all">All repositories</option>
            {repos.map((repo) => (
              <option key={repo.full_name} value={repo.full_name}>
                {repo.full_name} ({repo.issue_count || 0} issues)
              </option>
            ))}
          </select>
        </div>
      )}

      {items.length === 0 ? (
        <div className="text-center py-16 bg-emerald-950/20 rounded-3xl border border-white/10 backdrop-blur-sm">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-white/5 mb-4">
            <span className="text-2xl">📭</span>
          </div>
          <h3 className="text-lg font-medium text-white">No feedback items found</h3>
          <p className="mt-2 text-sm text-slate-400 max-w-sm mx-auto">
            {sourceFilter === 'all'
              ? 'Get started by connecting a feedback source or submitting manual feedback.'
              : `No ${sourceFilter} feedback items yet.`}
          </p>
          {sourceFilter === 'all' && onRequestShowSources && (
            <div className="mt-6">
              <button
                onClick={onRequestShowSources}
                className="inline-flex items-center justify-center gap-2 px-5 py-2.5 bg-emerald-500 text-black rounded-full hover:bg-emerald-400 transition-all font-medium shadow-[0_0_15px_rgba(16,185,129,0.3)]"
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
                    d="M12 6v6m0 0v6m0-6h6m-6 0H6"
                  />
                </svg>
                Connect GitHub Repository
              </button>
            </div>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((item) => (
            <FeedbackCard key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}