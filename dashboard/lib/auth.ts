import { getServerSession } from 'next-auth';
import GitHub from 'next-auth/providers/github';
import { Prisma } from '@prisma/client';
import { PrismaAdapter } from '@auth/prisma-adapter';
import { prisma } from '@/lib/prisma';
import type { NextAuthOptions } from 'next-auth';
import type { Adapter } from 'next-auth/adapters';

// Explicit type for the transaction client to satisfy $transaction callback
type TransactionClient = Prisma.TransactionClient;

/**
 * Ensure the specified user has a default project; create and assign one if missing.
 *
 * @param userId - The user's ID to ensure a default project for
 * @returns The ID of the user's default project
 */
async function ensureDefaultProject(userId: string): Promise<string> {
  const result = await prisma.$transaction(async (tx: TransactionClient) => {
    // Ensure the user row exists (DB might be freshly reset)
    const user = await tx.user.upsert({
      where: { id: userId },
      update: {},
      create: { id: userId },
      select: { defaultProjectId: true, id: true },
    });

    // If a default already exists, return it immediately
    if (user?.defaultProjectId) {
      return { projectId: user.defaultProjectId, isNew: false };
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

    return { projectId: updatedUser.defaultProjectId ?? project.id, isNew: true };
  }, {
    timeout: 15000, // 15 seconds (default is 5s)
  });

  // Always ensure project exists in backend Redis (handles Redis wipes/resets)
  try {
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';

    // First check if project exists in backend
    const checkResponse = await fetch(`${backendUrl}/projects?user_id=${userId}`, {
      method: 'GET',
    });

    // Check response body, not just HTTP status (200 with empty array means no projects)
    let projectExists = false;
    if (checkResponse.ok) {
      const data = await checkResponse.json();
      projectExists = data?.projects?.length > 0;
    }

    // If project doesn't exist in backend, sync it
    if (!projectExists || result.isNew) {
      const response = await fetch(`${backendUrl}/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: result.projectId,  // Send the project's ID from Prisma
          user_id: userId,               // Send the user's ID
          name: 'Default Project',
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Failed to sync project to backend:', {
          status: response.status,
          statusText: response.statusText,
          body: errorText,
          userId,
        });
      } else {
        console.log('Successfully synced project to backend Redis:', result.projectId);
      }
    }
  } catch (error) {
    // Don't fail the login if backend sync fails - just log it
    console.error('Failed to sync project to backend (non-blocking):', error);
  }

  return result.projectId;
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
    async jwt({ token, account, user, trigger }) {
      // Persist the OAuth access_token to the token right after signin
      if (account) {
        token.accessToken = account.access_token;
        // Mark as new login for consent check
        token.isNewLogin = true;
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

        // Fetch consent status and add to token
        // Update only on first load (undefined) or when explicitly triggered
        if (trigger === 'update' || token.consentedToResearch === undefined) {
          try {
            const userData = await prisma.user.findUnique({
              where: { id: token.sub },
              select: { consentedToResearch: true },
            });
            token.consentedToResearch = userData?.consentedToResearch ?? false;
          } catch (error) {
            console.error('Failed to fetch consent status', error);
            token.consentedToResearch = false;
          }
        }

        // Clear isNewLogin flag after first check (to avoid persistent redirect)
        if (token.isNewLogin && token.consentedToResearch) {
          delete token.isNewLogin;
        }
      }

      return token;
    },
    async session({ session, token }) {
      // Send properties to the client
      if (typeof token.accessToken === 'string') {
        session.accessToken = token.accessToken;
      }
      if (typeof token.projectId === 'string') {
        session.projectId = token.projectId;
      }
      if (session.user && token.sub) {
        session.user.id = token.sub;
      }
      if (typeof token.consentedToResearch === 'boolean') {
        session.consentedToResearch = token.consentedToResearch;
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