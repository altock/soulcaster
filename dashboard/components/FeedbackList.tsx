'use client';

import { useEffect, useState } from 'react';
import FeedbackCard from './FeedbackCard';
import type { FeedbackItem, FeedbackSource } from '@/types';

interface FeedbackListProps {
  refreshTrigger?: number;
}

export default function FeedbackList({ refreshTrigger }: FeedbackListProps) {
  const [items, setItems] = useState<FeedbackItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState<FeedbackSource | 'all'>('all');

  useEffect(() => {
    fetchFeedback();
  }, [sourceFilter, refreshTrigger]);

  const fetchFeedback = async () => {
    try {
      setLoading(true);
      setError(null);
      const queryParams = new URLSearchParams({ limit: '50' });
      if (sourceFilter !== 'all') {
        queryParams.append('source', sourceFilter);
      }
      const response = await fetch(`/api/feedback?${queryParams}`);
      if (!response.ok) {
        throw new Error('Failed to fetch feedback');
      }
      const data = await response.json();
      setItems(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
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

  if (error) {
    return (
      <div className="rounded-md bg-red-50 p-4">
        <div className="flex">
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800">Error loading feedback</h3>
            <div className="mt-2 text-sm text-red-700">{error}</div>
            <button
              onClick={fetchFeedback}
              className="mt-3 text-sm font-medium text-red-800 hover:text-red-900"
            >
              Try again
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Filter tabs */}
      <div className="flex gap-2 mb-6 border-b border-white/10 pb-1">
        {(['all', 'reddit', 'sentry', 'manual'] as const).map((filter) => (
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

      {items.length === 0 ? (
        <div className="text-center py-16 bg-emerald-950/20 rounded-3xl border border-white/10 backdrop-blur-sm">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-white/5 mb-4">
            <span className="text-2xl">📭</span>
          </div>
          <h3 className="text-lg font-medium text-white">No feedback items found</h3>
          <p className="mt-2 text-sm text-slate-400 max-w-sm mx-auto">
            {sourceFilter === 'all'
              ? 'Start by submitting manual feedback or configuring Reddit/Sentry sources.'
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
