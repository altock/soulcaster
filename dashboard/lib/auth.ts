import { getServerSession } from 'next-auth';
import GitHub from 'next-auth/providers/github';
import { PrismaAdapter } from '@auth/prisma-adapter';
import { prisma } from '@/lib/prisma';
import type { NextAuthOptions } from 'next-auth';
import type { Adapter } from 'next-auth/adapters';

/**
 * Ensures a user has a default project. Creates one if it doesn't exist.
 * Returns the default project ID.
 */
async function ensureDefaultProject(userId: string): Promise<string> {
  // Ensure the user row exists (DB might be freshly reset)
  const user = await prisma.user.upsert({
    where: { id: userId },
    update: {},
    create: { id: userId },
    select: { defaultProjectId: true, id: true },
  });

  if (user?.defaultProjectId) {
    return user.defaultProjectId;
  }

  // Create a default project for the user
  const project = await prisma.project.create({
    data: {
      name: 'Default Project',
      userId: user.id,
    },
  });

  // Set it as the user's default project
  await prisma.user.update({
    where: { id: userId },
    data: { defaultProjectId: project.id },
  });

  return project.id;
}

export const authOptions: NextAuthOptions = {
  adapter: PrismaAdapter(prisma) as Adapter,
  session: {
    strategy: 'jwt',
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
    async jwt({ token, account, user }) {
      // Persist the OAuth access_token to the token right after signin
      if (account) {
        token.accessToken = account.access_token;
      }

      // Ensure user has a default project and add projectId to token
      if (token.sub) {
        try {
          const projectId = await ensureDefaultProject(token.sub);
          token.projectId = projectId;
        } catch (error) {
          console.error('Failed to ensure default project:', error);
        }
      }

      return token;
    },
    async session({ session, token }) {
      // Send properties to the client
      session.accessToken = token.accessToken as string;
      session.projectId = token.projectId as string;
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
 * Retrieve the GitHub access token from the current server session, if present.
 *
 * @returns The GitHub access token when available from the session, `undefined` otherwise.
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