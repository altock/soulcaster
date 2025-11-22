'use client';

import type { FeedbackItem } from '@/types';

interface FeedbackCardProps {
  item: FeedbackItem;
}

export default function FeedbackCard({ item }: FeedbackCardProps) {
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
        return 'bg-orange-100 text-orange-800';
      case 'sentry':
        return 'bg-red-100 text-red-800';
      case 'manual':
        return 'bg-green-100 text-green-800';
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
    <div className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <h3 className="text-lg font-semibold text-gray-900 flex-1">{item.title}</h3>
        <div className="flex items-center gap-2">
          <span className={`px-2 py-1 text-xs font-medium rounded-full ${getSourceColor(item.source)}`}>
            {getSourceIcon(item.source)} {item.source}
          </span>
        </div>
      </div>

      <p className="text-gray-700 text-sm mb-4 line-clamp-3">{item.body}</p>

      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>{formatDate(item.created_at)}</span>
        {item.external_id && (
          <span className="font-mono bg-gray-100 px-2 py-1 rounded">
            {item.external_id.substring(0, 8)}
          </span>
        )}
      </div>

      {item.metadata && Object.keys(item.metadata).length > 0 && (
        <details className="mt-3 text-xs">
          <summary className="cursor-pointer text-gray-600 hover:text-gray-800">
            Metadata
          </summary>
          <pre className="mt-2 bg-gray-50 p-2 rounded overflow-x-auto">
            {JSON.stringify(item.metadata, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}
