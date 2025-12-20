'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import type { AgentJob, ClusterDetail, CodingPlan } from '@/types';
import {
  ClusterHeader,
  ClusterActionBar,
  ClusterTabs,
  ReviewTab,
  PlanTab,
  JobsTab,
  LogDrawer,
  type TabId,
} from './components';

export default function ClusterDetailPage() {
  const params = useParams();
  const clusterId = params.id as string;

  // Cluster data state
  const [cluster, setCluster] = useState<ClusterDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Action states
  const [isFixing, setIsFixing] = useState(false);
  const [isGeneratingPlan, setIsGeneratingPlan] = useState(false);

  // Filter state
  const [selectedRepo, setSelectedRepo] = useState<string | null>(null);

  // Plan state
  const [codingPlan, setCodingPlan] = useState<CodingPlan | null>(null);

  // Jobs state
  const [fixJobs, setFixJobs] = useState<AgentJob[]>([]);
  const [jobsError, setJobsError] = useState<string | null>(null);

  // Tab state
  const [activeTab, setActiveTab] = useState<TabId>('review');

  // Log drawer state
  const [logDrawerOpen, setLogDrawerOpen] = useState(false);
  const [selectedJobForLogs, setSelectedJobForLogs] = useState<AgentJob | null>(null);
  const [logText, setLogText] = useState<string>('');
  const [isTailingLogs, setIsTailingLogs] = useState(false);

  // Fetch functions (defined before effects that use them)
  const fetchCluster = useCallback(async () => {
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
  }, [clusterId]);

  const fetchPlan = useCallback(async () => {
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
  }, [clusterId]);

  const fetchFixJobs = useCallback(async () => {
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
  }, [clusterId]);

  const fetchJobLogs = useCallback(
    async (jobId: string) => {
      const response = await fetch(
        `/api/jobs/${encodeURIComponent(jobId)}/job-logs`
      );
      if (!response.ok) {
        throw new Error('Failed to fetch logs');
      }

      const payload = await response.json();
      const chunks = (payload?.chunks as string[]) || [];
      const source = payload?.source || 'unknown';

      // Update logs
      setLogText(chunks.join(''));

      // For Blob source (completed jobs), stop tailing
      if (source === 'blob') {
        setIsTailingLogs(false);
      }
      // For memory source, keep current tailing state (controlled by job status polling)
    },
    []
  );

  // Initial data fetch
  useEffect(() => {
    fetchCluster();
    fetchPlan();
    fetchFixJobs();
  }, [fetchCluster, fetchPlan, fetchFixJobs]);

  // Poll cluster status when fixing
  useEffect(() => {
    if (cluster?.status === 'fixing' && !isFixing) {
      const interval = setInterval(fetchCluster, 3000);
      return () => clearInterval(interval);
    }
  }, [cluster?.status, isFixing, fetchCluster]);

  // Poll jobs when running
  useEffect(() => {
    const jobIsRunning = fixJobs.some(
      (job) => job.status === 'running' || job.status === 'pending'
    );
    if (!jobIsRunning) return;
    const interval = setInterval(fetchFixJobs, 5000);
    return () => clearInterval(interval);
  }, [fixJobs, fetchFixJobs]);

  // Poll logs when tailing
  useEffect(() => {
    if (!selectedJobForLogs?.id || !isTailingLogs) return;
    const interval = setInterval(
      () => fetchJobLogs(selectedJobForLogs.id),
      2000
    );
    return () => clearInterval(interval);
  }, [selectedJobForLogs?.id, isTailingLogs, fetchJobLogs]);

  const handleGeneratePlan = async () => {
    try {
      setIsGeneratingPlan(true);
      const response = await fetch(`/api/clusters/${clusterId}/plan`, {
        method: 'POST',
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
      if (!codingPlan) {
        await handleGeneratePlan();
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
      // Switch to jobs tab to show progress
      setActiveTab('jobs');
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to start fix');
    } finally {
      setIsFixing(false);
    }
  };

  const handleViewLogs = async (job: AgentJob) => {
    setSelectedJobForLogs(job);
    setLogText('');
    setLogDrawerOpen(true);
    try {
      await fetchJobLogs(job.id);
    } catch (err) {
      console.error('Failed to fetch logs:', err);
    }
  };

  const handleCloseLogDrawer = () => {
    setLogDrawerOpen(false);
    setIsTailingLogs(false);
  };

  // Derived state
  const canStartFix = cluster && ['new', 'failed'].includes(cluster.status);
  const filteredFeedbackItems = selectedRepo
    ? cluster?.feedback_items.filter((item) => item.repo === selectedRepo) ?? []
    : cluster?.feedback_items ?? [];
  const hasRunningJob = fixJobs.some((job) => job.status === 'running');

  // Loading state
  if (loading && !cluster) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-center py-12">
          <div className="flex items-center gap-3 text-slate-400">
            <svg
              className="animate-spin h-5 w-5"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            Loading cluster details...
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !cluster) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="rounded-2xl bg-rose-500/10 border border-rose-500/20 p-6">
          <h3 className="text-sm font-medium text-rose-400">
            Error loading cluster
          </h3>
          <div className="mt-2 text-sm text-rose-300">
            {error || 'Cluster not found'}
          </div>
          <div className="mt-4 flex gap-3">
            <button
              onClick={fetchCluster}
              className="text-sm font-medium text-rose-400 hover:text-rose-300 transition-colors"
            >
              Try again
            </button>
            <Link
              href="/dashboard/clusters"
              className="text-sm font-medium text-rose-400 hover:text-rose-300 transition-colors"
            >
              Back to clusters
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#050505] pb-12 pt-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Back link */}
        <div className="mb-6">
          <Link
            href="/dashboard/clusters"
            className="text-sm font-medium text-slate-400 hover:text-emerald-400 transition-colors flex items-center gap-1"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 19l-7-7 7-7"
              />
            </svg>
            Back to clusters
          </Link>
        </div>

        {/* Header with cluster info */}
        <ClusterHeader
          cluster={cluster}
          selectedRepo={selectedRepo}
          onRepoSelect={setSelectedRepo}
        />

        {/* Action bar */}
        <ClusterActionBar
          cluster={cluster}
          codingPlan={codingPlan}
          isFixing={isFixing}
          isGeneratingPlan={isGeneratingPlan}
          onGeneratePlan={handleGeneratePlan}
          onStartFix={handleStartFix}
        />

        {/* Tabs */}
        <div className="mt-8">
          <ClusterTabs
            activeTab={activeTab}
            onTabChange={setActiveTab}
            jobCount={fixJobs.length}
            hasRunningJob={hasRunningJob}
          />

          {/* Tab content */}
          {activeTab === 'review' && (
            <ReviewTab
              feedbackItems={filteredFeedbackItems}
              allItems={cluster.feedback_items}
            />
          )}

          {activeTab === 'plan' && (
            <PlanTab
              codingPlan={codingPlan}
              canStartFix={canStartFix ?? false}
              isFixing={isFixing}
              isGeneratingPlan={isGeneratingPlan}
              onGeneratePlan={handleGeneratePlan}
              onStartFix={handleStartFix}
            />
          )}

          {activeTab === 'jobs' && (
            <JobsTab
              jobs={fixJobs}
              jobsError={jobsError}
              onRefresh={fetchFixJobs}
              onViewLogs={handleViewLogs}
            />
          )}
        </div>
      </div>

      {/* Log drawer */}
      <LogDrawer
        isOpen={logDrawerOpen}
        onClose={handleCloseLogDrawer}
        job={selectedJobForLogs}
        logText={logText}
        isTailing={isTailingLogs}
        onToggleTail={() => setIsTailingLogs((v) => !v)}
        onLoadMore={() => {
          if (selectedJobForLogs) {
            fetchJobLogs(selectedJobForLogs.id).catch(console.error);
          }
        }}
      />
    </div>
  );
}
