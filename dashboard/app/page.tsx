import Link from 'next/link';
import LandingHeader from '@/components/LandingHeader';
import Footer from '@/components/Footer';

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
            </div>
          </div>
        </div>
      </div>
      </div>
      <Footer />
    </>
  );
}
