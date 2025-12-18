/**
 * Tests for PrsPage retry button (UX-2)
 *
 * Acceptance Criteria:
 * - Error banner shows retry button
 * - Clicking retry clears error and shows loading state
 * - Successful retry shows jobs list
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// Mock next/link
jest.mock('next/link', () => {
  return ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  );
});

describe('PrsPage Error State (UX-2)', () => {
  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('Error banner with retry', () => {
    it('shows retry button when error occurs', async () => {
      global.fetch = jest.fn().mockResolvedValue({
        ok: false,
        status: 500,
      });

      const { default: Page } = await import(
        '@/app/(dashboard)/dashboard/prs/page'
      );
      render(<Page />);

      await waitFor(() => {
        expect(screen.getByText(/failed to fetch/i)).toBeInTheDocument();
      });

      // Should have a retry button
      const retryButton = screen.getByRole('button', { name: /retry|try again/i });
      expect(retryButton).toBeInTheDocument();
    });

    it('retry button triggers new fetch on click', async () => {
      const fetchMock = jest
        .fn()
        .mockResolvedValueOnce({ ok: false, status: 500 })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => [
            {
              id: 'job-1',
              cluster_id: 'cluster-1',
              status: 'success',
              created_at: new Date().toISOString(),
            },
          ],
        });

      global.fetch = fetchMock;

      const { default: Page } = await import(
        '@/app/(dashboard)/dashboard/prs/page'
      );
      render(<Page />);

      await waitFor(() => {
        expect(screen.getByText(/failed to fetch/i)).toBeInTheDocument();
      });

      const retryButton = screen.getByRole('button', { name: /retry|try again/i });
      fireEvent.click(retryButton);

      await waitFor(() => {
        expect(fetchMock.mock.calls.length).toBeGreaterThan(1);
      });
    });

    it('successful retry clears error and shows jobs', async () => {
      const fetchMock = jest
        .fn()
        .mockResolvedValueOnce({ ok: false, status: 500 })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => [
            {
              id: 'job-1',
              cluster_id: 'cluster-1',
              status: 'success',
              created_at: new Date().toISOString(),
            },
          ],
        });

      global.fetch = fetchMock;

      const { default: Page } = await import(
        '@/app/(dashboard)/dashboard/prs/page'
      );
      render(<Page />);

      await waitFor(() => {
        expect(screen.getByText(/failed to fetch/i)).toBeInTheDocument();
      });

      const retryButton = screen.getByRole('button', { name: /retry|try again/i });
      fireEvent.click(retryButton);

      await waitFor(() => {
        // Error should be cleared
        expect(screen.queryByText(/failed to fetch/i)).not.toBeInTheDocument();
      });

      // Should show job
      expect(screen.getByText(/job-1/i)).toBeInTheDocument();
    });
  });

  describe('Error has accessible role', () => {
    it('error banner has role="alert"', async () => {
      global.fetch = jest.fn().mockResolvedValue({
        ok: false,
        status: 500,
      });

      const { default: Page } = await import(
        '@/app/(dashboard)/dashboard/prs/page'
      );
      render(<Page />);

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });
    });
  });
});
