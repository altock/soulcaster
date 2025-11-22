import type { Metadata } from 'next';
import Link from 'next/link';
import './globals.css';

export const metadata: Metadata = {
  title: 'FeedbackAgent Dashboard',
  description: 'Self-healing dev loop triage dashboard',
};

/**
 * Provides the root HTML layout for the FeedbackAgent dashboard.
 *
 * Renders the document scaffold including <html lang="en">, a styled <body>, a header with the dashboard title, and a main content area that hosts `children`.
 *
 * @param children - The React node(s) to render inside the main content area
 * @returns The root JSX element representing the dashboard layout
 */
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="antialiased bg-gray-50">
        <div className="min-h-screen">
          <header className="bg-white shadow-sm border-b">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
              <Link href="/" className="text-2xl font-bold text-gray-900 hover:text-gray-700 transition-colors">
                FeedbackAgent
              </Link>
              <nav>
                <Link 
                  href="/clusters" 
                  className="text-sm font-medium text-gray-500 hover:text-gray-900 transition-colors"
                >
                  Dashboard
                </Link>
              </nav>
            </div>
          </header>
          <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
