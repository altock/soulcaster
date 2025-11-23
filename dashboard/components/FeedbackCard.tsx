'use client';

import type { FeedbackItem } from '@/types';

interface FeedbackCardProps {
  item: FeedbackItem;
}

export default function FeedbackCard({ item }: FeedbackCardProps) {
  const getSourceIcon = (source: FeedbackItem['source']) => {
    switch (source) {
      case 'reddit':
        return '🗨️';
      case 'sentry':
        return '⚠️';
      case 'manual':
        return '✍️';
    }
  };

  const getSourceColor = (source: FeedbackItem['source']) => {
    switch (source) {
      case 'reddit':
        return 'bg-orange-900/20 text-orange-400 border border-orange-900/50';
      case 'sentry':
        return 'bg-red-900/20 text-red-400 border border-red-900/50';
      case 'manual':
        return 'bg-matrix-green-dim text-matrix-green border border-matrix-green/30';
    }
  };

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleString();
    } catch {
      return dateString;
    }
  };

  return (
    <div className="group overflow-hidden hover:border-emerald-500/30 hover:shadow-[0_0_30px_rgba(16,185,129,0.15)] hover:bg-emerald-950/30 transition-all duration-500 bg-emerald-950/20 rounded-[2rem] pt-8 pr-8 pb-8 pl-8 relative border border-white/10">
      <div className="flex bg-gradient-to-b from-white/5 to-transparent h-full rounded-3xl relative shadow-inner flex-col group-hover:bg-white/[0.07] transition-colors duration-500">
        <div className="relative z-10 w-full rounded-2xl border border-white/10 bg-[#0F0F0F] p-5 shadow-2xl ring-1 ring-white/5 backdrop-blur-md transition-transform duration-500 group-hover:scale-[1.02]">
          <div className="mb-5 flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-gradient-to-br from-white/5 to-transparent group-hover:border-emerald-500/30 transition-colors">
                <span className="text-xl">{getSourceIcon(item.source)}</span>
              </div>
              <div>
                <div className="text-xs font-medium text-slate-200 group-hover:text-emerald-300 transition-colors">
                  {item.source}
                </div>
                <div className="text-[10px] text-slate-500">
                  {formatDate(item.created_at)}
                </div>
              </div>
            </div>
            <div className={`rounded-md px-2 py-1 text-[10px] font-medium backdrop-blur-md border ${item.source === 'manual'
                ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300'
                : 'border-white/10 bg-black/40 text-slate-300'
              }`}>
              {item.source === 'manual' ? 'Verified' : 'Auto-Captured'}
            </div>
          </div>

          <p className="text-sm text-slate-300 leading-relaxed mb-4">
            {item.body}
          </p>

          <div className="mt-4 flex gap-2 border-t border-white/5 pt-4">
            <div className="flex-1 rounded-full border border-white/5 bg-white/5 py-1.5 text-center text-[10px] font-medium text-slate-400 cursor-pointer hover:bg-white/10 transition-colors">
              Analyze
            </div>
            <div className="flex-1 rounded-full border border-white/5 bg-white/5 py-1.5 text-center text-[10px] font-medium text-slate-400 cursor-pointer hover:bg-white/10 transition-colors">
              Details
            </div>
          </div>
        </div>
      </div>

      {item.metadata && Object.keys(item.metadata).length > 0 && (
        <details className="mt-3 text-xs relative z-10 px-4">
          <summary className="cursor-pointer text-slate-500 hover:text-emerald-400 transition-colors font-medium uppercase tracking-wide">Metadata</summary>
          <pre className="mt-2 bg-black/50 p-3 rounded-lg overflow-x-auto text-emerald-400 border border-white/10 font-mono">
            {JSON.stringify(item.metadata, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}
