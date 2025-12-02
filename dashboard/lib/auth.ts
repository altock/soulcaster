import { getServerSession } from 'next-auth';
import GitHub from 'next-auth/providers/github';
import { PrismaAdapter } from '@auth/prisma-adapter';
import { prisma } from '@/lib/prisma';
import type { NextAuthOptions } from 'next-auth';
import type { Adapter } from 'next-auth/adapters';

export const authOptions: NextAuthOptions = {
  adapter: PrismaAdapter(prisma) as Adapter,
  session: {
    strategy: 'jwt', // Use JWT strategy even with database adapter to keep session stateless if preferred, or remove for database sessions
  },
  providers: [
    GitHub({
      clientId: process.env.GITHUB_ID!,
      clientSecret: process.env.GITHUB_SECRET!,
      authorization: {
        params: {
          scope: 'repo read:user',
        },
      },
    }),
  ],
  callbacks: {
    async jwt({ token, account }) {
      // Persist the OAuth access_token to the token right after signin
      if (account) {
        token.accessToken = account.access_token;
      }
      return token;
    },
    async session({ session, token }) {
      // Send properties to the client
      session.accessToken = token.accessToken as string;
      if (session.user && token.sub) {
        session.user.id = token.sub;
      }
      return session;
    },
  },
  pages: {
    signIn: '/auth/signin',
  },
};

/**
 * Gets the GitHub access token for API calls.
 * Priority: User's session token > Environment variable GITHUB_TOKEN
 *
 * @returns GitHub access token or undefined if neither is available
 */
export async function getGitHubToken(): Promise<string | undefined> {
  try {
    const session = await getServerSession(authOptions);
    if (session?.accessToken) {
      return session.accessToken;
    }
  } catch (error) {
    console.warn('Failed to get session:', error);
  }

  // Fallback to environment variable
  // return process.env.GITHUB_TOKEN;
  return undefined;
}

/**
 * Checks if a user is authenticated via session
 */
export async function isAuthenticated(): Promise<boolean> {
  try {
    const session = await getServerSession(authOptions);
    return !!session?.accessToken;
  } catch {
    return false;
  }
}
