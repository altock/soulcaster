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
          <div className="bg-matrix-card p-8 rounded-2xl shadow-lg border border-matrix-border hover:border-matrix-green transition-all group hover:shadow-card-hover">
            <div className="w-14 h-14 bg-matrix-green-dim rounded-xl flex items-center justify-center mb-6 text-3xl group-hover:shadow-neon-green transition-shadow border border-matrix-green/20">
              👂
            </div>
            <h3 className="text-xl font-bold text-white mb-3 group-hover:text-matrix-green transition-colors">Listen</h3>
            <p className="text-gray-400 leading-relaxed">
              Automatically ingests feedback from Reddit communities and GitHub issues in
              real-time.
            </p>
          </div>

          {/* Feature 2: Think */}
          <div className="bg-matrix-card p-8 rounded-2xl shadow-lg border border-matrix-border hover:border-matrix-green transition-all group hover:shadow-card-hover">
            <div className="w-14 h-14 bg-matrix-green-dim rounded-xl flex items-center justify-center mb-6 text-3xl group-hover:shadow-neon-green transition-shadow border border-matrix-green/20">
              🧠
            </div>
            <h3 className="text-xl font-bold text-white mb-3 group-hover:text-matrix-green transition-colors">Think</h3>
            <p className="text-gray-400 leading-relaxed">
              Intelligent agents cluster related issues, summarize the problem, and identify the
              root cause.
            </p>
          </div>

          {/* Feature 3: Act */}
          <div className="bg-matrix-card p-8 rounded-2xl shadow-lg border border-matrix-border hover:border-matrix-green transition-all group hover:shadow-card-hover">
            <div className="w-14 h-14 bg-matrix-green-dim rounded-xl flex items-center justify-center mb-6 text-3xl group-hover:shadow-neon-green transition-shadow border border-matrix-green/20">
              ⚡
            </div>
            <h3 className="text-xl font-bold text-white mb-3 group-hover:text-matrix-green transition-colors">Act</h3>
            <p className="text-gray-400 leading-relaxed">
              Generates code fixes and opens Pull Requests automatically. Review and merge with
              confidence.
            </p>
          </div>
        </div>
      </div>
      </div>
    </>
  );
}
