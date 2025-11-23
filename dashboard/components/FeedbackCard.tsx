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
    <div className="group relative overflow-hidden rounded-[2rem] border border-white/10 bg-gradient-to-br from-emerald-500/15 via-emerald-500/5 to-transparent p-6 shadow-[0_0_60px_rgba(16,185,129,0.15)] transition-all duration-500 hover:border-emerald-500/30 hover:shadow-[0_0_80px_rgba(16,185,129,0.25)]">
      {/* Glow Effect */}
      <div className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-500 group-hover:opacity-100">
        <div className="absolute -left-24 top-10 h-64 w-64 animate-pulse rounded-full bg-emerald-500/25 blur-3xl"></div>
        <div className="absolute -bottom-10 right-0 h-52 w-52 rounded-full bg-emerald-400/20 blur-3xl"></div>
      </div>

      <div className="relative z-10 flex flex-col gap-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-gradient-to-br from-white/5 to-transparent transition-colors group-hover:border-emerald-500/30">
              <span className="text-xl">{getSourceIcon(item.source)}</span>
            </div>
            <div>
              <div className="text-xs font-medium text-slate-200 transition-colors group-hover:text-emerald-300">
                {item.source}
              </div>
              <div className="text-[10px] text-slate-500">{formatDate(item.created_at)}</div>
            </div>
          </div>
          <div
            className={`rounded-md border px-2 py-1 text-[10px] font-medium backdrop-blur-md ${item.source === 'manual'
                ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300'
                : 'border-white/10 bg-black/40 text-slate-300'
              }`}
          >
            {item.source === 'manual' ? 'Verified' : 'Auto-Captured'}
          </div>
        </div>

        <p className="text-sm leading-relaxed text-slate-300">{item.body}</p>

        <div className="flex gap-2 border-t border-white/5 pt-4">
          <div className="flex-1 cursor-pointer rounded-full border border-white/5 bg-white/5 py-1.5 text-center text-[10px] font-medium text-slate-400 transition-colors hover:bg-white/10">
            Analyze
          </div>
          <div className="flex-1 cursor-pointer rounded-full border border-white/5 bg-white/5 py-1.5 text-center text-[10px] font-medium text-slate-400 transition-colors hover:bg-white/10">
            Details
          </div>
        </div>
      </div>
    </div>
  );
}
