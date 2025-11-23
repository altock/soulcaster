import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import Link from 'next/link';
import UnicornBackground from '@/components/UnicornBackground';
import './globals.css';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

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
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased text-white font-sans`}>
        <UnicornBackground />
        <div className="min-h-screen relative z-10">
          <header className="bg-matrix-black border-b border-matrix-border sticky top-0 z-50 backdrop-blur-md bg-opacity-80">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
              <Link
                href="/"
                className="text-2xl font-bold text-white hover:text-matrix-green transition-colors tracking-tighter flex items-center gap-2"
              >
                <span className="text-matrix-green drop-shadow-[0_0_10px_rgba(0,255,148,0.8)]">Soulcaster</span>
              </Link>
              <nav className="flex gap-6">
                <Link
                  href="/clusters"
                  className="text-sm font-medium text-gray-400 hover:text-matrix-green transition-colors uppercase tracking-wider"
                >
                  Dashboard
                </Link>
                <Link
                  href="/feedback"
                  className="text-sm font-medium text-gray-400 hover:text-matrix-green transition-colors uppercase tracking-wider"
                >
                  Feedback
                </Link>
              </nav>
            </div>
          </header>
          <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
