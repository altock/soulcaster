import Link from 'next/link';

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
  activePage = 'home',
  rightContent,
  className = '',
}: DashboardHeaderProps) {
  const getFeedbackLinkClass = () => {
    const baseClass =
      'px-4 py-2 text-sm font-medium rounded-md transition-colors';
    return activePage === 'feedback'
      ? `${baseClass} text-blue-600 bg-blue-50`
      : `${baseClass} text-gray-600 hover:text-gray-900 hover:bg-gray-100`;
  };

  const getClustersLinkClass = () => {
    const baseClass =
      'px-4 py-2 text-sm font-medium rounded-md transition-colors';
    return activePage === 'clusters'
      ? `${baseClass} text-blue-600 bg-blue-50`
      : `${baseClass} text-gray-600 hover:text-gray-900 hover:bg-gray-100`;
  };

  return (
    <div
      className={`bg-white shadow-sm border-b border-gray-200 ${className}`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div
          className={`flex items-center ${rightContent ? 'justify-between' : 'gap-4'}`}
        >
          <div className="flex items-center gap-4">
            <Link href="/" className="text-2xl font-bold text-blue-600">
              FeedbackAgent
            </Link>
            <nav className="flex gap-1" aria-label="Main navigation">
              <Link
                href="/feedback"
                className={getFeedbackLinkClass()}
                aria-current={activePage === 'feedback' ? 'page' : undefined}
              >
                Feedback
              </Link>
              <Link
                href="/clusters"
                className={getClustersLinkClass()}
                aria-current={activePage === 'clusters' ? 'page' : undefined}
              >
                Clusters
              </Link>
            </nav>
          </div>
          {rightContent && <div>{rightContent}</div>}
        </div>
      </div>
    </div>
  );
}

