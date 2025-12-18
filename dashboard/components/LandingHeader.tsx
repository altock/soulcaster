'use client';

import Link from 'next/link';
import { useSession, signIn } from 'next-auth/react';

export default function LandingHeader() {
  const { data: session, status } = useSession();

  return (
    <header className="sticky top-0 z-50 border-b border-white/5 bg-black/50 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto px-4 h-14 flex justify-between items-center">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5">
          <div className="flex bg-gradient-to-br from-emerald-400 to-emerald-600 w-6 h-6 rounded-full shadow-[0_0_15px_rgba(16,185,129,0.4)] items-center justify-center">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-black"
            >
              <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" fill="currentColor"></path>
            </svg>
          </div>
          <span className="text-sm font-semibold tracking-tight text-slate-100">Soulcaster</span>
        </Link>

        {/* Right side: Auth button only */}
        <div className="flex items-center gap-3">
          {status === 'loading' ? (
            <div className="h-8 w-20 rounded-full bg-white/5 animate-pulse"></div>
          ) : session ? (
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-2 h-8 px-4 rounded-full bg-emerald-500 text-xs font-medium text-black hover:bg-emerald-400 transition-all shadow-[0_0_15px_rgba(16,185,129,0.3)] hover:shadow-[0_0_20px_rgba(16,185,129,0.5)]"
            >
              Go to Dashboard
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            </Link>
          ) : (
            <button
              onClick={() => signIn('github')}
              className="inline-flex items-center gap-2 h-8 px-3 rounded-full border border-white/10 bg-white/5 text-xs font-medium text-slate-200 hover:bg-white/10 hover:border-white/20 transition-all"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
              </svg>
              Sign in with GitHub
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
