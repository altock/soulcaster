import Link from 'next/link';

export default function LandingPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[80vh]">
      {/* Hero Section */}
      <div className="text-center max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-20">
        <h1 className="text-4xl sm:text-6xl font-extrabold text-gray-900 tracking-tight mb-6">
          <span className="block">FeedbackAgent</span>
          <span className="block text-blue-600 mt-2">The Self-Healing Dev Loop</span>
        </h1>
        <p className="mt-4 text-xl text-gray-600 max-w-2xl mx-auto">
          Automate your bug triage and fixing workflow. From user report to pull request in minutes, not days.
        </p>
        <div className="mt-10 flex justify-center gap-4">
          <Link
            href="/feedback"
            className="px-8 py-3 border border-transparent text-base font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 md:py-4 md:text-lg md:px-10 shadow-lg transition-all hover:scale-105"
          >
            Enter Dashboard
          </Link>
          <a
            href="https://github.com/altock/soulcaster"
            target="_blank"
            rel="noopener noreferrer"
            className="px-8 py-3 border border-gray-300 text-base font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 md:py-4 md:text-lg md:px-10 shadow-sm transition-all hover:scale-105"
          >
            View on GitHub
          </a>
        </div>
      </div>

      {/* Features Grid */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Feature 1: Listen */}
          <div className="bg-white p-6 rounded-xl shadow-md border border-gray-100 hover:shadow-lg transition-shadow">
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4 text-2xl">
              👂
            </div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">Listen</h3>
            <p className="text-gray-600">
              Automatically ingests feedback from Reddit communities and Sentry error reports in real-time.
            </p>
          </div>

          {/* Feature 2: Think */}
          <div className="bg-white p-6 rounded-xl shadow-md border border-gray-100 hover:shadow-lg transition-shadow">
            <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center mb-4 text-2xl">
              🧠
            </div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">Think</h3>
            <p className="text-gray-600">
              Intelligent agents cluster related issues, summarize the problem, and identify the root cause.
            </p>
          </div>

          {/* Feature 3: Act */}
          <div className="bg-white p-6 rounded-xl shadow-md border border-gray-100 hover:shadow-lg transition-shadow">
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mb-4 text-2xl">
              ⚡
            </div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">Act</h3>
            <p className="text-gray-600">
              Generates code fixes and opens Pull Requests automatically. Review and merge with confidence.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
