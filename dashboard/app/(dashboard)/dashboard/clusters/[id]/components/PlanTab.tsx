'use client';

import type { CodingPlan } from '@/types';

interface PlanTabProps {
  codingPlan: CodingPlan | null;
  canStartFix: boolean;
  isFixing: boolean;
  isGeneratingPlan: boolean;
  onGeneratePlan: () => void;
  onStartFix: () => void;
}

export default function PlanTab({
  codingPlan,
  canStartFix,
  isFixing,
  isGeneratingPlan,
  onGeneratePlan,
  onStartFix,
}: PlanTabProps) {
  // Empty state when no plan exists
  if (!codingPlan) {
    return (
      <div className="rounded-3xl border border-white/10 bg-gradient-to-br from-emerald-500/5 to-transparent p-12 text-center">
        <div className="mx-auto w-16 h-16 bg-emerald-500/10 rounded-full flex items-center justify-center mb-6 border border-emerald-500/30">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-8 w-8 text-emerald-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
        </div>
        <h2 className="text-xl font-medium text-white mb-3">
          No Implementation Plan
        </h2>
        <p className="text-slate-400 max-w-md mx-auto mb-8 leading-relaxed">
          Generate a coding plan to analyze the feedback in this cluster and
          create a strategy for fixing the issues.
        </p>
        <button
          onClick={onGeneratePlan}
          disabled={isGeneratingPlan || !canStartFix}
          className="px-8 py-3 rounded-full bg-emerald-500 text-black text-sm font-bold hover:bg-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.3)] hover:shadow-[0_0_30px_rgba(16,185,129,0.5)] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isGeneratingPlan ? (
            <span className="flex items-center gap-2">
              <svg
                className="animate-spin h-4 w-4"
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
              Generating Plan...
            </span>
          ) : (
            'Generate Plan'
          )}
        </button>
        {!canStartFix && (
          <p className="text-xs text-slate-500 mt-4">
            Cannot generate plan while a fix is in progress.
          </p>
        )}
      </div>
    );
  }

  // Plan exists - show it prominently
  return (
    <div className="space-y-6">
      {/* Plan Content */}
      <div className="rounded-3xl border border-white/10 bg-gradient-to-br from-emerald-500/5 to-transparent p-8">
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-emerald-500/10 rounded-full flex items-center justify-center border border-emerald-500/30">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5 text-emerald-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
            </div>
            <div>
              <span className="text-xs font-medium text-emerald-400 uppercase tracking-wider">
                Implementation Plan
              </span>
              <p className="text-[10px] text-slate-500 mt-0.5">
                Generated {new Date(codingPlan.created_at).toLocaleString()}
              </p>
            </div>
          </div>
          {canStartFix && (
            <button
              onClick={onGeneratePlan}
              disabled={isGeneratingPlan || isFixing}
              className="text-xs text-slate-400 hover:text-emerald-400 transition-colors disabled:opacity-50"
            >
              {isGeneratingPlan ? 'Regenerating...' : 'Regenerate'}
            </button>
          )}
        </div>

        <h2 className="text-2xl font-semibold text-white mb-4">
          {codingPlan.title}
        </h2>

        <div className="prose prose-invert prose-sm max-w-none">
          <p className="text-slate-300 leading-relaxed whitespace-pre-wrap">
            {codingPlan.description}
          </p>
        </div>
      </div>

      {/* Action Panel */}
      {canStartFix && (
        <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div>
              <h3 className="text-sm font-medium text-white">
                Ready to implement?
              </h3>
              <p className="text-xs text-slate-400 mt-1">
                Start the automated fix to generate a pull request based on this
                plan.
              </p>
            </div>
            <button
              onClick={onStartFix}
              disabled={isFixing || isGeneratingPlan}
              className="w-full sm:w-auto px-8 py-3 rounded-full bg-emerald-500 text-black text-sm font-bold hover:bg-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.3)] hover:shadow-[0_0_30px_rgba(16,185,129,0.5)] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isFixing ? (
                <span className="flex items-center justify-center gap-2">
                  <svg
                    className="animate-spin h-4 w-4"
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
                  Starting Agent...
                </span>
              ) : (
                'Start Automated Fix'
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
