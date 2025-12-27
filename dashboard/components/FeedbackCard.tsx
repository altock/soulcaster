'use client';

import type { FeedbackItem } from '@/types';

interface FeedbackCardProps {
  item: FeedbackItem;
}

import { useState } from 'react';
import EditFeedbackModal from './EditFeedbackModal';
import { useProject } from '@/contexts/ProjectContext';

export default function FeedbackCard({ item }: FeedbackCardProps) {
  const { currentProjectId } = useProject();
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [feedbackItem, setFeedbackItem] = useState(item);

  const handleSave = async (updatedData: Partial<FeedbackItem>) => {
    if (!currentProjectId) {
      throw new Error('No project selected');
    }

    const response = await fetch(`/api/feedback?project_id=${currentProjectId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        id: item.id,
        ...updatedData,
      }),
      cache: 'no-store', // Prevent caching
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
      case 'github':
        return (
          <svg
            viewBox="0 0 24 24"
            fill="currentColor"
            className="w-5 h-5"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
              clipRule="evenodd"
            />
          </svg>
        );
      case 'manual':
        return '✍️';
    }
  };

  const getSourceColor = (source: FeedbackItem['source']) => {
    switch (source) {
      case 'reddit':
        return 'bg-orange-900/20 text-orange-400 border border-orange-900/50';
      case 'github':
        return 'bg-purple-900/20 text-purple-400 border border-purple-900/50';
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

        {/* GitHub-specific metadata badges */}
        {feedbackItem.source === 'github' && (
          <div className="flex flex-wrap gap-2">
            {feedbackItem.repo && (
              <span className="inline-flex items-center gap-1 rounded-md border border-purple-900/50 bg-purple-900/20 px-2 py-1 text-[10px] font-medium text-purple-300">
                <svg viewBox="0 0 16 16" fill="currentColor" className="w-3 h-3">
                  <path d="M2 2.5A2.5 2.5 0 014.5 0h8.75a.75.75 0 01.75.75v12.5a.75.75 0 01-.75.75h-2.5a.75.75 0 110-1.5h1.75v-2h-8a1 1 0 00-.714 1.7.75.75 0 01-1.072 1.05A2.495 2.495 0 012 11.5v-9zm10.5-1V9h-8c-.356 0-.694.074-1 .208V2.5a1 1 0 011-1h8zM5 12.25v3.25a.25.25 0 00.4.2l1.45-1.087a.25.25 0 01.3 0L8.6 15.7a.25.25 0 00.4-.2v-3.25a.25.25 0 00-.25-.25h-3.5a.25.25 0 00-.25.25z" />
                </svg>
                {feedbackItem.repo}
              </span>
            )}
            {feedbackItem.github_issue_number && (
              <span className="inline-flex items-center gap-1 rounded-md border border-purple-900/50 bg-purple-900/20 px-2 py-1 text-[10px] font-medium text-purple-300">
                #{feedbackItem.github_issue_number}
              </span>
            )}
            {feedbackItem.status && (
              <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[10px] font-medium ${
                feedbackItem.status === 'open'
                  ? 'border-green-900/50 bg-green-900/20 text-green-300'
                  : 'border-gray-900/50 bg-gray-900/20 text-gray-300'
              }`}>
                <span className={`w-2 h-2 rounded-full ${
                  feedbackItem.status === 'open' ? 'bg-green-400' : 'bg-gray-400'
                }`} />
                {feedbackItem.status}
              </span>
            )}
          </div>
        )}

        {/* Title - clickable for GitHub issues */}
        {feedbackItem.source === 'github' && feedbackItem.title && (
          <div>
            {feedbackItem.github_issue_url ? (
              <a
                href={feedbackItem.github_issue_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-base font-semibold text-white hover:text-purple-300 transition-colors line-clamp-2 block"
              >
                {feedbackItem.title}
                <svg
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  className="w-3 h-3 inline-block ml-1 opacity-50"
                >
                  <path
                    fillRule="evenodd"
                    d="M4.25 5.5a.75.75 0 00-.75.75v8.5c0 .414.336.75.75.75h8.5a.75.75 0 00.75-.75v-4a.75.75 0 011.5 0v4A2.25 2.25 0 0112.75 17h-8.5A2.25 2.25 0 012 14.75v-8.5A2.25 2.25 0 014.25 4h5a.75.75 0 010 1.5h-5z"
                    clipRule="evenodd"
                  />
                  <path
                    fillRule="evenodd"
                    d="M6.194 12.753a.75.75 0 001.06.053L16.5 4.44v2.81a.75.75 0 001.5 0v-4.5a.75.75 0 00-.75-.75h-4.5a.75.75 0 000 1.5h2.553l-9.056 8.194a.75.75 0 00-.053 1.06z"
                    clipRule="evenodd"
                  />
                </svg>
              </a>
            ) : (
              <h3 className="text-base font-semibold text-white line-clamp-2">
                {feedbackItem.title}
              </h3>
            )}
          </div>
        )}

        <p className="text-sm leading-relaxed text-slate-300 line-clamp-4">{feedbackItem.body}</p>

        {feedbackItem.github_repo_url && feedbackItem.source !== 'github' && (
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
