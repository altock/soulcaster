/**
 * Tests for ClustersListPage Error State Handling
 *
 * Validates error UX improvements:
 * 1. Contextual error messages based on error type (connection, auth, generic)
 * 2. Accessible error alerts with role="alert"
 * 3. Retry functionality that clears errors on success
 */

/// <reference types="@testing-library/jest-dom" />

import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import React from 'react';
import ClustersListPage from '@/app/(dashboard)/dashboard/clusters/page';

// Mock next/link
jest.mock('next/link', () => {
  const MockLink = ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  );
  MockLink.displayName = 'MockLink';
  return MockLink;
});

// Store original fetch for restoration
const originalFetch = global.fetch;

describe('ClustersListPage Error State', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  describe('Error Type Detection', () => {
    it('shows connection error with helpful hint for network failures', async () => {
      global.fetch = jest.fn().mockRejectedValue(new Error('Failed to fetch'));

      await act(async () => {
        render(<ClustersListPage />);
      });

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });

      expect(screen.getByText('Connection Error')).toBeInTheDocument();
      expect(screen.getByText(/check your network connection/i)).toBeInTheDocument();
    });

    it('shows authentication error for 401 response', async () => {
      global.fetch = jest.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({}),
      });

      await act(async () => {
        render(<ClustersListPage />);
      });

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });

      expect(screen.getByText('Authentication Error')).toBeInTheDocument();
      expect(screen.getByText(/session may have expired/i)).toBeInTheDocument();
    });

    it('shows authentication error for 403 response', async () => {
      global.fetch = jest.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: async () => ({}),
      });

      await act(async () => {
        render(<ClustersListPage />);
      });

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });

      expect(screen.getByText('Authentication Error')).toBeInTheDocument();
    });

    it('shows generic error for other HTTP errors', async () => {
      global.fetch = jest.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({}),
      });

      await act(async () => {
        render(<ClustersListPage />);
      });

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });

      expect(screen.getByText('Error loading clusters')).toBeInTheDocument();
      // Generic errors don't have extra hints
      expect(screen.queryByText(/check your network/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/session may have expired/i)).not.toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('error container has role="alert" for screen readers', async () => {
      global.fetch = jest.fn().mockRejectedValue(new Error('Network error'));

      await act(async () => {
        render(<ClustersListPage />);
      });

      await waitFor(() => {
        const alert = screen.getByRole('alert');
        expect(alert).toBeInTheDocument();
      });
    });

    it('retry button is present and accessible', async () => {
      global.fetch = jest.fn().mockRejectedValue(new Error('Failed'));

      await act(async () => {
        render(<ClustersListPage />);
      });

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });

      const retryButton = screen.getByRole('button', { name: /try again/i });
      expect(retryButton).toBeInTheDocument();
    });
  });

  describe('Retry Functionality', () => {
    it('clicking retry clears error on successful fetch', async () => {
      let fetchCallCount = 0;
      global.fetch = jest.fn().mockImplementation(() => {
        fetchCallCount++;
        // First two calls fail (clusters + jobs), subsequent calls succeed
        if (fetchCallCount <= 2) {
          return Promise.reject(new Error('Network error'));
        }
        return Promise.resolve({
          ok: true,
          json: async () => [],
        });
      });

      await act(async () => {
        render(<ClustersListPage />);
      });

      // Wait for error state
      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });

      // Click retry
      const retryButton = screen.getByRole('button', { name: /try again/i });
      await act(async () => {
        fireEvent.click(retryButton);
      });

      // Error should clear and empty state should show
      await waitFor(() => {
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
      });

      // Verify retry was attempted (behavior, not exact count)
      expect(fetchCallCount).toBeGreaterThan(2);
    });

    it('clicking retry shows new error if fetch fails again', async () => {
      global.fetch = jest.fn().mockRejectedValue(new Error('Persistent network error'));

      await act(async () => {
        render(<ClustersListPage />);
      });

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });

      // Click retry
      const retryButton = screen.getByRole('button', { name: /try again/i });
      await act(async () => {
        fireEvent.click(retryButton);
      });

      // Error should still be present
      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
        expect(screen.getByText('Connection Error')).toBeInTheDocument();
      });
    });
  });

  describe('Loading State', () => {
    it('shows loading spinner while fetching', async () => {
      // Never resolve to keep loading state
      global.fetch = jest.fn().mockImplementation(() => new Promise(() => {}));

      await act(async () => {
        render(<ClustersListPage />);
      });

      // Should show loading spinner (uses animate-spin class on a div)
      const spinner = document.querySelector('.animate-spin');
      expect(spinner).toBeInTheDocument();
    });
  });

  describe('Success State', () => {
    it('renders cluster list on successful fetch', async () => {
      const mockClusters = [
        {
          id: 'cluster-1',
          title: 'Test Cluster',
          issue_title: 'Login bug',
          summary: 'Users cannot log in',
          status: 'new',
          count: 5,
          repos: ['repo-1'],
        },
      ];

      global.fetch = jest.fn().mockResolvedValue({
        ok: true,
        json: async () => mockClusters,
      });

      await act(async () => {
        render(<ClustersListPage />);
      });

      await waitFor(() => {
        expect(screen.getByText('Login bug')).toBeInTheDocument();
      });

      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('shows empty state when no clusters exist', async () => {
      global.fetch = jest.fn().mockResolvedValue({
        ok: true,
        json: async () => [],
      });

      await act(async () => {
        render(<ClustersListPage />);
      });

      await waitFor(() => {
        expect(screen.getByText('No Clusters Yet')).toBeInTheDocument();
      });
    });
  });
});
