import Link from 'next/link';
import LandingHeader from '@/components/LandingHeader';

export default function Home() {
  return (
    <>
      <LandingHeader />
      <div className="flex flex-col items-center justify-center min-h-[80vh]">
        {/* Hero Section */}
        <section className="animate-in delay-0 z-10 mt-16 mb-24 relative">
          {/* Glow Effect */}
          <div className="pointer-events-none absolute -top-24 left-0 h-96 w-96 rounded-full bg-emerald-500/10 blur-[100px] opacity-50"></div>

          <div className="z-10 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
            <h1 className="text-5xl font-normal tracking-tight text-white sm:text-6xl">
            <span className="block text-slate-400">Self-Healing Dev Loop</span>
            <span className="block bg-gradient-to-r from-emerald-200 via-emerald-400 to-emerald-100 bg-clip-text text-transparent animate-gradient-text">
              Powered by AI Agents
            </span>
          </h1>

          <p className="mt-6 text-lg text-slate-400 leading-relaxed max-w-lg font-light">
            Automatically listen to feedback, cluster issues, and generate fixes. Your AI-powered
            development assistant that never sleeps.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-4">
            <Link
              href="/dashboard"
              className="group relative inline-flex h-10 min-w-[140px] items-center justify-center gap-2 overflow-hidden rounded-full border-none bg-emerald-500 px-5 text-sm font-medium tracking-tight text-black outline-none transition-all duration-200 active:scale-95 hover:scale-105 hover:bg-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.3)] hover:shadow-[0_0_20px_rgba(16,185,129,0.6)]"
            >
              <span className="relative z-10 flex items-center gap-2">
                Get Started
                <svg xmlns="http://www.w3.org/2000/svg" aria-hidden="true" role="img" width="16" height="16" viewBox="0 0 24 24" className="text-black/70 transition-transform duration-300 group-hover:translate-x-1 group-hover:text-black">
                  <path fill="currentColor" fillRule="evenodd" d="M3.25 12a.75.75 0 0 1 .75-.75h9.25v1.5H4a.75.75 0 0 1-.75-.75" clipRule="evenodd" opacity=".5"></path>
                  <path fill="currentColor" d="M13.25 12.75V18a.75.75 0 0 0 1.28.53l6-6a.75.75 0 0 0 0-1.06l-6-6a.75.75 0 0 0-1.28.53z"></path>
                </svg>
              </span>
            </Link>

            <a href="https://github.com/altock/soulcaster" target="_blank" rel="noopener noreferrer" className="inline-flex h-10 items-center gap-2 rounded-full border border-white/10 bg-white/5 px-5 text-sm font-normal text-slate-200 hover:bg-white/10 hover:border-white/20 hover:scale-105 transition-all active:scale-95">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"></path>
              </svg>
              <span>View on GitHub</span>
            </a>
          </div>
        </div>
      </section>

      {/* Feature Cards */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Feature 1: Listen */}
          <div className="relative ring-1 ring-white/10 p-6 md:p-8 shadow-[0_10px_40px_-10px_rgba(0,0,0,0.6)] overflow-hidden rounded-2xl group hover:ring-emerald-500/30 transition-all">
            <div className="absolute -left-10 -top-16 h-64 w-64 bg-gradient-to-tr from-emerald-400/20 to-emerald-300/5 rounded-full blur-2xl group-hover:opacity-80 opacity-50 transition-opacity" />
            <div className="relative">
              <div className="flex items-center gap-3 mb-6">
                <div className="h-10 w-10 rounded-xl bg-white/5 ring-1 ring-white/10 flex items-center justify-center group-hover:ring-emerald-500/30 transition-all">
                  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-emerald-300">
                    <path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9" />
                    <path d="M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5" />
                    <circle cx="12" cy="12" r="2" />
                    <path d="M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5" />
                    <path d="M19.1 4.9C23 8.8 23 15.1 19.1 19" />
                  </svg>
                </div>
                <h3 className="text-2xl md:text-3xl font-semibold tracking-tight text-white">Listen</h3>
              </div>
              <p className="text-white/70 leading-relaxed">
                Automatically ingests feedback from Reddit communities and GitHub issues in real-time.
              </p>
              <div className="mt-8 grid grid-cols-5 gap-3 md:gap-4">
                <div className="flex flex-col items-center gap-2">
                  <div className="h-10 w-10 md:h-12 md:w-12 rounded-full bg-white/5 ring-1 ring-white/10 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white/60">
                      <circle cx="12" cy="12" r="10" />
                      <polyline points="12 6 12 12 16 14" />
                    </svg>
                  </div>
                  <span className="text-[10px] md:text-xs text-white/60">Real-time</span>
                </div>
                <div className="flex flex-col items-center gap-2">
                  <div className="h-10 w-10 md:h-12 md:w-12 rounded-full bg-white/5 ring-1 ring-white/10 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white/60">
                      <rect width="18" height="18" x="3" y="3" rx="2" />
                      <path d="M7 7h10" />
                      <path d="M7 12h10" />
                      <path d="M7 17h10" />
                    </svg>
                  </div>
                  <span className="text-[10px] md:text-xs text-white/60">Multi-source</span>
                </div>
                <div className="flex flex-col items-center gap-2">
                  <div className="h-10 w-10 md:h-12 md:w-12 rounded-full bg-white/5 ring-1 ring-white/10 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white/60">
                      <path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8" />
                      <path d="M21 3v5h-5" />
                    </svg>
                  </div>
                  <span className="text-[10px] md:text-xs text-white/60">Continuous</span>
                </div>
                <div className="flex flex-col items-center gap-2">
                  <div className="h-10 w-10 md:h-12 md:w-12 rounded-full bg-white/5 ring-1 ring-white/10 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white/60">
                      <rect width="20" height="14" x="2" y="3" rx="2" />
                      <path d="M8 21h8" />
                      <path d="M12 17v4" />
                    </svg>
                  </div>
                  <span className="text-[10px] md:text-xs text-white/60">Automated</span>
                </div>
                <div className="flex flex-col items-center gap-2">
                  <div className="h-10 w-10 md:h-12 md:w-12 rounded-full bg-white/5 ring-1 ring-white/10 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-emerald-300">
                      <path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2" />
                    </svg>
                  </div>
                  <span className="text-[10px] md:text-xs text-white/60">Scalable</span>
                </div>
              </div>
            </div>
          </div>

          {/* Feature 2: Think */}
          <div className="relative ring-1 ring-white/10 p-6 md:p-8 shadow-[0_10px_40px_-10px_rgba(0,0,0,0.6)] overflow-hidden rounded-2xl group hover:ring-emerald-500/30 transition-all">
            <div className="absolute -right-10 -top-16 h-64 w-64 bg-gradient-to-tl from-emerald-400/20 to-emerald-300/5 rounded-full blur-2xl group-hover:opacity-80 opacity-50 transition-opacity" />
            <div className="relative">
              <div className="flex items-center gap-3 mb-6">
                <div className="h-10 w-10 rounded-xl bg-white/5 ring-1 ring-white/10 flex items-center justify-center group-hover:ring-emerald-500/30 transition-all">
                  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-emerald-300">
                    <path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z" />
                    <path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z" />
                    <path d="M15 13a4.5 4.5 0 0 1-3-4 4.5 4.5 0 0 1-3 4" />
                    <path d="M17.599 6.5a3 3 0 0 0 .399-1.375" />
                    <path d="M6.003 5.125A3 3 0 0 0 6.401 6.5" />
                    <path d="M3.477 10.896a4 4 0 0 1 .585-.396" />
                    <path d="M19.938 10.5a4 4 0 0 1 .585.396" />
                    <path d="M6 18a4 4 0 0 1-1.967-.516" />
                    <path d="M19.967 17.484A4 4 0 0 1 18 18" />
                  </svg>
                </div>
                <h3 className="text-2xl md:text-3xl font-semibold tracking-tight text-white">Think</h3>
              </div>
              <p className="text-white/70 leading-relaxed">
                Intelligent agents cluster related issues, summarize the problem, and identify the root cause.
              </p>
              <div className="mt-8 grid grid-cols-5 gap-3 md:gap-4">
                <div className="flex flex-col items-center gap-2">
                  <div className="h-10 w-10 md:h-12 md:w-12 rounded-full bg-white/5 ring-1 ring-white/10 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white/60">
                      <path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z" />
                      <path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65" />
                      <path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65" />
                    </svg>
                  </div>
                  <span className="text-[10px] md:text-xs text-white/60">Clustering</span>
                </div>
                <div className="flex flex-col items-center gap-2">
                  <div className="h-10 w-10 md:h-12 md:w-12 rounded-full bg-white/5 ring-1 ring-white/10 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white/60">
                      <path d="M3 3v16a2 2 0 0 0 2 2h16" />
                      <path d="m19 9-5 5-4-4-3 3" />
                    </svg>
                  </div>
                  <span className="text-[10px] md:text-xs text-white/60">Analysis</span>
                </div>
                <div className="flex flex-col items-center gap-2">
                  <div className="h-10 w-10 md:h-12 md:w-12 rounded-full bg-white/5 ring-1 ring-white/10 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white/60">
                      <circle cx="12" cy="12" r="10" />
                      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
                      <path d="M12 17h.01" />
                    </svg>
                  </div>
                  <span className="text-[10px] md:text-xs text-white/60">Patterns</span>
                </div>
                <div className="flex flex-col items-center gap-2">
                  <div className="h-10 w-10 md:h-12 md:w-12 rounded-full bg-white/5 ring-1 ring-white/10 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white/60">
                      <path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5" />
                      <path d="M9 18h6" />
                      <path d="M10 22h4" />
                    </svg>
                  </div>
                  <span className="text-[10px] md:text-xs text-white/60">Insights</span>
                </div>
                <div className="flex flex-col items-center gap-2">
                  <div className="h-10 w-10 md:h-12 md:w-12 rounded-full bg-white/5 ring-1 ring-white/10 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-emerald-300">
                      <circle cx="12" cy="12" r="10" />
                      <circle cx="12" cy="12" r="6" />
                      <circle cx="12" cy="12" r="2" />
                    </svg>
                  </div>
                  <span className="text-[10px] md:text-xs text-white/60">Context</span>
                </div>
              </div>
            </div>
          </div>

          {/* Feature 3: Act */}
          <div className="relative ring-1 ring-white/10 p-6 md:p-8 shadow-[0_10px_40px_-10px_rgba(0,0,0,0.6)] overflow-hidden rounded-2xl group hover:ring-emerald-500/30 transition-all">
            <div className="absolute -left-10 -bottom-16 h-64 w-64 bg-gradient-to-tr from-emerald-400/20 to-emerald-300/5 rounded-full blur-2xl group-hover:opacity-80 opacity-50 transition-opacity" />
            <div className="relative">
              <div className="flex items-center gap-3 mb-6">
                <div className="h-10 w-10 rounded-xl bg-white/5 ring-1 ring-white/10 flex items-center justify-center group-hover:ring-emerald-500/30 transition-all">
                  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-emerald-300">
                    <path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z" />
                  </svg>
                </div>
                <h3 className="text-2xl md:text-3xl font-semibold tracking-tight text-white">Act</h3>
              </div>
              <p className="text-white/70 leading-relaxed">
                Generates code fixes and opens Pull Requests automatically. Review and merge with confidence.
              </p>
              <div className="mt-8 grid grid-cols-5 gap-3 md:gap-4">
                <div className="flex flex-col items-center gap-2">
                  <div className="h-10 w-10 md:h-12 md:w-12 rounded-full bg-white/5 ring-1 ring-white/10 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white/60">
                      <rect width="18" height="18" x="3" y="3" rx="2" />
                      <path d="M3 9h18" />
                      <path d="M9 21V9" />
                    </svg>
                  </div>
                  <span className="text-[10px] md:text-xs text-white/60">Automated</span>
                </div>
                <div className="flex flex-col items-center gap-2">
                  <div className="h-10 w-10 md:h-12 md:w-12 rounded-full bg-white/5 ring-1 ring-white/10 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white/60">
                      <circle cx="12" cy="12" r="10" />
                      <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
                      <path d="M2 12h20" />
                    </svg>
                  </div>
                  <span className="text-[10px] md:text-xs text-white/60">Precise</span>
                </div>
                <div className="flex flex-col items-center gap-2">
                  <div className="h-10 w-10 md:h-12 md:w-12 rounded-full bg-white/5 ring-1 ring-white/10 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white/60">
                      <path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" />
                    </svg>
                  </div>
                  <span className="text-[10px] md:text-xs text-white/60">Fast</span>
                </div>
                <div className="flex flex-col items-center gap-2">
                  <div className="h-10 w-10 md:h-12 md:w-12 rounded-full bg-white/5 ring-1 ring-white/10 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white/60">
                      <path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z" />
                      <path d="m9 12 2 2 4-4" />
                    </svg>
                  </div>
                  <span className="text-[10px] md:text-xs text-white/60">Reliable</span>
                </div>
                <div className="flex flex-col items-center gap-2">
                  <div className="h-10 w-10 md:h-12 md:w-12 rounded-full bg-white/5 ring-1 ring-white/10 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-emerald-300">
                      <path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z" />
                      <path d="m9 12 2 2 4-4" />
                    </svg>
                  </div>
                  <span className="text-[10px] md:text-xs text-white/60">Verified</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      </div>
    </>
  );
}
