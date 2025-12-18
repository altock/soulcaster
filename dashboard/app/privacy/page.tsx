import Link from 'next/link';

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto">
        <div className="bg-white shadow rounded-lg p-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-6">Privacy Policy</h1>
          <p className="text-sm text-gray-500 mb-8">Last updated: December 15, 2025</p>

          <div className="prose prose-blue max-w-none">
            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Introduction</h2>
              <p className="text-gray-700 mb-4">
                Soulcaster is an automated feedback triage and code fix generation system currently in
                beta. This Privacy Policy explains how we collect, use, and protect your information
                when you use our service.
              </p>
              <p className="text-gray-700">
                By using Soulcaster, you agree to the collection and use of information in accordance
                with this policy.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">
                Information We Collect
              </h2>

              <h3 className="text-xl font-semibold text-gray-800 mb-3">1. GitHub Account Information</h3>
              <p className="text-gray-700 mb-3">
                When you sign in with GitHub OAuth, we collect:
              </p>
              <ul className="list-disc list-inside text-gray-700 mb-4 ml-4 space-y-1">
                <li>Your GitHub username</li>
                <li>Your email address</li>
                <li>Your profile information (name, avatar)</li>
                <li>An OAuth access token with <code className="bg-gray-100 px-1 py-0.5 rounded">repo</code> and <code className="bg-gray-100 px-1 py-0.5 rounded">read:user</code> scopes</li>
              </ul>

              <h3 className="text-xl font-semibold text-gray-800 mb-3">2. Repository Access</h3>
              <p className="text-gray-700 mb-3">
                With your authorization, Soulcaster accesses:
              </p>
              <ul className="list-disc list-inside text-gray-700 mb-4 ml-4 space-y-1">
                <li>Repository code (to analyze issues and generate fixes)</li>
                <li>Repository metadata (branches, commits, pull requests)</li>
                <li>Issue and feedback data you choose to ingest</li>
              </ul>

              <h3 className="text-xl font-semibold text-gray-800 mb-3">3. Usage Data</h3>
              <p className="text-gray-700 mb-4">
                We collect data about how you use Soulcaster, including:
              </p>
              <ul className="list-disc list-inside text-gray-700 mb-4 ml-4 space-y-1">
                <li>Feedback items you ingest from Reddit, Sentry, or GitHub</li>
                <li>Clusters you create and fix attempts you trigger</li>
                <li>Job logs and status (for debugging and improving the service)</li>
              </ul>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">How We Use Your Information</h2>
              <p className="text-gray-700 mb-3">We use your information to:</p>
              <ul className="list-disc list-inside text-gray-700 mb-4 ml-4 space-y-2">
                <li>
                  <strong>Provide the service:</strong> Analyze feedback, generate code fixes, and
                  create pull requests on your behalf
                </li>
                <li>
                  <strong>Authenticate you:</strong> Verify your identity using GitHub OAuth
                </li>
                <li>
                  <strong>Create PRs from your account:</strong> Pull requests are opened using your
                  GitHub credentials, showing your name as the author (e.g., @yourname)
                </li>
                <li>
                  <strong>Improve the service:</strong> Analyze usage patterns to enhance Soulcaster&apos;s
                  functionality
                </li>
              </ul>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Data Storage and Security</h2>
              <div className="space-y-4">
                <div>
                  <h3 className="text-lg font-semibold text-gray-800 mb-2">Token Storage</h3>
                  <p className="text-gray-700">
                    Your GitHub OAuth access token is stored securely using NextAuth.js with
                    encryption. Tokens are stored in:
                  </p>
                  <ul className="list-disc list-inside text-gray-700 mt-2 ml-4 space-y-1">
                    <li>Encrypted JWT session cookies (in your browser)</li>
                    <li>Never logged or exposed in plain text</li>
                    <li>Passed to our backend only when needed to create PRs</li>
                  </ul>
                </div>

                <div>
                  <h3 className="text-lg font-semibold text-gray-800 mb-2">Data Persistence</h3>
                  <p className="text-gray-700">
                    We store:
                  </p>
                  <ul className="list-disc list-inside text-gray-700 mt-2 ml-4 space-y-1">
                    <li>Feedback items and clusters in Redis (encrypted in transit)</li>
                    <li>User account data in PostgreSQL</li>
                    <li>Job logs temporarily for debugging (auto-expire after 30 days)</li>
                  </ul>
                </div>

                <div>
                  <h3 className="text-lg font-semibold text-gray-800 mb-2">Code Access</h3>
                  <p className="text-gray-700">
                    <strong>We do not permanently store your repository code.</strong> Code is:
                  </p>
                  <ul className="list-disc list-inside text-gray-700 mt-2 ml-4 space-y-1">
                    <li>Read temporarily in E2B sandboxes during fix generation</li>
                    <li>Processed in isolated, ephemeral environments</li>
                    <li>Deleted when the job completes</li>
                    <li>Never used to train machine learning models</li>
                  </ul>
                </div>
              </div>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Third-Party Services</h2>
              <p className="text-gray-700 mb-3">
                Soulcaster integrates with the following third-party services:
              </p>
              <ul className="list-disc list-inside text-gray-700 mb-4 ml-4 space-y-2">
                <li>
                  <strong>GitHub:</strong> For authentication and repository access
                  (<a href="https://docs.github.com/en/site-policy/privacy-policies/github-privacy-statement" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Privacy Policy</a>)
                </li>
                <li>
                  <strong>E2B:</strong> For secure sandbox execution of code generation
                  (<a href="https://e2b.dev/privacy" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Privacy Policy</a>)
                </li>
                <li>
                  <strong>Google Gemini:</strong> For LLM-powered embeddings and code generation
                  (<a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Privacy Policy</a>)
                </li>
                <li>
                  <strong>Upstash Redis:</strong> For data storage
                  (<a href="https://upstash.com/privacy" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Privacy Policy</a>)
                </li>
              </ul>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Your Rights and Choices</h2>
              <div className="space-y-3">
                <div>
                  <h3 className="text-lg font-semibold text-gray-800 mb-2">Revoke Access</h3>
                  <p className="text-gray-700">
                    You can revoke Soulcaster&apos;s access to your GitHub account at any time in your{' '}
                    <a
                      href="https://github.com/settings/applications"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline"
                    >
                      GitHub Settings → Applications
                    </a>
                    . This will immediately invalidate your OAuth token.
                  </p>
                </div>

                <div>
                  <h3 className="text-lg font-semibold text-gray-800 mb-2">Delete Your Data</h3>
                  <p className="text-gray-700">
                    To request deletion of your data, please contact us. We will delete:
                  </p>
                  <ul className="list-disc list-inside text-gray-700 mt-2 ml-4 space-y-1">
                    <li>Your user account and profile information</li>
                    <li>All feedback items and clusters you created</li>
                    <li>Job logs and execution history</li>
                  </ul>
                </div>

                <div>
                  <h3 className="text-lg font-semibold text-gray-800 mb-2">Data Portability</h3>
                  <p className="text-gray-700">
                    You can export your data at any time through the dashboard or by contacting us.
                  </p>
                </div>
              </div>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Beta Notice</h2>
              <p className="text-gray-700 mb-3">
                <strong>Soulcaster is currently in beta.</strong> This means:
              </p>
              <ul className="list-disc list-inside text-gray-700 mb-4 ml-4 space-y-2">
                <li>Features and data practices may change as we develop the service</li>
                <li>We may reset or migrate data during major updates</li>
                <li>We recommend testing on non-production repositories initially</li>
              </ul>
              <p className="text-gray-700">
                We will notify users of any significant changes to this Privacy Policy via email or
                through the dashboard.
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Future Changes</h2>
              <p className="text-gray-700 mb-3">
                <strong>GitHub App Support Coming Soon:</strong> We plan to offer GitHub App
                installation as an alternative to OAuth. This will allow:
              </p>
              <ul className="list-disc list-inside text-gray-700 mb-4 ml-4 space-y-1">
                <li>Bot-based PRs (soulcaster[bot]) instead of user-attributed PRs</li>
                <li>Fine-grained repository permissions</li>
                <li>Organization-wide installations</li>
              </ul>
              <p className="text-gray-700">
                When available, users will be able to choose between OAuth (personal PRs) or GitHub
                App (bot PRs).
              </p>
            </section>

            <section className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Contact Us</h2>
              <p className="text-gray-700">
                If you have questions or concerns about this Privacy Policy or how we handle your
                data, please contact us at:
              </p>
              <p className="text-gray-700 mt-3">
                <strong>Email:</strong>{' '}
                <a href="mailto:support@soulcaster.dev" className="text-blue-600 hover:underline">
                  support@soulcaster.dev
                </a>
                <br />
                <strong>GitHub:</strong>{' '}
                <a
                  href="https://github.com/altock/soulcaster/issues"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline"
                >
                  github.com/altock/soulcaster/issues
                </a>
              </p>
            </section>
          </div>

          <div className="mt-8 pt-8 border-t border-gray-200">
            <Link
              href="/"
              className="text-blue-600 hover:text-blue-800 font-medium flex items-center"
            >
              <svg
                className="w-4 h-4 mr-2"
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path d="M10 19l-7-7m0 0l7-7m-7 7h18"></path>
              </svg>
              Back to Dashboard
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
