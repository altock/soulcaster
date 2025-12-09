import { getServerSession } from 'next-auth';
import GitHub from 'next-auth/providers/github';
import { PrismaAdapter } from '@auth/prisma-adapter';
import { prisma } from '@/lib/prisma';
import type { NextAuthOptions } from 'next-auth';
import type { Adapter } from 'next-auth/adapters';

/**
 * Ensure the specified user has a default project; create and assign one if missing.
 *
 * @param userId - The user's ID to ensure a default project for
 * @returns The ID of the user's default project
 */
async function ensureDefaultProject(userId: string): Promise<string> {
  return prisma.$transaction(async (tx) => {
    // Ensure the user row exists (DB might be freshly reset)
    const user = await tx.user.upsert({
      where: { id: userId },
      update: {},
      create: { id: userId },
      select: { defaultProjectId: true, id: true },
    });

    // If a default already exists, return it immediately
    if (user?.defaultProjectId) {
      return user.defaultProjectId;
    }

    // Re-check inside the same transaction to avoid racing creations
    const existingDefault = await tx.user.findUnique({
      where: { id: userId },
      select: { defaultProjectId: true },
    });

    if (existingDefault?.defaultProjectId) {
      return existingDefault.defaultProjectId;
    }

    // Create a default project for the user and set it
    const project = await tx.project.create({
      data: {
        name: 'Default Project',
        userId: user.id,
      },
    });

    const updatedUser = await tx.user.update({
      where: { id: userId },
      data: { defaultProjectId: project.id },
      select: { defaultProjectId: true },
    });

    return updatedUser.defaultProjectId ?? project.id;
  });
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
        const maxAttempts = 3;
        for (let attempt = 1; attempt <= maxAttempts; attempt++) {
          try {
            const projectId = await ensureDefaultProject(token.sub);
            token.projectId = projectId;
            break;
          } catch (error) {
            const backoffMs = 100 * 2 ** (attempt - 1);
            console.error('Failed to ensure default project', {
              attempt,
              userId: token.sub,
              error,
            });

            if (attempt === maxAttempts) {
              throw new Error(
                'We could not set up your default project. Please try signing in again.'
              );
            }

            await new Promise((resolve) => setTimeout(resolve, backoffMs));
          }
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