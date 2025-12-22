'use client';

import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import Footer from '@/components/Footer';

export default function ConsentPage() {
  const { data: session, update } = useSession();
  const router = useRouter();
  const [agreed, setAgreed] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!agreed) return;

    setSubmitting(true);
    try {
      const res = await fetch('/api/consent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ consented: true }),
      });

      if (res.ok) {
        // Force session update to refresh consent status in token
        await update();
        router.push('/dashboard');
        router.refresh();
      } else {
        alert('Failed to save consent. Please try again.');
      }
    } catch (error) {
      console.error('Error saving consent:', error);
      alert('An error occurred. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <div className="flex-1 flex items-center justify-center px-4 sm:px-6 md:px-8 py-8">
        <div className="max-w-2xl lg:max-w-3xl w-full">
        <div className="bg-slate-900/80 backdrop-blur-xl border border-white/10 rounded-2xl p-8 shadow-2xl">
          {/* Header */}
          <div className="mb-8">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-emerald-500 to-blue-500 rounded-xl flex items-center justify-center">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="text-white"
                >
                  <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
                  <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
                </svg>
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white">Research Preview</h1>
                <p className="text-sm text-slate-400">
                  Welcome{session?.user?.name ? `, ${session.user.name.split(' ')[0]}` : ''}
                </p>
              </div>
            </div>
          </div>

          {/* Content */}
          <div className="mb-8 space-y-4">
            <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 sm:p-4 md:p-6">
              <p className="text-amber-200 text-sm font-medium">
                Soulcaster is in Research Preview. We collect usage data to improve service
                quality and user experience.
              </p>
            </div>

            <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3 sm:p-4 md:p-6">
              <h3 className="text-sm font-semibold text-blue-200 mb-2">What this means:</h3>
              <p className="text-sm text-blue-100/80">
                We collect data about how you use Soulcaster to make the service better.
                Your participation helps us improve the product.
              </p>
            </div>

            <div className="bg-slate-700/50 border border-white/10 rounded-lg p-3 sm:p-4 md:p-6">
              <h3 className="text-sm font-semibold text-slate-200 mb-2">Your privacy matters:</h3>
              <ul className="text-sm text-slate-300 space-y-1">
                <li>• GitHub tokens are encrypted and never logged</li>
                <li>• You can delete your data at any time</li>
                <li>
                  • Full details in our{' '}
                  <a
                    href="/privacy"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-400 hover:underline"
                  >
                    Privacy Policy
                  </a>
                </li>
              </ul>
            </div>
          </div>

          {/* Consent Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            <label className="flex items-start gap-3 cursor-pointer group">
              <input
                type="checkbox"
                checked={agreed}
                onChange={(e) => setAgreed(e.target.checked)}
                className="mt-1 w-5 h-5 rounded border-slate-600 bg-slate-700 text-emerald-500 focus:ring-2 focus:ring-emerald-500/50 cursor-pointer"
              />
              <span className="text-slate-200 text-sm group-hover:text-white transition-colors">
                I understand and agree to participate in Soulcaster Research Preview. I consent to
                the collection and review of the data described above to improve the service.
              </span>
            </label>

            <div className="flex flex-col sm:flex-row gap-4">
              <button
                type="submit"
                disabled={!agreed || submitting}
                className="w-full sm:flex-1 bg-gradient-to-r from-emerald-500 to-blue-500 text-white font-semibold py-3 px-6 rounded-lg hover:from-emerald-600 hover:to-blue-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:from-emerald-500 disabled:hover:to-blue-500"
              >
                {submitting ? 'Saving...' : 'Continue to Soulcaster'}
              </button>
              <a
                href="/api/auth/signout"
                className="w-full sm:w-auto px-6 py-3 text-slate-400 hover:text-white border border-slate-600 hover:border-slate-500 rounded-lg transition-colors text-center"
              >
                Sign Out
              </a>
            </div>
          </form>
        </div>
        </div>
      </div>
      <Footer />
    </div>
  );
}
