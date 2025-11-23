'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

interface AgentJob {
    id: string;
    cluster_id: string;
    status: 'pending' | 'running' | 'success' | 'failed';
    logs: string | null;
    created_at: string;
    updated_at: string;
}

export default function PrsPage() {
    const [jobs, setJobs] = useState<AgentJob[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchJobs = async () => {
            try {
                const res = await fetch('http://localhost:8000/jobs');
                if (res.ok) {
                    const data = await res.json();
                    setJobs(data);
                }
            } catch (error) {
                console.error('Failed to fetch jobs:', error);
            } finally {
                setLoading(false);
            }
        };

        fetchJobs();
        // Poll every 5 seconds
        const interval = setInterval(fetchJobs, 5000);
        return () => clearInterval(interval);
    }, []);

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'success': return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
            case 'failed': return 'bg-red-500/20 text-red-400 border-red-500/30';
            case 'running': return 'bg-blue-500/20 text-blue-400 border-blue-500/30 animate-pulse';
            default: return 'bg-slate-500/20 text-slate-400 border-slate-500/30';
        }
    };

    return (
        <div className="min-h-screen">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <div className="flex items-center justify-between mb-8">
                    <h1 className="text-2xl font-bold text-white">Agent Jobs & PRs</h1>
                    <div className="text-sm text-slate-400">
                        Auto-refreshing every 5s
                    </div>
                </div>

                {loading && jobs.length === 0 ? (
                    <div className="text-center py-12">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500 mx-auto mb-4"></div>
                        <p className="text-slate-400">Loading jobs...</p>
                    </div>
                ) : jobs.length === 0 ? (
                    <div className="bg-emerald-950/20 rounded-3xl border border-white/10 backdrop-blur-sm p-16 text-center relative overflow-hidden">
                        <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 via-transparent to-transparent pointer-events-none" />
                        <div className="relative z-10">
                            <div className="mx-auto w-16 h-16 bg-white/5 rounded-full flex items-center justify-center mb-6 border border-white/10">
                                <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V15a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2" />
                                </svg>
                            </div>
                            <h2 className="text-xl font-medium text-white mb-3">No Jobs Found</h2>
                            <p className="text-slate-400 max-w-sm mx-auto leading-relaxed">
                                Trigger a fix from the Clusters page to see agent activity here.
                            </p>
                        </div>
                    </div>
                ) : (
                    <div className="grid gap-4">
                        {jobs.map((job) => (
                            <div key={job.id} className="bg-white/5 rounded-xl border border-white/10 p-6 hover:border-white/20 transition-colors">
                                <div className="flex items-start justify-between">
                                    <div>
                                        <div className="flex items-center gap-3 mb-2">
                                            <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium border ${getStatusColor(job.status)} uppercase tracking-wide`}>
                                                {job.status}
                                            </span>
                                            <span className="text-slate-400 text-sm font-mono">
                                                {job.id.substring(0, 8)}
                                            </span>
                                            <span className="text-slate-500 text-xs">
                                                {new Date(job.created_at).toLocaleString()}
                                            </span>
                                        </div>
                                        <div className="text-slate-300 text-sm mb-4">
                                            Cluster: <Link href={`/clusters/${job.cluster_id}`} className="text-emerald-400 hover:underline">{job.cluster_id.substring(0, 8)}...</Link>
                                        </div>
                                    </div>
                                </div>

                                {job.logs && (
                                    <div className="mt-4 bg-black/50 rounded-lg p-4 font-mono text-xs text-slate-300 overflow-x-auto max-h-64 whitespace-pre-wrap border border-white/5">
                                        {job.logs}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
