/**
 * Tests for ClustersListPage error state improvements (UX-1)
 *
 * Acceptance Criteria:
 * - Error shows specific title based on error type
 * - Error shows troubleshooting hint
 * - Error has role="alert" for screen readers
 * - Retry button is styled as a button (not text link)
 * - Clicking retry triggers fetch with loading state
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// Mock next/link
jest.mock('next/link', () => {
  return ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  );
});

// We'll import the component after mocking fetch
let ClustersListPage: typeof import('@/app/(dashboard)/dashboard/clusters/page').default;

describe('ClustersListPage Error State (UX-1)', () => {
  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
  });

  describe('Error message specificity', () => {
    it('shows "Connection Error" title for network errors', async () => {
      global.fetch = jest.fn().mockRejectedValue(new Error('Failed to fetch'));

      const { default: Page } = await import(
        '@/app/(dashboard)/dashboard/clusters/page'
      );
      render(<Page />);

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });

      expect(screen.getByText(/connection error/i)).toBeInTheDocument();
    });

    it('shows troubleshooting hint for connection errors', async () => {
      global.fetch = jest.fn().mockRejectedValue(new Error('Failed to fetch'));

      const { default: Page } = await import(
        '@/app/(dashboard)/dashboard/clusters/page'
      );
      render(<Page />);

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });

      expect(
        screen.getByText(/check that the backend is running/i)
      ).toBeInTheDocument();
    });

    it('shows "Authentication Error" for 401 responses', async () => {
      global.fetch = jest.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ error: 'unauthorized' }),
      });

      const { default: Page } = await import(
        '@/app/(dashboard)/dashboard/clusters/page'
      );
      render(<Page />);

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });

      // Should mention authentication or session
      expect(
        screen.getByText(/authentication|session|sign/i)
      ).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('error container has role="alert"', async () => {
      global.fetch = jest.fn().mockRejectedValue(new Error('Failed to fetch'));

      const { default: Page } = await import(
        '@/app/(dashboard)/dashboard/clusters/page'
      );
      render(<Page />);

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });
    });
  });

  describe('Retry button', () => {
    it('renders retry button styled as button (not plain text)', async () => {
      global.fetch = jest.fn().mockRejectedValue(new Error('Failed to fetch'));

      const { default: Page } = await import(
        '@/app/(dashboard)/dashboard/clusters/page'
      );
      render(<Page />);

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });

      const retryButton = screen.getByRole('button', { name: /try again|retry/i });
      expect(retryButton).toBeInTheDocument();

      // Should have button-like styling (background color class)
      expect(retryButton.className).toMatch(/bg-/);
    });

    it('clicking retry triggers new fetch', async () => {
      const fetchMock = jest
        .fn()
        .mockRejectedValueOnce(new Error('Failed to fetch'))
        .mockResolvedValueOnce({
          ok: true,
          json: async () => [],
        });

      global.fetch = fetchMock;

      const { default: Page } = await import(
        '@/app/(dashboard)/dashboard/clusters/page'
      );
      render(<Page />);

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });

      const retryButton = screen.getByRole('button', { name: /try again|retry/i });
      fireEvent.click(retryButton);

      await waitFor(() => {
        // Should have called fetch again
        expect(fetchMock).toHaveBeenCalledTimes(3); // Initial + jobs fetch + retry
      });
    });
  });
});
