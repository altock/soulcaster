'use client';

import { useState } from 'react';
import Link from 'next/link';
import StatsCards from '@/components/StatsCards';
import FeedbackList from '@/components/FeedbackList';
import ManualFeedbackForm from '@/components/ManualFeedbackForm';
import SourceConfig from '@/components/SourceConfig';

export default function FeedbackPage() {
  const [showAddSource, setShowAddSource] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleFeedbackSubmitted = () => {
    // Trigger refresh of feedback list and stats
    setRefreshTrigger((prev) => prev + 1);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link href="/" className="text-2xl font-bold text-blue-600">
                FeedbackAgent
              </Link>
              <nav className="flex gap-1">
                <Link
                  href="/feedback"
                  className="px-4 py-2 text-sm font-medium text-blue-600 bg-blue-50 rounded-md"
                >
                  Feedback
                </Link>
                <Link
                  href="/clusters"
                  className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-md"
                >
                  Clusters
                </Link>
              </nav>
            </div>

            <button
              onClick={() => setShowAddSource(!showAddSource)}
              className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 font-medium transition-colors"
            >
              {showAddSource ? 'Hide Sources' : '+ Add Source'}
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats */}
        <StatsCards key={refreshTrigger} />

        {/* Add Source Panel (collapsible) */}
        {showAddSource && (
          <div className="mb-6 space-y-4 animate-in slide-in-from-top">
            <ManualFeedbackForm onSuccess={handleFeedbackSubmitted} />
            <SourceConfig />
          </div>
        )}

        {/* Feedback List */}
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">All Feedback</h2>
          <FeedbackList refreshTrigger={refreshTrigger} />
        </div>

        {/* Clustering Placeholder */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 text-center">
          <h3 className="text-lg font-semibold text-blue-900 mb-2">
            🧠 Clustering Coming Soon
          </h3>
          <p className="text-blue-700">
            Feedback items will automatically be clustered into related issues using AI.
            View clusters in the{' '}
            <Link href="/clusters" className="font-semibold underline">
              Clusters tab
            </Link>
            .
          </p>
        </div>
      </div>
    </div>
  );
}
