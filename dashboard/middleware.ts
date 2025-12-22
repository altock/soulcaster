import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { getToken } from 'next-auth/jwt';

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Public routes that don't require authentication or consent
  const publicPaths = [
    '/api/auth',
    '/auth/signin',
    '/consent',
    '/api/consent',
    '/privacy',
    '/_next',
    '/favicon.ico',
  ];

  // Allow public paths
  if (publicPaths.some((path) => pathname.startsWith(path))) {
    return NextResponse.next();
  }

  // Check if user is authenticated
  const token = await getToken({ req: request, secret: process.env.NEXTAUTH_SECRET });

  if (!token) {
    // Not authenticated, redirect to sign in
    const url = request.nextUrl.clone();
    url.pathname = '/auth/signin';
    return NextResponse.redirect(url);
  }

  // Check if user has consented (only redirect on new login or if explicitly not consented)
  const hasConsented = token.consentedToResearch === true;
  const isNewLogin = token.isNewLogin === true;

  // Only redirect to consent if:
  // 1. User hasn't consented AND
  // 2. It's a new login session (just authenticated) AND
  // 3. Not already on consent page
  if (!hasConsented && isNewLogin && pathname !== '/consent' && pathname.startsWith('/dashboard')) {
    const url = request.nextUrl.clone();
    url.pathname = '/consent';
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    '/((?!_next/static|_next/image|favicon.ico).*)',
  ],
};
