import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import LandingPage from './page';

describe('LandingPage', () => {
  it('renders the main heading', () => {
    render(<LandingPage />);
    const heading = screen.getByRole('heading', { level: 1 });
    expect(heading.textContent).toContain('FeedbackAgent');
    expect(heading.textContent).toContain('The Self-Healing Dev Loop');
  });

  it('renders the Enter Dashboard link', () => {
    render(<LandingPage />);
    const link = screen.getByRole('link', { name: /enter dashboard/i });
    expect(link).toBeDefined();
    expect(link.getAttribute('href')).toBe('/feedback');
  });
});