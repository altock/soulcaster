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
    <div className="bg-emerald-950/20 border border-white/10 backdrop-blur-sm rounded-3xl p-6 relative overflow-hidden mt-6">
      <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 via-transparent to-transparent pointer-events-none" />
      <h3 className="text-lg font-semibold text-white mb-4 relative z-10">Configure Feedback Sources</h3>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4 relative z-10">
        {sources.map((source) => (
          <button
            key={source.type}
            onClick={() => setSelectedSource(source.type)}
            className={`p-4 border-2 rounded-2xl text-left transition-all ${selectedSource === source.type
              ? 'border-emerald-500 bg-emerald-500/10 shadow-[0_0_20px_rgba(16,185,129,0.1)]'
              : 'border-white/5 bg-black/20 hover:border-white/10 hover:bg-black/30'
              }`}
          >
            <div className="text-2xl mb-2">{source.icon}</div>
            <h4 className={`font-semibold ${selectedSource === source.type ? 'text-emerald-300' : 'text-slate-200'}`}>{source.title}</h4>
            <p className="text-sm text-slate-400 mt-1">{source.description}</p>
          </button>
        ))}
      </div>

      {selectedSource === 'reddit' && (
        <div className="border-t border-white/10 pt-4 space-y-4 relative z-10">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h4 className="font-semibold text-slate-200">Reddit Poller</h4>
              <p className="text-sm text-slate-400">
                Uses public JSON feeds (no OAuth). Poller reads this list from Redis and posts to
                the backend.
              </p>
            </div>
            <span className="text-xs font-medium text-slate-500">
              1 req/sec per subreddit, caches with ETags
            </span>
          </div>

          <div className="bg-black/20 border border-white/5 p-4 rounded-xl space-y-3">
            <div className="flex items-center gap-2 flex-wrap">
              <input
                type="text"
                placeholder="add subreddit (e.g., claudeai)"
                value={newSubreddit}
                onChange={(e) => setNewSubreddit(e.target.value)}
                className="flex-1 min-w-[200px] rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
              />
              <button
                type="button"
                onClick={addSubreddit}
                className="px-3 py-2 text-sm font-semibold text-black bg-emerald-500 rounded-lg hover:bg-emerald-400 transition-colors"
              >
                Add
              </button>
              <button
                type="button"
                onClick={saveSubreddits}
                disabled={savingSubs || subreddits.length === 0}
                className={`px-3 py-2 text-sm font-semibold rounded-lg transition-colors ${savingSubs || subreddits.length === 0
                  ? 'bg-white/5 text-slate-500 cursor-not-allowed'
                  : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/30'
                  }`}
              >
                {savingSubs ? 'Saving…' : 'Save list'}
              </button>
              <button
                type="button"
                onClick={async () => {
                  try {
                    const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'}/admin/trigger-poll`, {
                      method: 'POST',
                    });
                    const data = await res.json();
                    if (res.ok) {
                      alert(`Poll triggered: ${data.message}`);
                    } else {
                      alert(`Failed to trigger poll: ${data.detail || 'Unknown error'}`);
                    }
                  } catch (err) {
                    alert('Failed to connect to backend poller');
                  }
                }}
                className="px-3 py-2 text-sm font-semibold text-emerald-300 border border-emerald-500/30 rounded-lg hover:bg-emerald-500/10 transition-colors"
              >
                ⚡ Trigger Poll
              </button>
            </div>

            {loadingSubs ? (
              <p className="text-sm text-slate-500">Loading subreddits…</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {subreddits.length === 0 && (
                  <span className="text-sm text-slate-500">No subreddits configured yet.</span>
                )}
                {subreddits.map((sub) => (
                  <span
                    key={sub}
                    className="inline-flex items-center gap-2 bg-white/5 border border-white/10 rounded-full px-3 py-1 text-sm text-slate-300"
                  >
                    r/{sub}
                    <button
                      type="button"
                      onClick={() => removeSubreddit(sub)}
                      className="text-slate-500 hover:text-rose-400 transition-colors"
                    >
                      ✕
                    </button>
                  </span>
                ))}
              </div>
            )}

            {subsMessage && <p className="text-sm text-emerald-400">{subsMessage}</p>}
            {subsError && <p className="text-sm text-rose-400">{subsError}</p>}
            <p className="text-xs text-slate-500">
              Keep this list small (e.g., 1–3 subs).
            </p>
          </div>
        </div>
      )}

      {selectedSource === 'sentry' && (
        <div className="border-t border-white/10 pt-4 space-y-3 relative z-10">
          <h4 className="font-semibold text-slate-200">Sentry Setup Instructions</h4>
          <div className="bg-black/20 border border-white/5 p-4 rounded-xl text-sm space-y-2">
            <p className="text-slate-300">
              <strong>1. Configure webhook URL in Sentry:</strong>
            </p>
            <pre className="bg-black/60 border border-white/10 text-emerald-400/90 p-3 rounded-lg overflow-x-auto font-mono text-xs">
              {typeof window !== 'undefined'
                ? `${window.location.origin}/api/ingest/sentry`
                : 'http://your-domain.com/api/ingest/sentry'}
            </pre>

            <p className="text-slate-300">
              <strong>2. In Sentry project settings:</strong>
            </p>
            <ul className="list-disc list-inside space-y-1 text-slate-400">
              <li>Go to Settings → Integrations → WebHooks</li>
              <li>Add the webhook URL above</li>
              <li>Enable "Issue" events</li>
              <li>Save the webhook configuration</li>
            </ul>

            <p className="text-slate-500 mt-3">
              📖 Learn more at{' '}
              <a
                href="https://docs.sentry.io/product/integrations/integration-platform/webhooks/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-emerald-400 hover:underline"
              >
                Sentry Webhook Docs
              </a>
            </p>
          </div>
        </div>
      )}

      {!selectedSource && (
        <p className="text-sm text-slate-500 text-center py-4 relative z-10">
          Select a source above to view setup instructions
        </p>
      )}
    </div>
  );
}
