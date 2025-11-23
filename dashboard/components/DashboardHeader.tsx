import Link from 'next/link';
import { usePathname } from 'next/navigation';

type ActivePage = 'feedback' | 'clusters' | 'home';

interface DashboardHeaderProps {
  activePage?: ActivePage;
  rightContent?: React.ReactNode;
  className?: string;
}

/**
 * Shared header component for dashboard pages with navigation.
 * Highlights the active page in the navigation menu.
 *
 * @param activePage - The currently active page ('feedback', 'clusters', or 'home')
 * @param rightContent - Optional content to render on the right side of the header
 * @param className - Optional additional CSS classes to apply to the outer container
 */
export default function DashboardHeader({
  className = '',
  rightContent,
  activePage,
}: DashboardHeaderProps) {
  const pathname = usePathname();
  const getFeedbackLinkClass = () => {
    const baseClass = 'px-4 py-2 text-sm font-medium rounded-md transition-colors';
    return activePage === 'feedback'
      ? `${baseClass} text-netflix-red bg-red-900/20`
      : `${baseClass} text-gray-400 hover:text-white hover:bg-gray-800`;
  };

  const getClustersLinkClass = () => {
    const baseClass = 'px-4 py-2 text-sm font-medium rounded-md transition-colors';
    return activePage === 'clusters'
      ? `${baseClass} text-netflix-red bg-red-900/20`
      : `${baseClass} text-gray-400 hover:text-white hover:bg-gray-800`;
  };

  return (
    <header className="sticky top-0 z-50 border-b border-white/5 bg-black/50 backdrop-blur-xl">
      <div className="max-w-6xl mx-auto px-4 h-14 flex justify-between items-center">
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="flex bg-gradient-to-br from-emerald-400 to-emerald-600 w-6 h-6 rounded-full shadow-[0_0_15px_rgba(16,185,129,0.4)] items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-black">
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" fill="currentColor"></path>
              </svg>
            </div>
            <span className="text-sm font-semibold tracking-tight text-slate-100">Soulcaster</span>
          </Link>

          <nav className="hidden sm:flex items-center gap-1">
            <Link
              href="/"
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${pathname === '/'
                  ? 'bg-white/5 text-emerald-400'
                  : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
                }`}
            >
              Overview
            </Link>
            <Link
              href="/clusters"
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${pathname.startsWith('/clusters')
                  ? 'bg-white/5 text-emerald-400'
                  : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
                }`}
            >
              Clusters
            </Link>
            <a href="#" className="rounded-md px-3 py-1.5 text-xs font-medium text-slate-400 hover:bg-white/5 hover:text-slate-200 transition-colors">
              Intelligence
            </a>
            <a href="#" className="rounded-md px-3 py-1.5 text-xs font-medium text-slate-400 hover:bg-white/5 hover:text-slate-200 transition-colors">
              API
            </a>
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
