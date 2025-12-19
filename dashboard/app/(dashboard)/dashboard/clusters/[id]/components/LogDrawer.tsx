'use client';

import { useEffect, useRef } from 'react';
import type { AgentJob } from '@/types';

interface LogDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  job: AgentJob | null;
  logText: string;
  isTailing: boolean;
  onToggleTail: () => void;
  onLoadMore: () => void;
}

export default function LogDrawer({
  isOpen,
  onClose,
  job,
  logText,
  isTailing,
  onToggleTail,
  onLoadMore,
}: LogDrawerProps) {
  const logContainerRef = useRef<HTMLPreElement>(null);

  // Auto-scroll to bottom when tailing
  useEffect(() => {
    if (isTailing && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logText, isTailing]);

  // Handle escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const getStatusColor = (status: AgentJob['status']) => {
    switch (status) {
      case 'running':
        return 'text-yellow-400';
      case 'success':
        return 'text-emerald-400';
      case 'failed':
        return 'text-rose-400';
      default:
        return 'text-slate-400';
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 z-40 transition-opacity duration-300"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <div
        className="fixed top-0 right-0 h-full w-full sm:w-[480px] bg-[#0A0A0A] border-l border-white/10 z-50 flex flex-col shadow-2xl transition-transform duration-300"
        role="dialog"
        aria-modal="true"
        aria-labelledby="log-drawer-title"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-white/10 shrink-0">
          <div>
            <h3 id="log-drawer-title" className="text-sm font-medium text-white">
              Job Logs
            </h3>
            {job && (
              <div className="flex items-center gap-2 mt-1">
                <span className="text-xs text-slate-500 font-mono">
                  {job.id.slice(0, 8)}...
                </span>
                <span className={`text-xs font-medium uppercase ${getStatusColor(job.status)}`}>
                  {job.status}
                </span>
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-full hover:bg-white/5 text-slate-400 hover:text-white transition-colors"
            aria-label="Close drawer"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Controls */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-white/5 bg-white/5 shrink-0">
          <div className="flex items-center gap-2">
            {isTailing && (
              <span className="flex items-center gap-1.5 text-xs text-emerald-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Tailing
              </span>
            )}
            {job?.status === 'running' && !isTailing && (
              <span className="text-xs text-slate-500">Paused</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={onLoadMore}
              className="text-xs text-slate-400 hover:text-white transition-colors px-2 py-1 rounded hover:bg-white/5"
            >
              Load more
            </button>
            <button
              onClick={onToggleTail}
              className={`text-xs px-3 py-1 rounded-full transition-colors ${
                isTailing
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                  : 'text-slate-400 hover:text-white hover:bg-white/5'
              }`}
            >
              {isTailing ? 'Pause' : 'Tail'}
            </button>
          </div>
        </div>

        {/* Log content */}
        <div className="flex-1 overflow-hidden">
          <pre
            ref={logContainerRef}
            className="h-full overflow-auto p-4 font-mono text-xs text-slate-300 whitespace-pre-wrap leading-relaxed"
          >
            {logText || (
              <span className="text-slate-500 italic">No logs yet...</span>
            )}
          </pre>
        </div>

        {/* Footer with PR link if available */}
        {job?.pr_url && (
          <div className="p-4 border-t border-white/10 shrink-0">
            <a
              href={job.pr_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 w-full px-4 py-2.5 rounded-full border border-emerald-500/30 text-sm font-medium text-emerald-400 hover:bg-emerald-500/10 transition-colors"
            >
              <svg
                viewBox="0 0 24 24"
                fill="currentColor"
                className="w-4 h-4"
              >
                <path
                  fillRule="evenodd"
                  d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
                  clipRule="evenodd"
                />
              </svg>
              View Pull Request
            </a>
          </div>
        )}
      </div>
    </>
  );
}
