# UX Implementation Spec

**Based on**: UX Audit 2025-12
**Status**: Ready for implementation
**Priority**: High-priority issues first

---

## Overview

This spec defines concrete implementation changes to address UX issues identified in the December 2025 audit. Each section includes:
- Problem statement with issue ID
- Current behavior
- Target behavior
- File changes required
- Acceptance criteria
- Analytics hooks (optional)

---

## Issue UX-1: Clusters Error State

**Severity**: 3 (Major)
**File**: `app/(dashboard)/dashboard/clusters/page.tsx`

### Current Behavior
```tsx
// Lines 114-129
if (error) {
  return (
    <div className="...">
      <h3 className="...">Error loading clusters</h3>
      <div className="...">{error}</div>
      <button onClick={fetchClusters} className="...text-red-400...">
        Try again
      </button>
    </div>
  );
}
```

Error message is generic ("Failed to fetch clusters") with no context about cause or troubleshooting steps. "Try again" is styled as a text link, inconsistent with button patterns elsewhere.

### Target Behavior

Show specific error context based on error type, with troubleshooting hints and a properly styled retry button.

### Implementation

```tsx
// Replace lines 114-129 with:
if (error) {
  const getErrorDetails = (errorMsg: string) => {
    if (errorMsg.includes('502') || errorMsg.includes('Backend service unavailable')) {
      return {
        title: 'Backend Unavailable',
        description: 'The backend service is temporarily unavailable.',
        hint: 'Please try again in a few moments.',
      };
    }
    if (errorMsg.includes('fetch') || errorMsg.includes('network')) {
      return {
        title: 'Connection Error',
        description: 'Could not connect to the API server.',
        hint: 'Check your internet connection and try again.',
      };
    }
    if (errorMsg.includes('401') || errorMsg.includes('unauthorized')) {
      return {
        title: 'Authentication Error',
        description: 'Your session may have expired.',
        hint: 'Try signing out and back in',
      };
    }
    return {
      title: 'Error Loading Clusters',
      description: errorMsg,
      hint: 'If this persists, check the browser console for details',
    };
  };

  const errorDetails = getErrorDetails(error);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div
        className="rounded-xl bg-red-500/10 border border-red-500/30 p-6"
        role="alert"
        aria-live="polite"
      >
        <div className="flex items-start gap-3">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-6 w-6 text-red-400 flex-shrink-0 mt-0.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <div className="flex-1">
            <h3 className="text-sm font-medium text-red-400">
              {errorDetails.title}
            </h3>
            <p className="mt-1 text-sm text-red-300">
              {errorDetails.description}
            </p>
            <p className="mt-2 text-xs text-red-300/70">
              {errorDetails.hint}
            </p>
          </div>
        </div>
        <div className="mt-4 flex gap-3">
          <button
            onClick={fetchClusters}
            className="inline-flex items-center gap-2 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-300 rounded-lg border border-red-500/30 transition-colors text-sm font-medium"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
            Try Again
          </button>
        </div>
      </div>
    </div>
  );
}
```

### Acceptance Criteria

```gherkin
Given the clusters API returns a network error
When user views /dashboard/clusters
Then error banner shows:
  - Title: "Connection Error"
  - Description: "Could not connect to the API server."
  - Hint: "Check your internet connection and try again."
  - "Try Again" button with refresh icon
And error has role="alert" for screen readers

Given the clusters API returns 502
When user views /dashboard/clusters
Then error banner shows:
  - Title: "Backend Unavailable"
  - Description: "The backend service is temporarily unavailable."
  - Hint: "Please try again in a few moments."
And clicking "Try Again" shows loading state and retries fetch

Given the clusters API returns 401
When user views /dashboard/clusters
Then error banner shows:
  - Title: "Authentication Error"
  - Hint: "Try signing out and back in"
```

---

## Issue UX-2: PRs Error State Missing Retry

**Severity**: 3 (Major)
**File**: `app/(dashboard)/dashboard/prs/page.tsx`

### Current Behavior
```tsx
// Lines 99-108
{error && (
  <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3">
    <div className="flex items-center gap-2">
      <svg>...</svg>
      <p className="text-sm text-red-300">{error}</p>
    </div>
  </div>
)}
```

Error banner shows message but has no retry action. User must manually refresh page.

### Target Behavior

Add retry button consistent with clusters page pattern. Include loading state during retry.

### Implementation

Add `fetchJobs` function extraction and retry button:

