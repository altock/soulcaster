'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

type ActivePage = 'overview' | 'feedback' | 'clusters' | 'prs';

interface DashboardHeaderProps {
  activePage?: ActivePage;
  rightContent?: React.ReactNode;
  className?: string;
}

/**
 * Shared header component for dashboard pages with navigation.
 * Highlights the active page in the navigation menu.
 *
 * @param activePage - The currently active page
 * @param rightContent - Optional content to render on the right side of the header
 * @param className - Optional additional CSS classes to apply to the outer container
 */
export default function DashboardHeader({
  className = '',
  rightContent,
  activePage,
}: DashboardHeaderProps) {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 border-b border-white/5 bg-black/50 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto px-4 h-14 flex justify-between items-center">
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="flex bg-gradient-to-br from-emerald-400 to-emerald-600 w-6 h-6 rounded-full shadow-[0_0_15px_rgba(16,185,129,0.4)] items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-black">
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" fill="currentColor"></path>
              </svg>
            </div>
            <span className="text-sm font-semibold tracking-tight text-slate-100">Soulcaster</span>
          </Link>

          <nav className="flex items-center gap-1">
            <Link
              href="/"
              className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${pathname === '/' || activePage === 'overview'
                ? 'bg-white/5 text-emerald-400'
                : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
                }`}
            >
              Overview
            </Link>
            <Link
              href="/feedback"
              className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${pathname.startsWith('/feedback') || activePage === 'feedback'
                ? 'bg-white/5 text-emerald-400'
                : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
                }`}
            >
              Feedback
            </Link>
            <Link
              href="/clusters"
              className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${pathname.startsWith('/clusters') || activePage === 'clusters'
                ? 'bg-white/5 text-emerald-400'
                : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
                }`}
            >
              Clusters
            </Link>
            <Link
              href="/prs"
              className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${pathname.startsWith('/prs') || activePage === 'prs'
                ? 'bg-white/5 text-emerald-400'
                : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
                }`}
            >
              PRs
            </Link>
          </nav>
        </div>

        <div className="flex items-center gap-3">
          <button className="flex h-7 w-7 items-center justify-center rounded-full border border-white/10 bg-white/5 text-slate-400 hover:text-emerald-400 transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
              <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
            </svg>
          </button>
          <div className="h-7 w-7 overflow-hidden rounded-full border border-emerald-500/30 bg-emerald-900/20 p-0.5">
            <div className="h-full w-full rounded-full bg-emerald-500/20 flex items-center justify-center text-[0.6rem] font-medium text-emerald-300">
              SC
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
