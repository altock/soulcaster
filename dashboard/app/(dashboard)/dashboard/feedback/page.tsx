'use client';

import { useState } from 'react';
import Link from 'next/link';
import FeedbackList from '@/components/FeedbackList';
import ManualFeedbackForm from '@/components/ManualFeedbackForm';

export default function FeedbackPage() {
  const [showManualForm, setShowManualForm] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleFeedbackSubmitted = () => {
    setRefreshTrigger((prev) => prev + 1);
    setShowManualForm(false);
  };

  return (
    <div className="min-h-screen">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex justify-end gap-3 mb-6">
          <button
            onClick={() => setShowManualForm(!showManualForm)}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 text-sm font-medium text-slate-200 hover:bg-white/10 hover:border-white/20 transition-all"
          >
            {showManualForm ? 'Cancel' : '+ Add Manual'}
          </button>
          <Link
            href="/settings/integrations"
            className="group relative inline-flex h-9 items-center justify-center gap-2 overflow-hidden rounded-full border-none bg-emerald-500 px-4 text-sm font-medium tracking-tight text-black outline-none transition-all duration-200 active:scale-95 hover:scale-105 hover:bg-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.3)] hover:shadow-[0_0_20px_rgba(16,185,129,0.6)]"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>
              <circle cx="12" cy="12" r="3"/>
            </svg>
            Configure Sources
          </Link>
        </div>

        {showManualForm && (
          <div className="mb-6 animate-in slide-in-from-top">
            <ManualFeedbackForm onSuccess={handleFeedbackSubmitted} />
          </div>
        )}

        <div className="mb-6">
          <h2 className="text-2xl font-bold text-white mb-4">All Feedback</h2>
          <FeedbackList
            refreshTrigger={refreshTrigger}
            onRequestShowSources={() => {}}
          />
        </div>
      </div>
    </div>
  );
}
