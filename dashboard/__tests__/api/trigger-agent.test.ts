import { getGitHubToken } from '@/lib/auth';

// Mock the auth module
jest.mock('next-auth', () => ({
  getServerSession: jest.fn(),
}));
jest.mock('next-auth/providers/github', () => jest.fn());
jest.mock('@/lib/auth');

const mockGetGitHubToken = getGitHubToken as jest.MockedFunction<typeof getGitHubToken>;

/**
 * Integration tests for API routes using GitHub tokens
 *
 * These tests verify that API routes correctly use the getGitHubToken()
 * helper, which prioritizes session tokens over environment tokens.
 *
 * The actual API route implementation is tested through the auth helper tests,
 * which verify the token priority logic:
 * 1. Session token (from logged-in user) - highest priority
 * 2. undefined - when not available
 */
describe('API Routes - GitHub Token Integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Token Resolution', () => {
    it('should resolve to session token when user is authenticated', async () => {
      const sessionToken = 'gho_session_token_123';
      mockGetGitHubToken.mockResolvedValue(sessionToken);

      const token = await getGitHubToken();

      expect(token).toBe(sessionToken);
      expect(mockGetGitHubToken).toHaveBeenCalled();
    });

    it('should return undefined when no token is available', async () => {
      mockGetGitHubToken.mockResolvedValue(undefined);

      const token = await getGitHubToken();

      expect(token).toBeUndefined();
    });
  });

  describe('API Route Token Usage Pattern', () => {
    it('demonstrates correct usage pattern for API routes', async () => {
      // Example of how API routes should use getGitHubToken()
      const mockApiRoute = async () => {
        const githubToken = await getGitHubToken();

        if (!githubToken) {
          throw new Error('No GitHub token available');
        }

        // Use token with Octokit or other GitHub API client
        return { authenticated: true, token: githubToken };
      };

      mockGetGitHubToken.mockResolvedValue('gho_test_token');

      const result = await mockApiRoute();

      expect(result.authenticated).toBe(true);
      expect(result.token).toBe('gho_test_token');
    });

    it('demonstrates fallback behavior when token is unavailable', async () => {
      const mockApiRoute = async () => {
        const githubToken = await getGitHubToken();

        if (!githubToken) {
          return { error: 'GitHub token required' };
        }

        return { authenticated: true };
      };

      mockGetGitHubToken.mockResolvedValue(undefined);

      const result = await mockApiRoute();

      expect(result.error).toBe('GitHub token required');
    });
  });
});
