'use client';

import Link from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import { useSession, signIn, signOut } from 'next-auth/react';
import { useState } from 'react';

type ActivePage = 'overview' | 'feedback' | 'clusters' | 'prs' | 'billing' | 'settings';

interface DashboardHeaderProps {
  activePage?: ActivePage;
  className?: string;
}

/**
 * Dashboard header that renders navigation, brand, and user session controls while highlighting the active page.
 *
 * @param activePage - Optional explicit active page identifier to force which nav item is highlighted
 * @param className - Optional CSS class names added to the outer container
 * @returns The dashboard header element
 */
export default function DashboardHeader({
  className = '',
  activePage,
}: DashboardHeaderProps) {
  const pathname = usePathname();
  const { data: session, status } = useSession();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navLinks = [
    { href: '/dashboard', label: 'Dashboard', active: pathname === '/dashboard' || activePage === 'overview' },
    { href: '/dashboard/clusters', label: 'Clusters', active: pathname.startsWith('/dashboard/clusters') || activePage === 'clusters' },
    { href: '/dashboard/feedback', label: 'Feedback', active: pathname.startsWith('/dashboard/feedback') || activePage === 'feedback' },
    { href: '/dashboard/prs', label: 'PRs', active: pathname.startsWith('/dashboard/prs') || activePage === 'prs' },
    { href: '/settings/integrations', label: 'Settings', active: pathname.startsWith('/settings') || activePage === 'settings' },
  ];

  return (
    <header className="sticky top-0 z-50 border-b border-white/5 bg-black/50 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto px-4 h-14 flex justify-between items-center">
        <div className="flex items-center gap-4 md:gap-8">
          <Link href="/" className="flex items-center gap-2">
            <div className="flex bg-gradient-to-br from-emerald-400 to-emerald-600 w-6 h-6 rounded-full shadow-[0_0_15px_rgba(16,185,129,0.4)] items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-black">
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" fill="currentColor"></path>
              </svg>
            </div>
            <span className="text-sm font-semibold tracking-tight text-slate-100 hidden sm:inline">Soulcaster</span>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-1">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${link.active
                  ? 'bg-white/5 text-emerald-400'
                  : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
                }`}
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-2">
          {status === 'loading' ? (
            <div className="h-7 w-7 rounded-full border border-white/10 bg-white/5 animate-pulse"></div>
          ) : session ? (
            <div className="relative">
              <button
                onClick={() => setDropdownOpen(!dropdownOpen)}
                onBlur={() => setTimeout(() => setDropdownOpen(false), 200)}
                className="h-7 w-7 overflow-hidden rounded-full border border-emerald-500/30 bg-emerald-900/20 hover:border-emerald-500/50 transition-colors"
                title={session.user?.name || 'User menu'}
              >
                {session.user?.image ? (
                  <Image src={session.user.image} alt={session.user.name || 'User'} width={28} height={28} className="h-full w-full object-cover" />
                ) : (
                  <div className="h-full w-full flex items-center justify-center text-[0.6rem] font-medium text-emerald-300 bg-emerald-500/20">
                    {session.user?.name?.substring(0, 2).toUpperCase() || 'SC'}
                  </div>
                )}
              </button>

              {dropdownOpen && (
                <div className="absolute right-0 mt-2 w-48 rounded-lg border border-white/10 bg-black/90 backdrop-blur-xl shadow-xl overflow-hidden">
                  <div className="px-4 py-3 border-b border-white/10">
                    <p className="text-sm font-medium text-white">{session.user?.name || 'User'}</p>
                    <p className="text-xs text-slate-400 mt-0.5">{session.user?.email || ''}</p>
                  </div>
                  <button
                    onClick={() => signOut()}
                    className="w-full text-left px-4 py-2 text-sm text-slate-300 hover:bg-white/5 hover:text-white transition-colors flex items-center gap-2"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                      <polyline points="16 17 21 12 16 7"></polyline>
                      <line x1="21" y1="12" x2="9" y2="12"></line>
                    </svg>
                    Sign out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <button
              onClick={() => signIn('github')}
              className="inline-flex items-center gap-2 h-8 px-3 rounded-full border border-white/10 bg-white/5 text-xs font-medium text-slate-200 hover:bg-white/10 hover:border-white/20 hover:text-white transition-all"
              title="Sign in to access private repositories"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
              </svg>
              Sign in
            </button>
          )}

          {/* Mobile hamburger */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden p-2 text-slate-400 hover:text-white transition-colors"
            aria-label="Toggle menu"
          >
            {mobileMenuOpen ? (
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="3" y1="12" x2="21" y2="12"></line>
                <line x1="3" y1="6" x2="21" y2="6"></line>
                <line x1="3" y1="18" x2="21" y2="18"></line>
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileMenuOpen && (
        <nav className="md:hidden border-t border-white/5 bg-black/90 backdrop-blur-xl">
          <div className="px-4 py-2 space-y-1">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                className={`block rounded-md px-3 py-2 text-sm font-medium transition-colors ${link.active
                  ? 'bg-white/5 text-emerald-400'
                  : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
                }`}
              >
                {link.label}
              </Link>
            ))}
          </div>
        </nav>
      )}
    </header>
  );
}