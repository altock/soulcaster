/**
 * Tests for FeedbackList empty state CTA (UX-5)
 *
 * Acceptance Criteria:
 * - Empty state shows "Connect GitHub Repository" button
 * - Clicking button triggers onRequestShowSources callback
 * - Button only shows when sourceFilter is 'all'
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import FeedbackList from '@/components/FeedbackList';

// Mock fetch for repos and feedback
const mockEmptyFeedback = () => {
  global.fetch = jest.fn().mockImplementation((url: string) => {
    if (url.includes('/api/config/github/repos')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ repos: [] }),
      });
    }
    if (url.includes('/api/feedback')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ items: [] }),
      });
    }
    return Promise.reject(new Error('Unknown URL'));
  });
};

describe('FeedbackList Empty State CTA (UX-5)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockEmptyFeedback();
  });

  describe('Empty state with CTA button', () => {
    it('shows CTA button in empty state', async () => {
      const mockOnRequestShowSources = jest.fn();
      render(<FeedbackList onRequestShowSources={mockOnRequestShowSources} />);

      await waitFor(() => {
        expect(screen.getByText(/no feedback items found/i)).toBeInTheDocument();
      });

      // Should have a direct CTA button
      const ctaButton = screen.getByRole('button', {
        name: /connect github|add source|get started/i,
      });
      expect(ctaButton).toBeInTheDocument();
    });

    it('CTA button calls onRequestShowSources when clicked', async () => {
      const mockOnRequestShowSources = jest.fn();

      render(<FeedbackList onRequestShowSources={mockOnRequestShowSources} />);

      await waitFor(() => {
        expect(screen.getByText(/no feedback items found/i)).toBeInTheDocument();
      });

      const ctaButton = screen.getByRole('button', {
        name: /connect github|add source|get started/i,
      });
      fireEvent.click(ctaButton);

      expect(mockOnRequestShowSources).toHaveBeenCalledTimes(1);
    });
  });

  describe('CTA visibility based on filter', () => {
    it('shows CTA when filter is "all"', async () => {
      const mockOnRequestShowSources = jest.fn();
      render(<FeedbackList onRequestShowSources={mockOnRequestShowSources} />);

      await waitFor(() => {
        expect(screen.getByText(/no feedback items found/i)).toBeInTheDocument();
      });

      // Default filter is 'all', so CTA should be visible
      expect(
        screen.getByRole('button', { name: /connect github|add source|get started/i })
      ).toBeInTheDocument();
    });

    it('hides CTA when filter is specific source (e.g., "github")', async () => {
      render(<FeedbackList />);

      await waitFor(() => {
        expect(screen.getByText(/no feedback items found/i)).toBeInTheDocument();
      });

      // Click GitHub filter
      const githubTab = screen.getByRole('button', { name: /github/i });
      fireEvent.click(githubTab);

      await waitFor(() => {
        // Empty message should change to source-specific
        expect(screen.getByText(/no github feedback/i)).toBeInTheDocument();
      });

      // CTA should NOT be present for filtered view
      expect(
        screen.queryByRole('button', { name: /connect github|add source|get started/i })
      ).not.toBeInTheDocument();
    });
  });

  describe('Empty state messaging', () => {
    it('shows actionable message in empty state', async () => {
      render(<FeedbackList />);

      await waitFor(() => {
        expect(screen.getByText(/no feedback items found/i)).toBeInTheDocument();
      });

      // Should have updated copy about getting started
      expect(
        screen.getByText(/get started|connect|submitting/i)
      ).toBeInTheDocument();
    });
  });
});
