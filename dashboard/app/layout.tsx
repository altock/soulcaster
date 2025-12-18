import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import UnicornBackground from '@/components/UnicornBackground';
import SessionProvider from '@/components/SessionProvider';
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
        <SessionProvider>
          <UnicornBackground />
          <div className="min-h-screen relative z-10">{children}</div>
        </SessionProvider>
      </body>
    </html>
  );
}
