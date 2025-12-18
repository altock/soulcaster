'use client';

import IntegrationsDirectory from '@/components/integrations/IntegrationsDirectory';

export default function IntegrationsPage() {
  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <div className="relative overflow-hidden border-b border-white/5 bg-gradient-to-b from-black via-black/95 to-transparent">
        {/* Animated background gradient */}
        <div className="pointer-events-none absolute -top-24 left-1/2 -translate-x-1/2 h-96 w-[800px] rounded-full bg-emerald-500/10 blur-[120px] opacity-60 animate-pulse" />

        <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 mb-6">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            <span className="text-xs font-medium text-emerald-300">Configuration</span>
          </div>

          <h1 className="text-4xl sm:text-5xl font-bold text-white mb-4">
            <span className="bg-gradient-to-r from-white via-emerald-200 to-emerald-400 bg-clip-text text-transparent">
              Integrations
            </span>
          </h1>

          <p className="text-lg text-slate-400 max-w-2xl leading-relaxed font-light">
            Connect your tools to automatically ingest feedback and trigger the self-healing dev loop.
            Configure webhooks, filters, and authentication below.
          </p>
        </div>
      </div>

      {/* Integration Cards Grid */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <IntegrationsDirectory />

        {/* Documentation Footer */}
        <div className="mt-16 border-t border-white/10 pt-8">
          <div className="bg-gradient-to-br from-black/40 via-black/20 to-black/40 border border-white/10 rounded-2xl p-8 backdrop-blur-sm">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-300 flex-shrink-0">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="16" x2="12" y2="12" />
                  <line x1="12" y1="8" x2="12.01" y2="8" />
                </svg>
              </div>
              <div>
                <h4 className="text-lg font-semibold text-white mb-2">Need help configuring webhooks?</h4>
                <p className="text-sm text-slate-400 leading-relaxed mb-4">
                  Each integration requires webhook configuration on the source platform. Check out our
                  documentation for step-by-step setup guides for each tool.
                </p>
                <a
                  href="https://github.com/altock/soulcaster#integrations"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-sm font-medium text-emerald-300 hover:text-emerald-200 transition-colors"
                >
                  View Documentation
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                    <polyline points="15 3 21 3 21 9" />
                    <line x1="10" y1="14" x2="21" y2="3" />
                  </svg>
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
