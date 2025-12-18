'use client';

import { useState } from 'react';
import FeedbackList from '@/components/FeedbackList';
import ManualFeedbackForm from '@/components/ManualFeedbackForm';
import SourceConfig from '@/components/SourceConfig';

export default function FeedbackPage() {
  const [showAddSource, setShowAddSource] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleFeedbackSubmitted = () => {
    setRefreshTrigger((prev) => prev + 1);
  };

  return (
    <div className="min-h-screen">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex justify-end mb-6">
          <button
            onClick={() => setShowAddSource(!showAddSource)}
            className="group relative inline-flex h-9 items-center justify-center gap-2 overflow-hidden rounded-full border-none bg-emerald-500 px-4 text-sm font-medium tracking-tight text-black outline-none transition-all duration-200 active:scale-95 hover:scale-105 hover:bg-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.3)] hover:shadow-[0_0_20px_rgba(16,185,129,0.6)]"
          >
            <span className="relative z-10 flex items-center gap-2">
              {showAddSource ? 'Hide Sources' : 'Configure Sources'}
            </span>
          </button>
        </div>

        {showAddSource && (
          <div className="mb-6 space-y-4 animate-in slide-in-from-top">
            <ManualFeedbackForm onSuccess={handleFeedbackSubmitted} />
            <SourceConfig />
          </div>
        )}

        <div className="mb-6">
          <h2 className="text-2xl font-bold text-white mb-4">All Feedback</h2>
          <FeedbackList refreshTrigger={refreshTrigger} />
        </div>
      </div>
    </div>
  );
}
