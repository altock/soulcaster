'use client';

import { useEffect, useState } from 'react';

type SourceType = 'reddit' | 'sentry';

export default function SourceConfig() {
  const [selectedSource, setSelectedSource] = useState<SourceType | null>(null);
  const [subreddits, setSubreddits] = useState<string[]>([]);
  const [newSubreddit, setNewSubreddit] = useState('');
  const [loadingSubs, setLoadingSubs] = useState(false);
  const [savingSubs, setSavingSubs] = useState(false);
  const [subsMessage, setSubsMessage] = useState<string | null>(null);
  const [subsError, setSubsError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoadingSubs(true);
      setSubsError(null);
      try {
        const res = await fetch('/api/config/reddit/subreddits', { cache: 'no-store' });
        const data = await res.json();
        setSubreddits(data.subreddits ?? []);
      } catch (err) {
        setSubsError('Failed to load subreddit config');
      } finally {
        setLoadingSubs(false);
      }
    };
    load();
  }, []);

  const sources = [
    {
      type: 'reddit' as const,
      icon: '🗨️',
      title: 'Reddit Integration',
      description: 'Monitor subreddits (JSON polling, no OAuth)',
    },
    {
      type: 'sentry' as const,
      icon: '⚠️',
      title: 'Sentry Webhook',
      description: 'Receive error reports from Sentry in real-time',
    },
  ];

  const addSubreddit = () => {
    const slug = newSubreddit.trim().toLowerCase();
    if (!slug) return;
    if (subreddits.includes(slug)) {
      setNewSubreddit('');
      return;
    }
    setSubreddits((prev) => [...prev, slug]);
    setNewSubreddit('');
  };

  const removeSubreddit = (slug: string) => {
    setSubreddits((prev) => prev.filter((s) => s !== slug));
  };

  const saveSubreddits = async () => {
    setSavingSubs(true);
    setSubsMessage(null);
    setSubsError(null);
    try {
      const res = await fetch('/api/config/reddit/subreddits', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subreddits }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || 'Failed to save');
      }
      setSubreddits(data.subreddits ?? []);
      setSubsMessage('Saved subreddit list');
    } catch (err: any) {
      setSubsError(err?.message || 'Failed to save subreddit list');
    } finally {
      setSavingSubs(false);
    }
  };

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
        <div className="border-t pt-4 space-y-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h4 className="font-semibold text-gray-900">Reddit Poller</h4>
              <p className="text-sm text-gray-600">
                Uses public JSON feeds (no OAuth). Poller reads this list from Redis and posts to
                the backend.
              </p>
            </div>
            <span className="text-xs font-medium text-gray-500">
              1 req/sec per subreddit, caches with ETags
            </span>
          </div>

          <div className="bg-gray-50 p-4 rounded-md space-y-3">
            <div className="flex items-center gap-2 flex-wrap">
              <input
                type="text"
                placeholder="add subreddit (e.g., claudeai)"
                value={newSubreddit}
                onChange={(e) => setNewSubreddit(e.target.value)}
                className="flex-1 min-w-[200px] rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                type="button"
                onClick={addSubreddit}
                className="px-3 py-2 text-sm font-semibold text-white bg-blue-600 rounded hover:bg-blue-700"
              >
                Add
              </button>
              <button
                type="button"
                onClick={saveSubreddits}
                disabled={savingSubs || subreddits.length === 0}
                className={`px-3 py-2 text-sm font-semibold rounded ${
                  savingSubs || subreddits.length === 0
                    ? 'bg-gray-300 text-gray-600'
                    : 'bg-green-600 text-white hover:bg-green-700'
                }`}
              >
                {savingSubs ? 'Saving…' : 'Save list'}
              </button>
            </div>

            {loadingSubs ? (
              <p className="text-sm text-gray-500">Loading subreddits…</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {subreddits.length === 0 && (
                  <span className="text-sm text-gray-500">No subreddits configured yet.</span>
                )}
                {subreddits.map((sub) => (
                  <span
                    key={sub}
                    className="inline-flex items-center gap-2 bg-white border border-gray-200 rounded-full px-3 py-1 text-sm"
                  >
                    r/{sub}
                    <button
                      type="button"
                      onClick={() => removeSubreddit(sub)}
                      className="text-gray-500 hover:text-red-600"
                    >
                      ✕
                    </button>
                  </span>
                ))}
              </div>
            )}

            {subsMessage && <p className="text-sm text-green-700">{subsMessage}</p>}
            {subsError && <p className="text-sm text-red-600">{subsError}</p>}
            <p className="text-xs text-gray-500">
              Keep this list small (e.g., 1–3 subs). Poller runs server-side: `python -m
              backend.reddit_poller`.
            </p>
          </div>

          <div className="bg-gray-50 p-4 rounded-md text-sm space-y-2">
            <p>
              <strong>Poller command (runs continuously):</strong>
            </p>
            <pre className="bg-gray-800 text-gray-100 p-2 rounded overflow-x-auto">
              {`BACKEND_URL=http://localhost:8000 \\
UPSTASH_REDIS_REST_URL=... \\
UPSTASH_REDIS_REST_TOKEN=... \\
python -m backend.reddit_poller`}
            </pre>
            <p className="text-gray-600">
              The poller re-reads this list every cycle (5–10 minutes by default) and posts new
              items to `/ingest/reddit`.
            </p>
          </div>
        </div>
      )}

      {selectedSource === 'sentry' && (
        <div className="border-t pt-4 space-y-3">
          <h4 className="font-semibold text-gray-900">Sentry Setup Instructions</h4>
          <div className="bg-gray-50 p-4 rounded-md text-sm space-y-2">
            <p>
              <strong>1. Configure webhook URL in Sentry:</strong>
            </p>
            <pre className="bg-gray-800 text-gray-100 p-2 rounded overflow-x-auto">
              {typeof window !== 'undefined'
                ? `${window.location.origin}/api/ingest/sentry`
                : 'http://your-domain.com/api/ingest/sentry'}
            </pre>

            <p>
              <strong>2. In Sentry project settings:</strong>
            </p>
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
