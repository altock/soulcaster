'use client';

import { useState } from 'react';

type SourceType = 'reddit' | 'sentry';

export default function SourceConfig() {
  const [selectedSource, setSelectedSource] = useState<SourceType | null>(null);

  const sources = [
    {
      type: 'reddit' as const,
      icon: '🗨️',
      title: 'Reddit Integration',
      description: 'Monitor subreddits for bug reports and feature requests',
    },
    {
      type: 'sentry' as const,
      icon: '⚠️',
      title: 'Sentry Webhook',
      description: 'Receive error reports from Sentry in real-time',
    },
  ];

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Configure Feedback Sources</h3>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        {sources.map((source) => (
          <button
            key={source.type}
            onClick={() => setSelectedSource(source.type)}
            className={`p-4 border-2 rounded-lg text-left transition-all ${
              selectedSource === source.type
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-200 hover:border-gray-300'
            }`}
          >
            <div className="text-2xl mb-2">{source.icon}</div>
            <h4 className="font-semibold text-gray-900">{source.title}</h4>
            <p className="text-sm text-gray-600 mt-1">{source.description}</p>
          </button>
        ))}
      </div>

      {selectedSource === 'reddit' && (
        <div className="border-t pt-4 space-y-3">
          <h4 className="font-semibold text-gray-900">Reddit Setup Instructions</h4>
          <div className="bg-gray-50 p-4 rounded-md text-sm space-y-2">
            <p><strong>1. Set environment variables:</strong></p>
            <pre className="bg-gray-800 text-gray-100 p-2 rounded overflow-x-auto">
{`export REDDIT_CLIENT_ID="your_client_id"
export REDDIT_CLIENT_SECRET="your_secret"
export REDDIT_SUBREDDIT="programming"`}
            </pre>

            <p><strong>2. Run the Reddit poller:</strong></p>
            <pre className="bg-gray-800 text-gray-100 p-2 rounded overflow-x-auto">
              python -m backend.reddit_poller
            </pre>

            <p className="text-gray-600 mt-3">
              📖 Get Reddit API credentials from{' '}
              <a
                href="https://www.reddit.com/prefs/apps"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                reddit.com/prefs/apps
              </a>
            </p>
          </div>
        </div>
      )}

      {selectedSource === 'sentry' && (
        <div className="border-t pt-4 space-y-3">
          <h4 className="font-semibold text-gray-900">Sentry Setup Instructions</h4>
          <div className="bg-gray-50 p-4 rounded-md text-sm space-y-2">
            <p><strong>1. Configure webhook URL in Sentry:</strong></p>
            <pre className="bg-gray-800 text-gray-100 p-2 rounded overflow-x-auto">
              {typeof window !== 'undefined'
                ? `${window.location.origin}/api/ingest/sentry`
                : 'http://your-domain.com/api/ingest/sentry'
              }
            </pre>

            <p><strong>2. In Sentry project settings:</strong></p>
            <ul className="list-disc list-inside space-y-1 text-gray-700">
              <li>Go to Settings → Integrations → WebHooks</li>
              <li>Add the webhook URL above</li>
              <li>Enable "Issue" events</li>
              <li>Save the webhook configuration</li>
            </ul>

            <p className="text-gray-600 mt-3">
              📖 Learn more at{' '}
              <a
                href="https://docs.sentry.io/product/integrations/integration-platform/webhooks/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                Sentry Webhook Docs
              </a>
            </p>
          </div>
        </div>
      )}

      {!selectedSource && (
        <p className="text-sm text-gray-500 text-center py-4">
          Select a source above to view setup instructions
        </p>
      )}
    </div>
  );
}
