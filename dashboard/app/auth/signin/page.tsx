'use client';

import { signIn } from 'next-auth/react';
import { useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import Link from 'next/link';
import LandingHeader from '@/components/LandingHeader';

function CheckIcon() {
  return (
    <svg
      className="h-5 w-5 text-emerald-400 mr-2 flex-shrink-0 mt-0.5"
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path d="M5 13l4 4L19 7"></path>
    </svg>
  );
}

function isValidCallbackUrl(url: string): boolean {
  // Only allow relative paths starting with / to prevent open redirect
  if (!url.startsWith('/')) return false;
  // Prevent protocol-relative URLs (e.g., //evil.com)
  if (url.startsWith('//')) return false;
  return true;
}

function SignInContent() {
  const searchParams = useSearchParams();
  const rawCallbackUrl = searchParams.get('callbackUrl') || '/dashboard';
  const callbackUrl = isValidCallbackUrl(rawCallbackUrl) ? rawCallbackUrl : '/dashboard';
  const error = searchParams.get('error');

  return (
    <>
      <LandingHeader />
      <div className="min-h-[calc(100vh-56px)] flex items-center justify-center">
        <div className="max-w-md w-full space-y-8 p-8 bg-matrix-card rounded-2xl border border-matrix-border">
          <div>
            <div className="flex justify-center mb-4">
              <div className="flex bg-gradient-to-br from-emerald-400 to-emerald-600 w-12 h-12 rounded-full shadow-[0_0_25px_rgba(16,185,129,0.4)] items-center justify-center">
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
                  className="text-black"
                >
                  <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" fill="currentColor"></path>
                </svg>
              </div>
            </div>
            <h2 className="text-center text-2xl font-bold text-white tracking-tight">
              Sign in to Soulcaster
            </h2>
            <p className="mt-2 text-center text-sm text-slate-400">
              Automated feedback triage and code fixes
            </p>
          </div>

          {error && (
            <div className="bg-red-500/10 border border-red-500/30 text-red-300 px-4 py-3 rounded-xl">
              <p className="text-sm">
                {error === 'OAuthAccountNotLinked'
                  ? 'This email is already associated with another account.'
                  : 'An error occurred during sign in. Please try again.'}
              </p>
            </div>
          )}

          <div className="space-y-4">
            <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-xl p-4">
              <h3 className="text-sm font-semibold text-emerald-300 mb-3">
                Soulcaster needs access to:
              </h3>
              <ul className="text-sm text-slate-300 space-y-2">
                <li className="flex items-start">
                  <CheckIcon />
                  <span>
                    <strong className="text-white">Create branches and pull requests</strong> to fix
                    issues in your repositories
                  </span>
                </li>
                <li className="flex items-start">
                  <CheckIcon />
                  <span>
                    <strong className="text-white">Read repository code</strong> to analyze issues
                    and generate fixes
                  </span>
                </li>
                <li className="flex items-start">
                  <CheckIcon />
                  <span>
                    <strong className="text-white">Push commits</strong> to branches with automated
                    code changes
                  </span>
                </li>
              </ul>
              <p className="mt-3 text-xs text-slate-400">
                Pull requests will be created from your account. You can revoke access anytime in
                your{' '}
                <a
                  href="https://github.com/settings/applications"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-emerald-400 hover:text-emerald-300 underline"
                >
                  GitHub Settings
                </a>
                .
              </p>
            </div>

            <button
              onClick={() => signIn('github', { callbackUrl })}
              className="w-full flex items-center justify-center px-4 py-3 border border-transparent text-base font-medium rounded-full text-black bg-emerald-500 hover:bg-emerald-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-emerald-500 transition-all shadow-[0_0_15px_rgba(16,185,129,0.3)] hover:shadow-[0_0_20px_rgba(16,185,129,0.5)]"
            >
              <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                <path
                  fillRule="evenodd"
                  d="M10 0C4.477 0 0 4.484 0 10.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0110 4.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.203 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.942.359.31.678.921.678 1.856 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0020 10.017C20 4.484 15.522 0 10 0z"
                  clipRule="evenodd"
                />
              </svg>
              Sign in with GitHub
            </button>

            <p className="text-xs text-center text-slate-500">
              By signing in, you agree to our{' '}
              <Link href="/privacy" className="text-emerald-400 hover:text-emerald-300 underline">
                Privacy Policy
              </Link>
              .
            </p>
          </div>
        </div>
      </div>
    </>
  );
}

export default function SignInPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center">
          <div className="text-slate-400">Loading...</div>
        </div>
      }
    >
      <SignInContent />
    </Suspense>
  );
}
