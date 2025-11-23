'use client';

export default function PrsPage() {
    return (
        <div className="min-h-screen">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <h1 className="text-2xl font-bold text-white mb-6">Pull Requests</h1>

                <div className="bg-emerald-950/20 rounded-3xl border border-white/10 backdrop-blur-sm p-16 text-center relative overflow-hidden">
                    <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 via-transparent to-transparent pointer-events-none" />

                    <div className="relative z-10">
                        <div className="mx-auto w-16 h-16 bg-white/5 rounded-full flex items-center justify-center mb-6 border border-white/10">
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V15a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2" />
                            </svg>
                        </div>
                        <h2 className="text-xl font-medium text-white mb-3">No Pull Requests Yet</h2>
                        <p className="text-slate-400 max-w-sm mx-auto leading-relaxed">
                            Generated pull requests for fixed issues will appear here once the agents start resolving clusters.
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}
