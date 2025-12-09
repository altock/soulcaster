'use client';

import { useEffect, useState } from 'react';
import FeedbackCard from './FeedbackCard';
import type { FeedbackItem, FeedbackSource, GitHubRepo } from '@/types';

interface FeedbackListProps {
  refreshTrigger?: number;
}

export default function FeedbackList({ refreshTrigger }: FeedbackListProps) {
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
        {(['all', 'reddit', 'github', 'manual'] as const).map((filter) => (
          <button
            key={filter}
            onClick={() => setSourceFilter(filter)}
            className={`px-4 py-2 text-sm font-medium transition-all uppercase tracking-wider rounded-t-lg relative top-[1px] ${sourceFilter === filter
                ? 'border-b-2 border-emerald-500 text-emerald-400 drop-shadow-[0_0_5px_rgba(16,185,129,0.5)]'
                : 'text-slate-500 hover:text-emerald-300'
              }`}
          >
            {filter.charAt(0).toUpperCase() + filter.slice(1)}
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
              ? 'Start by submitting manual feedback or configuring Reddit sources.'
              : `No ${sourceFilter} feedback items yet.`}
          </p>
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
