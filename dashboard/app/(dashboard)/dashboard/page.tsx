'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useSession } from 'next-auth/react';
import type { StatsResponse, AgentJob } from '@/types';

export default function DashboardOverview() {
  const { data: session } = useSession();
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [prCount, setPrCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, jobsRes] = await Promise.all([
          fetch('/api/stats'),
          fetch('/api/jobs'),
        ]);

        if (statsRes.ok) {
          const data = await statsRes.json();
          setStats(data);
        }

        if (jobsRes.ok) {
          const jobs: AgentJob[] = await jobsRes.json();
          const prsWithUrl = jobs.filter((j) => j.pr_url).length;
          setPrCount(prsWithUrl);
        }
      } catch (error) {
        console.error('Error fetching data:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Welcome Section */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white tracking-tight">
          Welcome back{session?.user?.name ? `, ${session.user.name.split(' ')[0]}` : ''}
        </h1>
        <p className="mt-2 text-slate-400">
          Monitor your feedback clusters and manage automated fixes.
        </p>
      </div>

      {/* Action Cards with Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Link
          href="/dashboard/clusters"
          className="overflow-hidden hover-card-effect group bg-gradient-to-br from-emerald-500/10 via-emerald-500/5 to-transparent rounded-2xl p-6 relative border border-white/10 hover:border-emerald-500/30 transition-all"
        >
          <div className="pointer-events-none group-hover:opacity-60 transition-opacity duration-500 opacity-40 absolute inset-0">
            <div className="absolute -left-12 top-5 h-32 w-32 rounded-full bg-emerald-500/20 blur-3xl"></div>
          </div>
          <div className="relative">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-emerald-500/10 rounded-xl flex items-center justify-center group-hover:bg-emerald-500/20 transition-colors border border-emerald-500/20">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="text-emerald-400"
                >
                  <circle cx="12" cy="12" r="3" />
                  <path d="M12 2v4m0 12v4M2 12h4m12 0h4" />
                  <path d="m4.93 4.93 2.83 2.83m8.48 8.48 2.83 2.83M4.93 19.07l2.83-2.83m8.48-8.48 2.83-2.83" />
                </svg>
              </div>
              <div className="text-right">
                <p className="text-3xl font-medium tracking-tight text-slate-50 tabular-nums">
                  {loading ? '...' : stats?.total_clusters || 0}
                </p>
                <p className="text-xs text-emerald-300/70 uppercase tracking-wide">clusters</p>
              </div>
            </div>
            <h3 className="text-lg font-semibold text-white group-hover:text-emerald-400 transition-colors">
              View Clusters
            </h3>
            <p className="mt-1 text-sm text-slate-400">
              Browse issue clusters and generate fixes
            </p>
          </div>
        </Link>

        <Link
          href="/dashboard/feedback"
          className="overflow-hidden hover-card-effect group bg-gradient-to-br from-blue-500/10 via-blue-500/5 to-transparent rounded-2xl p-6 relative border border-white/10 hover:border-blue-500/30 transition-all"
        >
          <div className="pointer-events-none group-hover:opacity-60 transition-opacity duration-500 opacity-40 absolute inset-0">
            <div className="absolute -right-12 top-5 h-32 w-32 rounded-full bg-blue-500/20 blur-3xl"></div>
          </div>
          <div className="relative">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-blue-500/10 rounded-xl flex items-center justify-center group-hover:bg-blue-500/20 transition-colors border border-blue-500/20">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="text-blue-400"
                >
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
              </div>
              <div className="text-right">
                <p className="text-3xl font-medium tracking-tight text-slate-50 tabular-nums">
                  {loading ? '...' : stats?.total_feedback || 0}
                </p>
                <p className="text-xs text-blue-300/70 uppercase tracking-wide">feedback</p>
              </div>
            </div>
            <h3 className="text-lg font-semibold text-white group-hover:text-blue-400 transition-colors">
              Manage Feedback
            </h3>
            <p className="mt-1 text-sm text-slate-400">
              View and add feedback sources
            </p>
          </div>
        </Link>

        <Link
          href="/dashboard/prs"
          className="overflow-hidden hover-card-effect group bg-gradient-to-br from-purple-500/10 via-purple-500/5 to-transparent rounded-2xl p-6 relative border border-white/10 hover:border-purple-500/30 transition-all"
        >
          <div className="pointer-events-none group-hover:opacity-60 transition-opacity duration-500 opacity-40 absolute inset-0">
            <div className="absolute -left-12 bottom-5 h-32 w-32 rounded-full bg-purple-500/20 blur-3xl"></div>
          </div>
          <div className="relative">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-purple-500/10 rounded-xl flex items-center justify-center group-hover:bg-purple-500/20 transition-colors border border-purple-500/20">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="text-purple-400"
                >
                  <circle cx="18" cy="18" r="3" />
                  <circle cx="6" cy="6" r="3" />
                  <path d="M6 21V9a9 9 0 0 0 9 9" />
                </svg>
              </div>
              <div className="text-right">
                <p className="text-3xl font-medium tracking-tight text-slate-50 tabular-nums">
                  {loading ? '...' : prCount}
                </p>
                <p className="text-xs text-purple-300/70 uppercase tracking-wide">PRs</p>
              </div>
            </div>
            <h3 className="text-lg font-semibold text-white group-hover:text-purple-400 transition-colors">
              Pull Requests
            </h3>
            <p className="mt-1 text-sm text-slate-400">
              Track agent jobs and PRs
            </p>
          </div>
        </Link>
      </div>
    </div>
  );
}
