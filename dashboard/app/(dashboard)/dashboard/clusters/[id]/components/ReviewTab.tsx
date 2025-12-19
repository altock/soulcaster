'use client';

import type { FeedbackItem } from '@/types';
import FeedbackCard from '@/components/FeedbackCard';
import GitHubIssuesList from './GitHubIssuesList';

interface ReviewTabProps {
  feedbackItems: FeedbackItem[];
  allItems: FeedbackItem[]; // For GitHub issues sidebar
}

export default function ReviewTab({ feedbackItems, allItems }: ReviewTabProps) {
  const hasGitHubIssues = allItems.some((item) => item.source === 'github');

  return (
    <div className={`grid gap-6 ${hasGitHubIssues ? 'lg:grid-cols-3' : 'grid-cols-1'}`}>
      {/* Feedback Items */}
      <div className={hasGitHubIssues ? 'lg:col-span-2' : ''}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium tracking-tight text-slate-50">
            Feedback Items
          </h2>
          <span className="text-xs text-slate-500">
            {feedbackItems.length} {feedbackItems.length === 1 ? 'item' : 'items'}
          </span>
        </div>

        <div className="space-y-4">
          {feedbackItems.map((item) => (
            <FeedbackCard key={item.id} item={item} />
          ))}
          {feedbackItems.length === 0 && (
            <div className="text-center py-12 rounded-2xl border border-white/10 bg-white/5 border-dashed">
              <p className="text-slate-400">No feedback items found.</p>
            </div>
          )}
        </div>
      </div>

      {/* GitHub Issues Sidebar */}
      {hasGitHubIssues && (
        <div className="lg:col-span-1">
          <GitHubIssuesList items={allItems} />
        </div>
      )}
    </div>
  );
}
