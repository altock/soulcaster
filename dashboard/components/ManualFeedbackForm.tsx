'use client';

import { useState } from 'react';

interface ManualFeedbackFormProps {
  onSuccess?: () => void;
}

export default function ManualFeedbackForm({ onSuccess }: ManualFeedbackFormProps) {
  const [text, setText] = useState('');
  const [githubRepoUrl, setGithubRepoUrl] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;

    setIsSubmitting(true);
    setError(null);
    setSuccess(false);

    try {
      const response = await fetch('/api/ingest/manual', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text: text.trim(),
          github_repo_url: githubRepoUrl.trim() || undefined,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to submit feedback');
      }

      setSuccess(true);
      setText('');
      setGithubRepoUrl('');
      onSuccess?.();

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-emerald-950/20 border border-white/10 backdrop-blur-sm rounded-3xl p-6 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 via-transparent to-transparent pointer-events-none" />
      <h3 className="text-lg font-semibold text-white mb-4 relative z-10">✍️ Submit Manual Feedback</h3>

      <form onSubmit={handleSubmit} className="relative z-10">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Describe the bug, issue, or feature request..."
          rows={4}
          className="w-full px-4 py-3 bg-black/40 border border-white/10 rounded-xl text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50 resize-none transition-all"
          disabled={isSubmitting}
        />

        <div className="mt-4">
          <input
            type="url"
            value={githubRepoUrl}
            onChange={(e) => setGithubRepoUrl(e.target.value)}
            placeholder="GitHub Repository URL"
            className="w-full px-4 py-3 bg-black/40 border border-white/10 rounded-xl text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50 transition-all"
            disabled={isSubmitting}
          />
        </div>

        <div className="mt-4 flex items-center justify-between">
          <div className="flex-1">
            {error && <p className="text-sm text-rose-400">{error}</p>}
            {success && (
              <p className="text-sm text-emerald-400">Feedback submitted successfully!</p>
            )}
            {!error && !success && !text.trim() && (
              <p className="text-sm text-slate-500">Enter feedback text to submit</p>
            )}
          </div>

          <button
            type="submit"
            disabled={isSubmitting || !text.trim()}
            className="px-5 py-2 bg-emerald-500 text-black rounded-full hover:bg-emerald-400 disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed transition-all font-medium shadow-[0_0_15px_rgba(16,185,129,0.2)] hover:shadow-[0_0_20px_rgba(16,185,129,0.4)] active:scale-95"
          >
            {isSubmitting ? 'Submitting...' : 'Submit Feedback'}
          </button>
        </div>
      </form>

      <div className="mt-4 text-xs text-slate-500 relative z-10">
        <p>
          💡 Tip: Manual feedback is useful for testing or when reporting issues directly from your
          team.
        </p>
      </div>
    </div>
  );
}
