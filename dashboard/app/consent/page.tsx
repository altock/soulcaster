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
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!agreed) return;

    setSubmitting(true);
    setError(null);
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
      } else {
        setError('Failed to save consent. Please try again.');
      }
    } catch (err) {
      console.error('Error saving consent:', err);
      setError('An error occurred. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col relative overflow-hidden">
      {/* Background Glow */}
      <div className="pointer-events-none absolute -top-24 left-1/2 -translate-x-1/2 h-96 w-full max-w-4xl rounded-full bg-emerald-500/5 blur-[100px] opacity-50" />
      
      <div className="flex-1 flex items-center justify-center px-4 sm:px-6 md:px-8 py-12 relative z-10">
        <div className="max-w-2xl w-full">
          <div className="relative ring-1 ring-white/10 bg-slate-900/40 backdrop-blur-xl rounded-3xl p-8 md:p-12 shadow-[0_20px_50px_-12px_rgba(0,0,0,0.8)] overflow-hidden group">
            {/* Subtle inner glow */}
            <div className="absolute -left-10 -top-16 h-64 w-64 bg-gradient-to-tr from-emerald-400/10 to-transparent rounded-full blur-3xl opacity-50" />
            
            <div className="relative">
              {/* Header */}
              <div className="mb-10">
                <div className="flex items-center gap-4 mb-6">
                  <div className="h-12 w-12 rounded-xl bg-white/5 ring-1 ring-white/10 flex items-center justify-center">
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
                      className="text-emerald-400"
                    >
                      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10" />
                      <path d="m9 12 2 2 4-4" />
                    </svg>
                  </div>
                  <div>
                    <h1 className="text-3xl font-medium tracking-tight text-white">Research Preview</h1>
                    <p className="text-slate-400 font-light">
                      Welcome{session?.user?.name ? `, ${session.user.name.split(' ')[0] || session.user.name}` : ''}
                    </p>
                  </div>
                </div>
              </div>

              {/* Content */}
              <div className="mb-10 space-y-6">
                <div className="space-y-2">
                  <h3 className="text-sm font-medium text-emerald-400/90 tracking-wider uppercase">Our Commitment</h3>
                  <p className="text-slate-300 leading-relaxed font-light">
                    Soulcaster is in Research Preview. We collect usage data to improve service quality and help our AI agents learn how to better assist you.
                  </p>
                </div>

                <div className="grid grid-cols-1 gap-4">
                  <div className="bg-white/5 border border-white/5 rounded-2xl p-5 hover:border-emerald-500/20 transition-colors text-left">
                    <h4 className="text-sm font-medium text-white mb-2 flex items-center gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                      What we collect
                    </h4>
                    <p className="text-sm text-slate-400 leading-relaxed font-light">
                      Usage patterns, performance metrics, and interaction data. This helps us identify where the system succeeds and where it needs improvement.
                    </p>
                  </div>

                  <div className="bg-white/5 border border-white/5 rounded-2xl p-5 hover:border-emerald-500/20 transition-colors text-left">
                    <h4 className="text-sm font-medium text-white mb-2 flex items-center gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                      Your Privacy
                    </h4>
                    <ul className="text-sm text-slate-400 space-y-2 font-light">
                      <li className="flex items-start gap-2 text-left">
                        <span className="text-emerald-500/60">•</span>
                        <span>GitHub tokens are encrypted at rest and never logged</span>
                      </li>
                      <li className="flex items-start gap-2 text-left">
                        <span className="text-emerald-500/60">•</span>
                        <span>You maintain full control over your data at all times</span>
                      </li>
                      <li className="flex items-start gap-2 text-left">
                        <span className="text-emerald-500/60">•</span>
                        <span>Read our full{' '}
                          <a href="/privacy" className="text-emerald-400 hover:text-emerald-300 underline underline-offset-4 transition-colors">
                            Privacy Policy
                          </a>
                        </span>
                      </li>
                    </ul>
                  </div>
                </div>
              </div>

              {/* Error Message */}
              {error && (
                <div className="bg-red-500/10 border border-red-500/20 rounded-2xl p-4 text-left">
                  <p className="text-sm text-red-400">{error}</p>
                </div>
              )}

              {/* Consent Form */}
              <form onSubmit={handleSubmit} className="space-y-8">
                <label className="flex items-start gap-4 cursor-pointer group text-left">
                  <div className="relative flex items-center mt-1">
                    <input
                      type="checkbox"
                      checked={agreed}
                      onChange={(e) => setAgreed(e.target.checked)}
                      className="peer h-5 w-5 cursor-pointer appearance-none rounded border border-white/20 bg-white/5 transition-all checked:bg-emerald-500 checked:border-emerald-500 focus:ring-2 focus:ring-emerald-500/50 focus:ring-offset-2 focus:ring-offset-slate-900"
                    />
                    <svg className="absolute h-5 w-5 text-black pointer-events-none opacity-0 peer-checked:opacity-100 transition-opacity" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  </div>
                  <span className="text-slate-400 text-sm leading-relaxed group-hover:text-slate-200 transition-colors font-light">
                    I understand and agree to participate in the Soulcaster Research Preview. I consent to the collection and review of the data described above.
                  </span>
                </label>

                <div className="flex flex-col sm:flex-row gap-4">
                  <button
                    type="submit"
                    disabled={!agreed || submitting}
                    className="group relative inline-flex h-12 flex-1 items-center justify-center gap-2 overflow-hidden rounded-full border-none bg-emerald-500 px-8 text-sm font-medium tracking-tight text-black outline-none transition-all duration-200 active:scale-95 hover:scale-[1.02] hover:bg-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.4)] hover:shadow-[0_0_30px_rgba(16,185,129,0.6)] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100 disabled:shadow-none"
                  >
                    <span className="relative z-10 flex items-center gap-2">
                      {submitting ? 'Setting up your workspace...' : 'Enter Soulcaster'}
                      {!submitting && (
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="transition-transform duration-300 group-hover:translate-x-1">
                          <path d="M5 12h14" />
                          <path d="m12 5 7 7-7 7" />
                        </svg>
                      )}
                    </span>
                  </button>
                  <a
                    href="/api/auth/signout"
                    className="inline-flex h-12 items-center justify-center gap-2 rounded-full border border-white/10 bg-white/5 px-8 text-sm font-normal text-slate-300 hover:bg-white/10 hover:border-white/20 hover:text-white transition-all active:scale-95 sm:w-auto"
                  >
                    Sign Out
                  </a>
                </div>
              </form>
            </div>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
}