```tsx
// Extract fetchJobs to component scope (move from useEffect)
// Around line 21, create a stable reference:
const fetchJobs = async () => {
  try {
    const res = await fetch('/api/jobs');
    if (res.ok) {
      const data = await res.json();
      setJobs(data);
      setError(null);
    } else {
      setError('Failed to fetch jobs');
    }
  } catch (err) {
    console.error('Failed to fetch jobs:', err);
    setError('Failed to fetch jobs');
  } finally {
    setLoading(false);
  }
};

// Replace lines 99-108 with:
{error && (
  <div
    className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3"
    role="alert"
  >
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p className="text-sm text-red-300">{error}</p>
      </div>
      <button
        onClick={() => {
          setLoading(true);
          setError(null);
          fetchJobs();
        }}
        className="inline-flex items-center gap-2 px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30 text-red-300 rounded-lg border border-red-500/30 transition-colors text-xs font-medium"
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        Retry
      </button>
    </div>
  </div>
)}
```

### Acceptance Criteria

```gherkin
Given the jobs API fails
When user views /dashboard/prs
Then error banner shows message AND retry button
And clicking "Retry" clears error and shows loading state
And successful retry shows jobs list
```

---

## Issue UX-4: Disabled Submit Button Without Explanation

**Severity**: 2 (Minor)
**File**: `components/ManualFeedbackForm.tsx`

### Current Behavior
```tsx
// Lines 88-94
<button
  type="submit"
  disabled={isSubmitting || !text.trim()}
  className="...disabled:bg-slate-700 disabled:text-slate-500..."
>
  {isSubmitting ? 'Submitting...' : 'Submit Feedback'}
</button>
```

Button is disabled when textarea is empty, but no explanation is shown.

### Target Behavior

Show helper text when button is disabled due to empty input.

### Implementation

```tsx
// Replace lines 80-95 with:
<div className="mt-4 flex items-center justify-between">
  <div className="flex-1">
    {error && <p className="text-sm text-rose-400">{error}</p>}
    {success && (
      <p className="text-sm text-emerald-400">Feedback submitted successfully!</p>
    )}
    {!error && !success && !text.trim() && (
      <p className="text-sm text-slate-500">Enter feedback text to submit</p>
    )}
  </div>

  <button
    type="submit"
    disabled={isSubmitting || !text.trim()}
    aria-describedby={!text.trim() ? 'submit-hint' : undefined}
    className="px-5 py-2 bg-emerald-500 text-black rounded-full hover:bg-emerald-400 disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed transition-all font-medium shadow-[0_0_15px_rgba(16,185,129,0.2)] hover:shadow-[0_0_20px_rgba(16,185,129,0.4)] active:scale-95"
  >
    {isSubmitting ? 'Submitting...' : 'Submit Feedback'}
  </button>
</div>
```

### Acceptance Criteria

```gherkin
Given the feedback textarea is empty
When user views the manual feedback form
Then helper text "Enter feedback text to submit" is shown below the form
And submit button is disabled

Given user types in the textarea
When textarea has content
Then helper text disappears
And submit button becomes enabled
```

---

## Issue UX-5: Empty State CTA Hidden Behind Toggle

**Severity**: 2 (Minor)
**Files**:
- `app/(dashboard)/dashboard/feedback/page.tsx`
- `components/FeedbackList.tsx`

### Current Behavior

Empty state says "Start by submitting manual feedback or syncing GitHub issues" but the actions are hidden behind "Configure Sources" button.

### Target Behavior

Surface primary action directly in empty state without requiring extra click.

### Implementation

**Option A: Add CTA button to FeedbackList empty state** (Recommended)

In `components/FeedbackList.tsx`, update lines 153-164:

```tsx
{items.length === 0 ? (
  <div className="text-center py-16 bg-emerald-950/20 rounded-3xl border border-white/10 backdrop-blur-sm">
    <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-white/5 mb-4">
      <span className="text-2xl">📭</span>
    </div>
    <h3 className="text-lg font-medium text-white">No feedback items found</h3>
    <p className="mt-2 text-sm text-slate-400 max-w-sm mx-auto">
      {sourceFilter === 'all'
        ? 'Get started by connecting a feedback source or submitting manual feedback.'
        : `No ${sourceFilter} feedback items yet.`}
    </p>
    {sourceFilter === 'all' && (
      <div className="mt-6 flex flex-col sm:flex-row gap-3 justify-center">
        <button
          onClick={() => {
            // Trigger parent to show config panel
            // This requires passing a callback prop from FeedbackPage
          }}
          className="inline-flex items-center justify-center gap-2 px-5 py-2.5 bg-emerald-500 text-black rounded-full hover:bg-emerald-400 transition-all font-medium shadow-[0_0_15px_rgba(16,185,129,0.3)]"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
          Connect GitHub Repository
        </button>
      </div>
    )}
  </div>
) : (
  // ... existing grid
)}
```

