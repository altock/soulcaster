// Mock next-auth BEFORE imports
jest.mock('next-auth', () => ({
  getServerSession: jest.fn(),
  default: jest.fn(),
}));

jest.mock('next-auth/providers/github', () => {
  return {
    __esModule: true,
    default: jest.fn(() => ({
      id: 'github',
      name: 'GitHub',
      type: 'oauth',
    })),
  };
});

import { getGitHubToken, isAuthenticated } from '@/lib/auth';
import { getServerSession } from 'next-auth';

describe('Auth Helper', () => {
  const mockGetServerSession = getServerSession as jest.MockedFunction<typeof getServerSession>;

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('getGitHubToken', () => {
    it('should return session access token when user is authenticated', async () => {
      const mockAccessToken = 'gho_sessiontoken123';
      mockGetServerSession.mockResolvedValue({
        accessToken: mockAccessToken,
        expires: '2024-12-31',
        user: { name: 'Test User', email: 'test@example.com' },
      });

      const token = await getGitHubToken();
      expect(token).toBe(mockAccessToken);
    });

    it('should return undefined when session is null', async () => {
      mockGetServerSession.mockResolvedValue(null);

      const token = await getGitHubToken();
      expect(token).toBeUndefined();
    });

    it('should return undefined when session has no accessToken', async () => {
      mockGetServerSession.mockResolvedValue({
        expires: '2024-12-31',
        user: { name: 'Test User', email: 'test@example.com' },
      });

      const token = await getGitHubToken();
      expect(token).toBeUndefined();
    });

    it('should return undefined when getServerSession throws error', async () => {
      mockGetServerSession.mockRejectedValue(new Error('Session error'));

      const token = await getGitHubToken();
      expect(token).toBeUndefined();
    });
  });

  describe('isAuthenticated', () => {
    it('should return true when session has access token', async () => {
      mockGetServerSession.mockResolvedValue({
        accessToken: 'gho_token123',
        expires: '2024-12-31',
        user: { name: 'Test User', email: 'test@example.com' },
      });

      const result = await isAuthenticated();
      expect(result).toBe(true);
    });

    it('should return false when session is null', async () => {
      mockGetServerSession.mockResolvedValue(null);

      const result = await isAuthenticated();
      expect(result).toBe(false);
    });

    it('should return false when session has no access token', async () => {
      mockGetServerSession.mockResolvedValue({
        expires: '2024-12-31',
        user: { name: 'Test User', email: 'test@example.com' },
      });

      const result = await isAuthenticated();
      expect(result).toBe(false);
    });

    it('should return false when getServerSession throws error', async () => {
      mockGetServerSession.mockRejectedValue(new Error('Session error'));

      const result = await isAuthenticated();
      expect(result).toBe(false);
    });
  });
});
