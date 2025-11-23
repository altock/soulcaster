'use client';

import { useEffect, useState } from 'react';
import type { StatsResponse } from '@/types';

export default function StatsCards() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/stats');
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Error fetching stats:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-2 gap-x-6 gap-y-6 w-full">
      {/* Card 1: Treasury Overview Style */}
      <section className="animate-in delay-200 overflow-hidden sm:p-8 hover-card-effect group bg-gradient-to-br from-emerald-500/15 via-emerald-500/5 to-transparent rounded-3xl pt-6 pr-6 pb-6 pl-6 relative shadow-[0_0_60px_rgba(16,185,129,0.15)] border border-white/10">
        <div className="pointer-events-none group-hover:opacity-60 transition-opacity duration-500 opacity-40 absolute top-0 right-0 bottom-0 left-0">
          <div className="absolute -left-24 top-10 h-64 w-64 rounded-full bg-emerald-500/25 blur-3xl animate-pulse"></div>
          <div className="absolute right-0 -bottom-10 h-52 w-52 rounded-full bg-emerald-400/20 blur-3xl"></div>
        </div>

        <div className="relative flex flex-col gap-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-normal uppercase tracking-[0.12em] text-emerald-300/70">
                Total Clusters
              </p>
              <div className="mt-2 flex items-end gap-3">
                <p className="text-4xl font-medium tracking-tight text-slate-50 tabular-nums">
                  {loading ? '...' : stats?.total_clusters || 0}
                </p>
                <div className="flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5">
                  <svg xmlns="http://www.w3.org/2000/svg" aria-hidden="true" role="img" width="14" height="14" viewBox="0 0 24 24" className="text-emerald-400">
                    <path fill="currentColor" d="M2 12c0-4.714 0-7.071 1.464-8.536C4.93 2 7.286 2 12 2s7.071 0 8.535 1.464C22 4.93 22 7.286 22 12s0 7.071-1.465 8.535C19.072 22 16.714 22 12 22s-7.071 0-8.536-1.465C2 19.072 2 16.714 2 12" opacity=".5"></path>
                    <path fill="currentColor" d="M14.5 10.75a.75.75 0 0 1 0-1.5H17a.75.75 0 0 1 .75.75v2.5a.75.75 0 0 1-1.5 0v-.69l-2.013 2.013a1.75 1.75 0 0 1-2.474 0l-1.586-1.586a.25.25 0 0 0-.354 0L7.53 14.53a.75.75 0 0 1-1.06-1.06l2.293-2.293a1.75 1.75 0 0 1 2.474 0l1.586 1.586a.25.25 0 0 0 .354 0l2.012-2.013z"></path>
                  </svg>
                  <span className="text-xs font-normal tracking-tight text-emerald-200">+12%</span>
                </div>
              </div>
            </div>
            <div className="flex flex-col items-end gap-2">
              <button className="inline-flex items-center gap-2 rounded-full bg-emerald-500/90 px-3 py-1.5 text-xs font-normal tracking-tight text-black shadow-lg shadow-emerald-500/40 hover:bg-emerald-400 transition-all hover:scale-105 hover:shadow-emerald-500/60 animate-pulse-glow">
                <svg xmlns="http://www.w3.org/2000/svg" aria-hidden="true" role="img" width="14" height="14" viewBox="0 0 24 24" className="text-black">
                  <path fill="currentColor" fillRule="evenodd" d="M8.732 5.771L5.67 9.914c-1.285 1.739-1.928 2.608-1.574 3.291l.018.034c.375.673 1.485.673 3.704.673c1.233 0 1.85 0 2.236.363l.02.02l3.872-4.57l-.02-.02c-.379-.371-.379-.963-.379-2.148v-.31c0-3.285 0-4.927-.923-5.21s-1.913 1.056-3.892 3.734" clipRule="evenodd"></path>
                  <path fill="currentColor" d="M10.453 16.443v.31c0 3.284 0 4.927.923 5.21s1.913-1.056 3.893-3.734l3.062-4.143c1.284-1.739 1.927-2.608 1.573-3.291l-.018-.034c-.375-.673-1.485-.673-3.704-.673c-1.233 0-1.85 0-2.236-.363l-3.872 4.57c.379.371.379.963.379 2.148" opacity=".5"></path>
                </svg>
                New Cluster
              </button>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-2xl border border-emerald-400/20 bg-black/40 p-3 backdrop-blur-sm transition-colors hover:bg-emerald-500/10 group/item cursor-pointer">
              <div className="flex items-center justify-between">
                <p className="text-xs font-normal tracking-tight text-slate-200">Active Nodes</p>
                <span className="text-[0.7rem] font-normal tracking-tight text-emerald-300">Healthy</span>
              </div>
              <p className="mt-2 text-xl font-medium tracking-tight text-slate-50 group-hover/item:translate-x-1 transition-transform">
                {loading ? '...' : stats?.active_clusters || 0}
              </p>
            </div>
            <div className="rounded-2xl border border-emerald-400/20 bg-black/40 p-3 backdrop-blur-sm transition-colors hover:bg-rose-500/10 group/item cursor-pointer">
              <div className="flex items-center justify-between">
                <p className="text-xs font-normal tracking-tight text-slate-200">Issues Detected</p>
                <span className="text-[0.7rem] font-normal tracking-tight text-rose-300">Action Req</span>
              </div>
              <p className="mt-2 text-xl font-medium tracking-tight text-slate-50 group-hover/item:translate-x-1 transition-transform">
                {loading ? '...' : stats?.total_feedback || 0}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Card 2: Smart Transfers Style (Adapted for Recent Activity) */}
      <section className="animate-in delay-300 overflow-hidden sm:p-8 bg-gradient-to-bl from-emerald-500/20 via-emerald-500/5 to-transparent rounded-3xl pt-6 pr-6 pb-6 pl-6 relative hover-card-effect border border-white/10">
        <div className="pointer-events-none absolute inset-0 opacity-40">
          <div className="absolute right-0 top-0 h-60 w-60 -translate-y-10 translate-x-10 rounded-full bg-emerald-500/25 blur-3xl"></div>
          <div className="absolute left-1/4 bottom-0 h-40 w-40 translate-y-1/3 rounded-full bg-emerald-400/20 blur-3xl"></div>
        </div>

        <div className="relative flex flex-col gap-5">
          <div className="flex items-center justify-between gap-4">
            <p className="text-xs font-normal uppercase tracking-[0.12em] text-emerald-200/80">
              System Status
            </p>
            <div className="flex items-center gap-2 rounded-full bg-black/40 px-2.5 py-1 border border-emerald-300/40">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-ping"></span>
              <span className="text-[0.7rem] font-normal tracking-tight text-emerald-100">Live Monitoring</span>
            </div>
          </div>

          <div className="space-y-4">
            <div className="relative rounded-2xl border border-emerald-400/40 bg-black/60 p-4 shadow-[0_0_40px_rgba(16,185,129,0.35)] backdrop-blur-sm transition-all hover:border-emerald-400/70">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-emerald-500/15 text-xs font-normal tracking-tight text-emerald-100 border border-emerald-400/60">
                    AI
                  </span>
                  <div>
                    <p className="text-xs font-normal tracking-tight text-slate-200">Agent Status</p>
                    <p className="mt-0.5 text-xl font-medium tracking-tight text-slate-50">Online</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-[0.7rem] text-slate-400">Uptime: 99.9%</p>
                  <p className="text-[0.7rem] text-emerald-300">Latency: 24ms</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