**FeedbackPage changes** (`app/(dashboard)/dashboard/feedback/page.tsx`):

```tsx
// Add prop to FeedbackList
<FeedbackList
  refreshTrigger={refreshTrigger}
  onRequestShowSources={() => setShowAddSource(true)}
/>
```

**FeedbackList interface update**:

```tsx
interface FeedbackListProps {
  refreshTrigger?: number;
  onRequestShowSources?: () => void;
}
```

### Acceptance Criteria

```gherkin
Given no feedback items exist
When user views /dashboard/feedback
Then empty state shows "Connect GitHub Repository" button
And clicking button opens the Configure Sources panel
And manual feedback form becomes visible
```

---

## Issue UX-9: Integration Toggle Missing Save Feedback

**Severity**: 2 (Minor)
**File**: `app/(dashboard)/settings/integrations/page.tsx` (or relevant component)

### Current Behavior

Toggle switches and "Save Configuration" buttons have no visible feedback on success.

### Target Behavior

Show inline "Saved" confirmation or toast after successful save.

### Implementation

Add success state to each integration card:

```tsx
const [saveStatus, setSaveStatus] = useState<Record<string, 'idle' | 'saving' | 'saved'>>({});

const handleSave = async (integrationId: string) => {
  setSaveStatus(prev => ({ ...prev, [integrationId]: 'saving' }));

  // ... existing save logic ...

  setSaveStatus(prev => ({ ...prev, [integrationId]: 'saved' }));

  // Clear after 2 seconds
  setTimeout(() => {
    setSaveStatus(prev => ({ ...prev, [integrationId]: 'idle' }));
  }, 2000);
};

// In button:
<button
  onClick={() => handleSave('splunk')}
  disabled={saveStatus['splunk'] === 'saving'}
  className="..."
>
  {saveStatus['splunk'] === 'saving' && 'Saving...'}
  {saveStatus['splunk'] === 'saved' && (
    <span className="flex items-center gap-2">
      <svg className="h-4 w-4 text-emerald-400">...</svg>
      Saved
    </span>
  )}
  {saveStatus['splunk'] === 'idle' && 'Save Configuration'}
</button>
```

### Acceptance Criteria

```gherkin
Given user is on /settings/integrations
When user clicks "Save Configuration" on any integration
Then button shows "Saving..." during API call
And button shows checkmark + "Saved" for 2 seconds after success
And button returns to "Save Configuration" after 2 seconds
```

---

## Low Priority Items (Backlog)

### UX-6: Hide "Billing - Coming Soon"

**File**: `components/DashboardHeader.tsx` (or layout nav)

Remove or conditionally hide the Billing nav item until the feature is ready:

```tsx
// Option 1: Remove entirely
// Option 2: Environment variable
{process.env.NEXT_PUBLIC_SHOW_BILLING === 'true' && (
  <NavItem href="/billing">Billing</NavItem>
)}
```

### UX-7: Remove Reddit "Coming Soon" Tab

**File**: `components/FeedbackList.tsx`

Either remove the Reddit filter entirely or move it to a separate "Roadmap" section:

```tsx
// Option: Filter out disabled items
const enabledFilters = sourceFilters.filter(f => f.enabled);
```

### UX-10: Hide Header Sign-in on Auth Page

**File**: `app/auth/signin/page.tsx` or layout

Add conditional to hide redundant header CTA on sign-in page.

---

## Testing Checklist

- [ ] UX-1: Clusters error shows specific message and styled retry button
- [ ] UX-2: PRs error has retry button that works
- [ ] UX-4: Empty textarea shows "Enter feedback text" hint
- [ ] UX-5: Empty feedback state has direct CTA button
- [ ] UX-9: Integration save shows success feedback
- [ ] All error states have `role="alert"`
- [ ] Keyboard navigation still works (Tab through new buttons)
- [ ] No TypeScript errors
- [ ] No console errors

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2025-12-18 | Initial spec | Claude |
