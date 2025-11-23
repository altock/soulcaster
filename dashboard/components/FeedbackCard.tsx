'use client';

import type { FeedbackItem } from '@/types';

interface FeedbackCardProps {
  item: FeedbackItem;
}

import { useState } from 'react';
import EditFeedbackModal from './EditFeedbackModal';

export default function FeedbackCard({ item }: FeedbackCardProps) {
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [feedbackItem, setFeedbackItem] = useState(item);

  const handleSave = async (updatedData: Partial<FeedbackItem>) => {
    const response = await fetch('/api/feedback', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        id: item.id,
        ...updatedData,
      }),
    });

    if (!response.ok) {
      throw new Error('Failed to update feedback');
    }

    setFeedbackItem((prev) => ({ ...prev, ...updatedData }));
  };
  const getSourceIcon = (source: FeedbackItem['source']) => {
    switch (source) {
      case 'reddit':
        return '🗨️';
      case 'sentry':
        return '⚠️';
      case 'manual':
        return '✍️';
    }
  };

  const getSourceColor = (source: FeedbackItem['source']) => {
    switch (source) {
      case 'reddit':
        return 'bg-orange-900/20 text-orange-400 border border-orange-900/50';
      case 'sentry':
        return 'bg-red-900/20 text-red-400 border border-red-900/50';
      case 'manual':
        return 'bg-matrix-green-dim text-matrix-green border border-matrix-green/30';
    }
  };

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleString();
    } catch {
      return dateString;
    }
  };

  return (
    <div className="group relative overflow-hidden rounded-[2rem] border border-white/10 bg-gradient-to-br from-emerald-500/15 via-emerald-500/5 to-transparent p-6 shadow-[0_0_60px_rgba(16,185,129,0.15)] transition-all duration-500 hover:border-emerald-500/30 hover:shadow-[0_0_80px_rgba(16,185,129,0.25)]">
      {/* Glow Effect */}
      <div className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-500 group-hover:opacity-100">
        <div className="absolute -left-24 top-10 h-64 w-64 animate-pulse rounded-full bg-emerald-500/25 blur-3xl"></div>
        <div className="absolute -bottom-10 right-0 h-52 w-52 rounded-full bg-emerald-400/20 blur-3xl"></div>
      </div>

      <div className="relative z-10 flex flex-col gap-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-gradient-to-br from-white/5 to-transparent transition-colors group-hover:border-emerald-500/30">
              <span className="text-xl">{getSourceIcon(feedbackItem.source)}</span>
            </div>
            <div>
              <div className="text-xs font-medium text-slate-200 transition-colors group-hover:text-emerald-300">
                {feedbackItem.source}
              </div>
              <div className="text-[10px] text-slate-500">{formatDate(feedbackItem.created_at)}</div>
            </div>
          </div>
          <div
            className={`rounded-md border px-2 py-1 text-[10px] font-medium backdrop-blur-md ${feedbackItem.source === 'manual'
              ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300'
              : 'border-white/10 bg-black/40 text-slate-300'
              }`}
          >
            {feedbackItem.source === 'manual' ? 'Verified' : 'Auto-Captured'}
          </div>
        </div>

        <p className="text-sm leading-relaxed text-slate-300 line-clamp-4">{feedbackItem.body}</p>

        {feedbackItem.github_repo_url && (
          <a
            href={feedbackItem.github_repo_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-xs text-emerald-400 hover:text-emerald-300 transition-colors"
          >
            <svg
              viewBox="0 0 24 24"
              fill="currentColor"
              className="w-4 h-4"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
                clipRule="evenodd"
              />
            </svg>
            View Repository
          </a>
        )}

        <div className="flex gap-2 border-t border-white/5 pt-4">
          <button
            onClick={() => setIsEditModalOpen(true)}
            className="flex-1 cursor-pointer rounded-full border border-white/5 bg-white/5 py-1.5 text-center text-[10px] font-medium text-slate-400 transition-colors hover:bg-white/10 hover:text-emerald-400"
          >
            Edit
          </button>
        </div>
      </div>

      <EditFeedbackModal
        item={feedbackItem}
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        onSave={handleSave}
      />
    </div>
  );
}
