import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';

/**
 * Return diagnostic information about the current server session.
 *
 * @returns A JSON object with:
 * - `authenticated`: `true` if a session exists, `false` otherwise.
 * - `hasAccessToken`: `true` if the session contains an access token, `false` otherwise.
 * - `user`: the session user's email, or `undefined` if not present.
 * - `tokenLength`: the length of the access token string, or `0` if absent.
 */
export async function GET() {
  try {
    const session = await getServerSession(authOptions);
    return NextResponse.json({
      authenticated: !!session,
      hasAccessToken: !!session?.accessToken,
      user: session?.user?.email,
      tokenLength: session?.accessToken?.length || 0,
    });
  } catch (error) {
    return NextResponse.json({ error: 'Failed to get session' }, { status: 500 });
  }
}