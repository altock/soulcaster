'use client';

import { useEffect, useState } from 'react';
import type { GitHubRepo } from '@/types';
import IntegrationsDirectory, { type IntegrationId } from '@/components/integrations/IntegrationsDirectory';
import RequestIntegrationDialog from '@/components/integrations/RequestIntegrationDialog';
import SearchInput from '@/components/ui/SearchInput';

type SourceType = 'reddit' | 'github' | IntegrationId;

/**
 * Render the administration panel for configuring Reddit subreddits and GitHub repositories.
 *
 * Loads configured subreddits and repositories on mount and provides actions to add, remove, and persist subreddits; add and remove GitHub repos; trigger per-repo or all-repo syncs; and trigger the Reddit poller.
 *
 * @returns The JSX element for the SourceConfig administration panel.
 */
export default function SourceConfig() {
  const [selectedSource, setSelectedSource] = useState<SourceType | null>(null);
  const [sourceQuery, setSourceQuery] = useState('');

  // Reddit state
  const [subreddits, setSubreddits] = useState<string[]>([]);
  const [newSubreddit, setNewSubreddit] = useState('');
  const [loadingSubs, setLoadingSubs] = useState(false);
  const [savingSubs, setSavingSubs] = useState(false);
  const [subsMessage, setSubsMessage] = useState<string | null>(null);
  const [subsError, setSubsError] = useState<string | null>(null);

  // GitHub state
  const [repos, setRepos] = useState<GitHubRepo[]>([]);
  const [newRepo, setNewRepo] = useState('');
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [addingRepo, setAddingRepo] = useState(false);
  const [syncingRepo, setSyncingRepo] = useState<string | null>(null);
  const [repoMessage, setRepoMessage] = useState<string | null>(null);
  const [repoError, setRepoError] = useState<string | null>(null);

  useEffect(() => {
    loadSubreddits();
    loadRepos();
  }, []);

  const loadSubreddits = async () => {
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

  const loadRepos = async () => {
    setLoadingRepos(true);
    setRepoError(null);
    try {
      const res = await fetch('/api/config/github/repos', { cache: 'no-store' });
      const data = await res.json();
      setRepos(data.repos ?? []);
    } catch (err) {
      setRepoError('Failed to load GitHub repos');
    } finally {
      setLoadingRepos(false);
    }
  };

  const sources = [
    {
      type: 'reddit' as const,
      icon: '🗨️',
      title: 'Reddit Integration',
      description: 'Monitor subreddits (JSON polling, no OAuth)',
      enabled: false,
    },
    {
      type: 'github' as const,
      icon: '⚙️',
      title: 'GitHub Issues',
      description: 'Sync open-source repository issues automatically',
      enabled: true,
    },
    {
      type: 'sentry' as const,
      icon: '⚠️',
      title: 'Sentry',
      description: 'Capture errors and performance issues',
      enabled: false,
    },
    {
      type: 'splunk' as const,
      icon: '🔍',
      title: 'Splunk',
      description: 'Monitor logs and trigger alerts via webhook',
      enabled: false,
    },
    {
      type: 'datadog' as const,
      icon: '🐕',
      title: 'Datadog',
      description: 'Receive monitor alerts and metrics',
      enabled: false,
    },
    {
      type: 'posthog' as const,
      icon: '📊',
      title: 'PostHog',
      description: 'Track product analytics events',
      enabled: false,
    },
  ];

  const integrationIds: IntegrationId[] = ['sentry', 'splunk', 'datadog', 'posthog'];
  const selectedIntegration =
    selectedSource && integrationIds.includes(selectedSource as IntegrationId)
      ? (selectedSource as IntegrationId)
      : null;
  const selectedIntegrationMeta = selectedIntegration
    ? sources.find((source) => source.type === selectedIntegration)
    : null;

  const normalizedSourceQuery = sourceQuery.trim().toLowerCase();
  const matchedSources = normalizedSourceQuery
    ? sources.filter((source) => {
        const haystack = `${source.title} ${source.description} ${source.type}`.toLowerCase();
        return haystack.includes(normalizedSourceQuery);
      })
    : sources;

  const selectedSourceItem = selectedSource ? sources.find((source) => source.type === selectedSource) : null;
  const visibleSources =
    selectedSourceItem && !matchedSources.some((source) => source.type === selectedSourceItem.type)
      ? [selectedSourceItem, ...matchedSources]
      : matchedSources;

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

  const addRepo = async () => {
    const repoString = newRepo.trim();
    if (!repoString) return;

    setAddingRepo(true);
    setRepoMessage(null);
    setRepoError(null);
    try {
      const res = await fetch('/api/config/github/repos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo: repoString }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.error || data?.detail || 'Failed to add repo');
      }
      setNewRepo('');
      await loadRepos();
      setRepoMessage(`Added ${data.repo.full_name}`);
    } catch (err: any) {
      setRepoError(err?.message || 'Failed to add repository');
    } finally {
      setAddingRepo(false);
    }
  };

  const removeRepo = async (fullName: string) => {
    setRepoMessage(null);
    setRepoError(null);
    try {
      const res = await fetch(`/api/config/github/repos/${encodeURIComponent(fullName)}`, {
        method: 'DELETE',
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data?.error || 'Failed to remove repo');
      }
      await loadRepos();
      setRepoMessage(`Removed ${fullName}`);
    } catch (err: any) {
      setRepoError(err?.message || 'Failed to remove repository');
    }
  };

  const syncRepo = async (fullName: string) => {
    setSyncingRepo(fullName);
    setRepoMessage(null);
    setRepoError(null);
    try {
      const res = await fetch(`/api/ingest/github/sync/${encodeURIComponent(fullName)}`, {
        method: 'POST',
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.error || data?.detail || 'Failed to sync repo');
      }
      await loadRepos();
      const ignoredCount = data.ignored_prs ?? 0;
      setRepoMessage(
        `Synced ${fullName}: ${data.new_issues} new, ${data.updated_issues} updated, ${data.closed_issues} closed` +
        (ignoredCount > 0 ? ` (${ignoredCount} PRs ignored)` : '')
      );
    } catch (err: any) {
      setRepoError(err?.message || 'Failed to sync repository');
    } finally {
      setSyncingRepo(null);
    }
  };

  const syncAllRepos = async () => {
    setSyncingRepo('all');
    setRepoMessage(null);
    setRepoError(null);
    try {
      const res = await fetch('/api/ingest/github/sync', {
        method: 'POST',
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.error || data?.detail || 'Failed to sync repos');
      }
      await loadRepos();
      const totalIgnored = (data.repos ?? []).reduce((sum: number, repo: any) => sum + (repo.ignored_prs ?? 0), 0);
      setRepoMessage(
        `Synced all repos: ${data.total_new} new, ${data.total_updated} updated, ${data.total_closed} closed` +
        (totalIgnored > 0 ? ` (${totalIgnored} PRs ignored)` : '')
      );
    } catch (err: any) {
      setRepoError(err?.message || 'Failed to sync repositories');
    } finally {
      setSyncingRepo(null);
    }
  };

  return (
    <div className="bg-emerald-950/20 border border-white/10 backdrop-blur-sm rounded-3xl p-6 relative overflow-hidden mt-6">
      <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 via-transparent to-transparent pointer-events-none" />
      <h3 className="text-lg font-semibold text-white mb-4 relative z-10">Configure Feedback Sources</h3>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4 relative z-10">
        <SearchInput
          value={sourceQuery}
          onChange={setSourceQuery}
          placeholder="Search sources…"
          className="flex-1"
        />
        <RequestIntegrationDialog
          requestHref="mailto:support@soulcaster.dev?subject=Integration%20%2F%20Source%20Request"
          triggerTitle="Request a new integration/source"
          triggerClassName="inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-200 hover:bg-white/10 hover:text-white transition-colors"
        >
          Add new integration/source
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 5v14" />
            <path d="M5 12h14" />
          </svg>
        </RequestIntegrationDialog>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4 relative z-10">
        {visibleSources.map((source) => {
          const isSelected = selectedSource === source.type;
          return (
            <button
              key={source.type}
              type="button"
              disabled={!source.enabled}
              onClick={() => {
                if (source.enabled) setSelectedSource(source.type);
              }}
              className={`p-4 border-2 rounded-2xl text-left transition-all ${isSelected
                ? 'border-emerald-500 bg-emerald-500/10 shadow-[0_0_20px_rgba(16,185,129,0.1)]'
                : 'border-white/5 bg-black/20 hover:border-white/10 hover:bg-black/30'
                } ${!source.enabled ? 'opacity-50 cursor-not-allowed hover:border-white/5 hover:bg-black/20' : ''}`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="text-2xl">{source.icon}</div>
                {!source.enabled && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/10 text-slate-300 border border-white/10">
                    Coming soon
                  </span>
                )}
              </div>
              <h4 className={`mt-1 font-semibold ${isSelected ? 'text-emerald-300' : 'text-slate-200'}`}>
                {source.title}
              </h4>
              <p className="text-sm text-slate-400 mt-1">{source.description}</p>
            </button>
          );
        })}
      </div>

      {visibleSources.length === 0 && (
        <div className="rounded-2xl border border-white/10 bg-white/5 p-6 text-center relative z-10">
          <p className="text-sm text-slate-300">No sources match “{sourceQuery}”.</p>
        </div>
      )}

      {selectedSource === 'reddit' && sources.find((s) => s.type === 'reddit')?.enabled && (
        <div className="border-t border-white/10 pt-4 space-y-4 relative z-10">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h4 className="font-semibold text-slate-200">Reddit Poller</h4>
              <p className="text-sm text-slate-400">
                Automatically monitors these subreddits for new posts using Reddit&apos;s public feeds.
              </p>
            </div>
            <span className="text-xs font-medium text-slate-500">
              Checks each subreddit once per second
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
                    const res = await fetch('/api/admin/trigger-poll', {
                      method: 'POST',
                    });
                    const data = await res.json();
                    if (res.ok) {
                      alert(`Poll triggered: ${data.message}`);
                    } else {
                      alert(`Failed to trigger poll: ${data.detail || data.error || 'Unknown error'}`);
                    }
                  } catch (err) {
                    alert('Failed to start Reddit polling. Please try again.');
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

      {selectedSource === 'github' && (
        <div className="border-t border-white/10 pt-4 space-y-4 relative z-10">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h4 className="font-semibold text-slate-200">GitHub Repository Issues</h4>
              <p className="text-sm text-slate-400">
                Sync open & closed issues from public GitHub repos. Uses GitHub API with your session token for higher rate limits.
              </p>
            </div>
          </div>

          <div className="bg-black/20 border border-white/5 p-4 rounded-xl space-y-3">
            <div className="flex items-center gap-2 flex-wrap">
              <input
                type="text"
                placeholder="owner/repo or GitHub URL"
                value={newRepo}
                onChange={(e) => setNewRepo(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === 'Enter') addRepo();
                }}
                className="flex-1 min-w-[200px] rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
              />
              <button
                type="button"
                onClick={addRepo}
                disabled={addingRepo || !newRepo.trim()}
                className={`px-3 py-2 text-sm font-semibold rounded-lg transition-colors ${
                  addingRepo || !newRepo.trim()
                    ? 'bg-white/5 text-slate-500 cursor-not-allowed'
                    : 'text-black bg-emerald-500 hover:bg-emerald-400'
                }`}
              >
                {addingRepo ? 'Adding…' : 'Add Repo'}
              </button>
              <button
                type="button"
                onClick={syncAllRepos}
                disabled={syncingRepo === 'all' || repos.length === 0}
                className={`px-3 py-2 text-sm font-semibold rounded-lg transition-colors ${
                  syncingRepo === 'all' || repos.length === 0
                    ? 'bg-white/5 text-slate-500 cursor-not-allowed'
                    : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/30'
                }`}
              >
                {syncingRepo === 'all' ? '⏳ Syncing All…' : '🔄 Sync All'}
              </button>
            </div>

            {loadingRepos ? (
              <p className="text-sm text-slate-500">Loading repositories…</p>
            ) : (
              <div className="space-y-2">
                {repos.length === 0 && (
                  <span className="text-sm text-slate-500">No repositories configured yet.</span>
                )}
                {repos.map((repo) => (
                  <div
                    key={repo.full_name}
                    className="flex items-center justify-between gap-3 bg-white/5 border border-white/10 rounded-lg px-3 py-2"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <a
                          href={`https://github.com/${repo.full_name}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm font-medium text-slate-200 hover:text-emerald-300 transition-colors truncate"
                        >
                          {repo.full_name}
                        </a>
                        {(repo.issue_count || 0) > 0 && (
                          <span className="text-xs text-slate-500">
                            ({repo.issue_count || 0} issues)
                          </span>
                        )}
                      </div>
                      {repo.last_synced && (
                        <p className="text-xs text-slate-500">
                          Last synced: {new Date(repo.last_synced).toLocaleString()}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => syncRepo(repo.full_name)}
                        disabled={syncingRepo === repo.full_name}
                        className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
                          syncingRepo === repo.full_name
                            ? 'bg-white/5 text-slate-500 cursor-not-allowed'
                            : 'text-emerald-300 hover:bg-emerald-500/10'
                        }`}
                        title="Sync this repo"
                      >
                        {syncingRepo === repo.full_name ? '⏳' : '🔄'}
                      </button>
                      <button
                        type="button"
                        onClick={() => removeRepo(repo.full_name)}
                        className="text-slate-500 hover:text-rose-400 transition-colors text-xs"
                        title="Remove repo"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {repoMessage && <p className="text-sm text-emerald-400">{repoMessage}</p>}
            {repoError && <p className="text-sm text-rose-400">{repoError}</p>}
          </div>
        </div>
      )}

      {selectedIntegration && (
        <div className="border-t border-white/10 pt-4 space-y-4 relative z-10">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h4 className="font-semibold text-slate-200">{selectedIntegrationMeta?.title ?? 'Integration'}</h4>
              <p className="text-sm text-slate-400">
                {selectedIntegrationMeta?.description ??
                  'Connect third-party tools to automatically ingest feedback via webhooks.'}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <a
                href="/settings/integrations"
                className="text-xs font-medium text-emerald-300 hover:text-emerald-200 transition-colors"
                title="Open full-page integrations directory"
              >
                Open all →
              </a>
              <RequestIntegrationDialog
                requestHref="mailto:support@soulcaster.dev?subject=Integration%20Request"
                defaultName={selectedIntegrationMeta?.title ?? ''}
                triggerTitle="Request a new integration"
                triggerClassName="text-xs font-medium text-slate-400 hover:text-slate-200 transition-colors"
              >
                Request →
              </RequestIntegrationDialog>
            </div>
          </div>

          <IntegrationsDirectory
            integrationIds={[selectedIntegration]}
            pageSize={1}
            showSearch={false}
            showMeta={false}
            showPagination={false}
            showRequestButton={false}
          />
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
