'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import type { AgentJob, ClusterDetail, FeedbackSource, CodingPlan } from '@/types';
import FeedbackCard from '@/components/FeedbackCard';

/**
 * Client React component that renders details for a single cluster, its feedback items, and actions related to generating fixes.
 *
 * Displays loading and error states, the cluster summary (timestamps, source counts, GitHub links/branch, and any error message), a list of feedback items, and an action to start fix generation. While a cluster is in the "fixing" status the component polls the API for updates.
 *
 * @returns The rendered JSX element for the cluster detail page
 */
export default function ClusterDetailPage() {
  const params = useParams();
  const clusterId = params.id as string;

  const [cluster, setCluster] = useState<ClusterDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isFixing, setIsFixing] = useState(false);
  const [selectedRepo, setSelectedRepo] = useState<string | null>(null);
  const [codingPlan, setCodingPlan] = useState<CodingPlan | null>(null);
  const [isGeneratingPlan, setIsGeneratingPlan] = useState(false);
  const [fixJobs, setFixJobs] = useState<AgentJob[]>([]);
  const [jobsError, setJobsError] = useState<string | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [logText, setLogText] = useState<string>('');
  const [logCursor, setLogCursor] = useState(0);
  const [isTailingLogs, setIsTailingLogs] = useState(false);

  useEffect(() => {
    fetchCluster();
    fetchPlan();
    fetchFixJobs();
  }, [clusterId]);

  useEffect(() => {
    if (cluster?.status === 'fixing' && !isFixing) {
      // Poll for updates while fixing
      const interval = setInterval(fetchCluster, 3000);
      return () => clearInterval(interval);
    }
  }, [cluster?.status, isFixing]);

  useEffect(() => {
    const jobIsRunning = fixJobs.some((job) => job.status === 'running' || job.status === 'pending');
    if (!jobIsRunning) return;
    const interval = setInterval(fetchFixJobs, 5000);
    return () => clearInterval(interval);
  }, [fixJobs]);

  useEffect(() => {
    if (!selectedJobId || !isTailingLogs) return;
    const interval = setInterval(() => fetchJobLogs(selectedJobId, { append: true }), 2000);
    return () => clearInterval(interval);
  }, [selectedJobId, isTailingLogs, logCursor, fixJobs]);

  const fetchCluster = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`/api/clusters/${clusterId}`);
      if (!response.ok) {
        throw new Error('Failed to fetch cluster');
      }
      const data = await response.json();
      setCluster(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const fetchPlan = async () => {
    try {
      const response = await fetch(`/api/clusters/${clusterId}/plan`);
      if (response.ok) {
        const data = await response.json();
        setCodingPlan(data);
      } else {
        setCodingPlan(null);
      }
    } catch (err) {
      console.error('Failed to fetch plan:', err);
    }
  };

  const fetchFixJobs = async () => {
    try {
      setJobsError(null);
      const response = await fetch(`/api/clusters/${clusterId}/jobs`);
      if (!response.ok) {
        throw new Error('Failed to fetch fix jobs');
      }
      const data = (await response.json()) as AgentJob[];
      setFixJobs(Array.isArray(data) ? data : []);
    } catch (err) {
      setJobsError(err instanceof Error ? err.message : 'Failed to fetch fix jobs');
    }
  };

  const fetchJobLogs = async (jobId: string, opts?: { append?: boolean }) => {
    const append = opts?.append ?? false;
    const cursor = append ? logCursor : 0;
    const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/job-logs?cursor=${cursor}&limit=200`);
    if (!response.ok) {
      throw new Error('Failed to fetch logs');
    }
    const payload = await response.json();
    const chunks = (payload?.chunks as string[]) || [];
    const nextCursor = typeof payload?.next_cursor === 'number' ? payload.next_cursor : cursor + chunks.length;
    if (append) {
      setLogText((prev) => prev + chunks.join(''));
    } else {
      setLogText(chunks.join(''));
    }
    setLogCursor(nextCursor);
    setIsTailingLogs(Boolean(payload?.has_more) || fixJobs.some((j) => j.id === jobId && j.status === 'running'));
  };

  const handleGeneratePlan = async () => {
    try {
      setIsGeneratingPlan(true);
      const response = await fetch(`/api/clusters/${clusterId}/plan`, {
        method: 'POST'
      });
      if (!response.ok) throw new Error('Failed to generate plan');
      const data = await response.json();
      setCodingPlan(data);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Plan generation failed');
    } finally {
      setIsGeneratingPlan(false);
    }
  };

  const handleStartFix = async () => {
    try {
      setIsFixing(true);
      // Ensure plan exists first
      if (!codingPlan) {
        await handleGeneratePlan();
        // Fetch updated plan
        await fetchPlan();
      }

      const response = await fetch(`/api/clusters/${clusterId}/start_fix`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error('Failed to start fix');
      }
      await fetchCluster();
      await fetchFixJobs();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to start fix');
    } finally {
      setIsFixing(false);
    }
  };

  const getStatusBadgeClass = (status: ClusterDetail['status']) => {
    const baseClass = 'px-3 py-1 text-xs font-bold rounded-md uppercase tracking-wider border';
    switch (status) {
      case 'new':
        return `${baseClass} bg-blue-900/20 text-blue-400 border-blue-900/50`;
      case 'fixing':
        return `${baseClass} bg-yellow-900/20 text-yellow-400 border-yellow-900/50`;
      case 'pr_opened':
        return `${baseClass} bg-matrix-green-dim text-matrix-green border-matrix-green/30`;
      case 'failed':
        return `${baseClass} bg-red-900/20 text-red-400 border-red-900/50`;
      default:
        return `${baseClass} bg-gray-900/50 text-gray-400 border-gray-800`;
    }
  };

  const getSourceIcon = (source: FeedbackSource) => {
    switch (source) {
      case 'reddit':
        return '🗨️ Reddit';
      case 'github':
        return '🐙 GitHub';
      case 'manual':
        return '✍️ Manual';
    }
  };

  const canStartFix = cluster && ['new', 'failed'].includes(cluster.status);

  const statusLabel = (status: AgentJob['status']) => {
    switch (status) {
      case 'success':
        return 'success';
      case 'failed':
        return 'failed';
      case 'running':
        return 'running';
      default:
        return 'pending';
    }
  };

  if (loading && !cluster) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-center py-12">
          <div className="text-gray-500">Loading cluster details...</div>
        </div>
      </div>
    );
  }

  if (error || !cluster) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="rounded-md bg-red-50 p-4">
          <div className="flex">
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Error loading cluster</h3>
              <div className="mt-2 text-sm text-red-700">{error || 'Cluster not found'}</div>
              <div className="mt-4 flex gap-3">
                <button
                  onClick={fetchCluster}
                  className="text-sm font-medium text-red-800 hover:text-red-900"
                >
                  Try again
                </button>
                <Link href="/" className="text-sm font-medium text-red-800 hover:text-red-900">
                  Back to clusters
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Count by source
  const sourceCounts = cluster.feedback_items.reduce(
    (acc, item) => {
      acc[item.source] = (acc[item.source] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  // Count by repo
  const repoCounts = cluster.feedback_items.reduce(
    (acc, item) => {
      if (item.repo) {
        acc[item.repo] = (acc[item.repo] || 0) + 1;
      }
      return acc;
    },
    {} as Record<string, number>
  );

  // Filter feedback items by selected repo
  const filteredFeedbackItems = selectedRepo
    ? cluster.feedback_items.filter((item) => item.repo === selectedRepo)
    : cluster.feedback_items;

  // Count GitHub issues in the cluster
  const githubIssueCount = cluster.feedback_items.filter(
    (item) => item.source === 'github'
  ).length;

  return (
    <div className="min-h-screen bg-matrix-black pb-12 pt-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-6">
          <Link
            href="/clusters"
            className="text-sm font-medium text-gray-400 hover:text-matrix-green transition-colors flex items-center gap-1 uppercase tracking-wide"
          >
            ← Back to all clusters
          </Link>
        </div>

        <div className="bg-matrix-card shadow-lg rounded-2xl overflow-hidden border border-matrix-border mb-8">
          <div className="px-6 py-8 border-b border-matrix-border">
            <div className="flex justify-between items-start">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-4">
                  <h1 className="text-2xl font-bold text-white tracking-tight">
                    {cluster.issue_title || cluster.title || 'Untitled Cluster'}
                  </h1>
                  <span className={getStatusBadgeClass(cluster.status)}>
                    {cluster.status.replace('_', ' ')}
                  </span>
                </div>
                <p className="text-gray-400 text-lg leading-relaxed">
                  {cluster.issue_description || cluster.summary}
                </p>
                {cluster.issue_description && cluster.summary && cluster.issue_description !== cluster.summary && (
                  <p className="text-gray-500 text-sm leading-relaxed mt-3">
                    Cluster summary: {cluster.summary}
                  </p>
                )}
              </div>
              <div className="ml-6 flex flex-col gap-3">
                {cluster.github_pr_url && (
                  <a
                    href={cluster.github_pr_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center px-4 py-2 border border-matrix-border shadow-sm text-sm font-bold rounded-full text-white bg-matrix-black hover:bg-matrix-border focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-matrix-green transition-all uppercase tracking-wide"
                  >
                    View PR on GitHub
                  </a>
                )}
                {canStartFix && (
                  <button
                    onClick={handleStartFix}
                    disabled={isFixing}
                    className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-bold rounded-full shadow-neon-green text-black bg-matrix-green hover:bg-green-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-matrix-green disabled:opacity-50 disabled:cursor-not-allowed transition-all uppercase tracking-wide"
                  >
                    {isFixing ? 'Starting...' : 'Generate Fix'}
                  </button>
                )}
              </div>
            </div>

            <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-6 text-sm text-gray-500 font-mono border-t border-matrix-border pt-6">
              <div>
                <dt className="text-xs font-bold text-matrix-green uppercase tracking-wider mb-1">Created</dt>
                <dd className="text-gray-300">{new Date(cluster.created_at).toLocaleString()}</dd>
              </div>
              <div>
                <dt className="text-xs font-bold text-matrix-green uppercase tracking-wider mb-1">Last Updated</dt>
                <dd className="text-gray-300">{new Date(cluster.updated_at).toLocaleString()}</dd>
              </div>
              <div>
                <dt className="text-xs font-bold text-matrix-green uppercase tracking-wider mb-1">Sources</dt>
                <dd className="text-gray-300">
                  {Object.entries(sourceCounts).map(([source, count]) => (
                    <span key={source} className="mr-2">
                      {count} {source}
                    </span>
                  ))}
                </dd>
              </div>
              {cluster.github_repo_url && (
                <div>
                  <dt className="text-xs font-bold text-matrix-green uppercase tracking-wider mb-1">Target Repo</dt>
                  <dd>
                    <a
                      href={cluster.github_repo_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-emerald-400 hover:text-emerald-300 break-all"
                    >
                      {cluster.github_repo_url}
                    </a>
                  </dd>
                </div>
              )}
              {Object.keys(repoCounts).length > 0 && (
                <div>
                  <dt className="text-xs font-bold text-purple-400 uppercase tracking-wider mb-1">Repositories</dt>
                  <dd className="text-purple-300">
                    {Object.keys(repoCounts).length} {Object.keys(repoCounts).length === 1 ? 'repo' : 'repos'}
                  </dd>
                </div>
              )}
            </div>

            {Object.keys(repoCounts).length > 0 && (
              <div className="mt-4 pt-4 border-t border-matrix-border">
                <dt className="text-xs font-bold text-purple-400 uppercase tracking-wider mb-3">Repository Breakdown</dt>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(repoCounts).map(([repo, count]) => (
                    <button
                      key={repo}
                      onClick={() => setSelectedRepo(selectedRepo === repo ? null : repo)}
                      className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium transition-all ${selectedRepo === repo
                        ? 'border-purple-500/50 bg-purple-500/20 text-purple-200'
                        : 'border-purple-900/50 bg-purple-900/20 text-purple-300 hover:bg-purple-900/30'
                        }`}
                    >
                      <svg viewBox="0 0 16 16" fill="currentColor" className="w-4 h-4">
                        <path d="M2 2.5A2.5 2.5 0 014.5 0h8.75a.75.75 0 01.75.75v12.5a.75.75 0 01-.75.75h-2.5a.75.75 0 110-1.5h1.75v-2h-8a1 1 0 00-.714 1.7.75.75 0 01-1.072 1.05A2.495 2.495 0 012 11.5v-9zm10.5-1V9h-8c-.356 0-.694.074-1 .208V2.5a1 1 0 011-1h8zM5 12.25v3.25a.25.25 0 00.4.2l1.45-1.087a.25.25 0 01.3 0L8.6 15.7a.25.25 0 00.4-.2v-3.25a.25.25 0 00-.25-.25h-3.5a.25.25 0 00-.25.25z" />
                      </svg>
                      <span>{repo}</span>
                      <span className="ml-1 rounded-full bg-purple-500/30 px-2 py-0.5 text-[10px]">
                        {count}
                      </span>
                    </button>
                  ))}
                </div>
                {selectedRepo && (
                  <div className="mt-3 text-xs text-purple-300">
                    Showing {filteredFeedbackItems.length} {filteredFeedbackItems.length === 1 ? 'item' : 'items'} from <span className="font-semibold">{selectedRepo}</span>
                    <button
                      onClick={() => setSelectedRepo(null)}
                      className="ml-2 text-purple-400 hover:text-purple-200 underline"
                    >
                      Clear filter
                    </button>
                  </div>
                )}
              </div>
            )}

            {cluster.github_branch && (
              <div className="mt-4 pt-4 border-t border-matrix-border">
                <dt className="text-xs font-bold text-matrix-green uppercase tracking-wider mb-1">GitHub Branch</dt>
                <dd className="text-gray-300 font-mono">{cluster.github_branch}</dd>
              </div>
            )}

            {cluster.error_message && (
              <div className="mt-4 p-3 bg-red-900/20 rounded-md border border-red-900/50">
                <dt className="text-xs font-bold text-red-400 uppercase tracking-wider mb-1">Error</dt>
                <dd className="text-red-300 font-mono">{cluster.error_message}</dd>
              </div>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-medium tracking-tight text-slate-50 flex items-center gap-2">
                <span className="inline-block h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
                Live Feed
              </h2>
              <div className="flex gap-2">
                <span className="px-2 py-1 rounded-md bg-white/5 border border-white/10 text-[10px] text-slate-400">Real-time</span>
                <span className="px-2 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-[10px] text-emerald-400">Connected</span>
              </div>
            </div>

            <div className="space-y-4">
              {filteredFeedbackItems.map((item) => (
                <FeedbackCard key={item.id} item={item} />
              ))}
              {filteredFeedbackItems.length === 0 && (
                <div className="text-center py-12 rounded-3xl border border-white/10 bg-white/5 border-dashed">
                  <p className="text-slate-400">
                    {selectedRepo
                      ? `No feedback items found for ${selectedRepo}.`
                      : 'No feedback items found for this cluster.'}
                  </p>
                </div>
              )}
            </div>
          </div>

          <div className="space-y-6">
            {githubIssueCount > 0 && (
              <div className="animate-in delay-200 rounded-3xl border border-purple-900/50 bg-gradient-to-br from-purple-900/20 to-purple-900/5 p-6 backdrop-blur-md">
                <div className="flex items-center gap-2 mb-4">
                  <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 text-purple-400">
                    <path
                      fillRule="evenodd"
                      d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
                      clipRule="evenodd"
                    />
                  </svg>
                  <h3 className="text-sm font-medium text-purple-300 uppercase tracking-wider">GitHub Issues ({githubIssueCount})</h3>
                </div>
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {cluster.feedback_items
                    .filter((item) => item.source === 'github')
                    .map((item) => (
                      <a
                        key={item.id}
                        href={item.github_issue_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block p-3 rounded-xl bg-purple-900/20 border border-purple-900/30 hover:bg-purple-900/30 hover:border-purple-500/50 transition-all group"
                      >
                        <div className="flex items-start gap-2">
                          <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] ${item.status === 'open'
                            ? 'bg-green-500/20 text-green-400'
                            : 'bg-gray-500/20 text-gray-400'
                            }`}>
                            {item.status === 'open' ? '●' : '✓'}
                          </span>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              {item.repo && (
                                <span className="text-[10px] text-purple-400 font-medium">{item.repo}</span>
                              )}
                              {item.github_issue_number && (
                                <span className="text-[10px] text-purple-300">#{item.github_issue_number}</span>
                              )}
                            </div>
                            <p className="text-xs text-slate-200 line-clamp-2 group-hover:text-purple-200">
                              {item.title}
                            </p>
                          </div>
                          <svg
                            viewBox="0 0 20 20"
                            fill="currentColor"
                            className="w-3 h-3 text-purple-400 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
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
                        </div>
                      </a>
                    ))}
                </div>
              </div>
            )}

            <div className="animate-in delay-300 rounded-3xl border border-white/10 bg-black/40 p-6 backdrop-blur-md">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider">Implementation Plan</h3>
                {codingPlan && (
                  <button
                    onClick={handleGeneratePlan}
                    disabled={isGeneratingPlan || isFixing}
                    className="text-xs text-matrix-green hover:underline"
                  >
                    {isGeneratingPlan ? 'Regenerating...' : 'Regenerate'}
                  </button>
                )}
              </div>

              {codingPlan ? (
                <div className="space-y-4">
                  <div className="p-4 rounded-2xl bg-white/5 border border-white/10">
                    <h4 className="text-sm font-bold text-slate-200 mb-2">{codingPlan.title}</h4>
                    <p className="text-xs text-slate-400 mb-4">{codingPlan.description}</p>
                  </div>

                  {canStartFix && (
                    <button
                      onClick={handleStartFix}
                      disabled={isFixing}
                      className={`w-full py-3 rounded-xl border text-sm font-medium transition-colors ${isFixing
                        ? 'bg-matrix-green/20 border-matrix-green text-matrix-green cursor-wait'
                        : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400 hover:bg-emerald-500/20'
                        }`}
                    >
                      {isFixing ? 'Starting Agent...' : 'Start Automated Fix'}
                    </button>
                  )}
                </div>
              ) : (
                <div className="text-center py-8">
                  <p className="text-sm text-slate-500 mb-4">No plan generated yet.</p>
                  <button
                    onClick={handleGeneratePlan}
                    disabled={isGeneratingPlan}
                    className="px-4 py-2 rounded-full bg-purple-600 text-white text-xs font-bold hover:bg-purple-500 disabled:opacity-50"
                  >
                    {isGeneratingPlan ? 'Generating...' : 'Generate Plan'}
                  </button>
                </div>
              )}
            </div>

            <div className="mt-6 rounded-3xl border border-white/10 bg-black/40 p-6 backdrop-blur-md">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider">Fix Jobs</h3>
                <button
                  onClick={fetchFixJobs}
                  className="text-xs text-matrix-green hover:underline"
                >
                  Refresh
                </button>
              </div>

              {jobsError && (
                <div className="text-xs text-red-400 mb-3">{jobsError}</div>
              )}

              {fixJobs.length === 0 ? (
                <div className="text-sm text-slate-500">No fix jobs yet. Click “Start Automated Fix” to create one.</div>
              ) : (
                <div className="grid gap-3">
                  {fixJobs.map((job) => (
                    <div key={job.id} className="rounded-2xl border border-white/10 bg-black/30 p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-mono text-slate-400">{job.id.slice(0, 8)}</span>
                            <span className="text-[10px] uppercase tracking-wider text-slate-500">
                              {new Date(job.created_at).toLocaleString()}
                            </span>
                            <span className="text-[10px] uppercase tracking-wider text-slate-300">
                              {statusLabel(job.status)}
                            </span>
                          </div>
                          {job.pr_url && (
                            <a
                              href={job.pr_url}
                              target="_blank"
                              rel="noreferrer"
                              className="mt-2 inline-flex text-xs text-emerald-400 hover:underline break-all"
                            >
                              View PR
                            </a>
                          )}
                        </div>
                        <div className="shrink-0 flex gap-2">
                          <button
                            onClick={async () => {
                              setSelectedJobId(selectedJobId === job.id ? null : job.id);
                              setLogCursor(0);
                              setLogText('');
                              if (selectedJobId !== job.id) {
                                try {
                                  await fetchJobLogs(job.id, { append: false });
                                } catch (err) {
                                  alert(err instanceof Error ? err.message : 'Failed to fetch logs');
                                }
                              } else {
                                setIsTailingLogs(false);
                              }
                            }}
                            className="text-xs rounded-lg border border-white/10 px-3 py-2 bg-black/20 hover:bg-black/40 transition-colors text-slate-200"
                          >
                            {selectedJobId === job.id ? 'Hide logs' : 'View logs'}
                          </button>
                        </div>
                      </div>

                      {selectedJobId === job.id && (
                        <div className="mt-3">
                          <div className="flex items-center justify-between mb-2">
                            <div className="text-[10px] uppercase tracking-wider text-slate-500">
                              {isTailingLogs ? 'Tailing…' : 'Logs'}
                            </div>
                            <div className="flex gap-2">
                              <button
                                onClick={async () => {
                                  try {
                                    await fetchJobLogs(job.id, { append: true });
                                  } catch (err) {
                                    alert(err instanceof Error ? err.message : 'Failed to fetch logs');
                                  }
                                }}
                                className="text-[10px] text-matrix-green hover:underline"
                              >
                                Load more
                              </button>
                              <button
                                onClick={() => setIsTailingLogs((v) => !v)}
                                className="text-[10px] text-slate-300 hover:underline"
                              >
                                {isTailingLogs ? 'Pause' : 'Tail'}
                              </button>
                            </div>
                          </div>
                          <pre className="bg-black/50 rounded-lg p-4 font-mono text-xs text-slate-300 overflow-x-auto max-h-96 whitespace-pre-wrap border border-white/5">
                            {logText || 'No logs yet.'}
                          </pre>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
