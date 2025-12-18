# UX Audit: Soulcaster Dashboard

**Date**: December 2025
**Auditor**: Claude (automated)
**Type**: Quick UX Pass
**Context**: B2B/SaaS internal tool (conservative patterns, low delight)

---

## Executive Summary

The Soulcaster dashboard has solid foundations: clean visual design, logical navigation, and good accessibility basics. However, there are **actionability gaps** in error/empty states and onboarding friction that would confuse first-time users.

**Key findings**:
- Error states lack specific guidance and consistent recovery actions
- Empty states don't surface primary CTAs effectively
- "Coming soon" features add clutter without value
- Form feedback could be more helpful

**Recommendation**: Prioritize error state improvements and empty state CTAs—these have the highest impact on user success.

---

## Audit Scope

### Pages Reviewed

| Page | URL | Status |
|------|-----|--------|
| Landing | `/` | Captured |
| Sign-in | `/auth/signin` | Captured |
| Dashboard | `/dashboard` | Captured |
| Clusters | `/dashboard/clusters` | Captured (error state) |
| Feedback | `/dashboard/feedback` | Captured (empty state + config panel) |
| PRs | `/dashboard/prs` | Captured (error state) |
| Integrations | `/settings/integrations` | Captured |

### User Context

- **Primary user**: Developer triaging bugs
- **Primary job**: Review clustered feedback and trigger fixes
- **Devices**: Desktop-first (assumed)

---

## Issue Backlog

### Severity Scale

| Level | Definition |
|-------|------------|
| **4 - Critical** | Prevents task completion, causes data loss |
| **3 - Major** | Frequently blocks tasks or causes serious confusion |
| **2 - Minor** | Causes friction or mild error risk |
| **1 - Cosmetic** | Doesn't impede task completion |

### Issues

| ID | Location | Problem | Heuristic | Sev | Evidence |
|----|----------|---------|-----------|-----|----------|
| UX-1 | Clusters page | Error message "Failed to fetch clusters" lacks context—user doesn't know if backend is down, auth expired, or network issue | H9: Help users recover from errors | **3** | Screenshot shows generic error with no troubleshooting hint |
| UX-2 | PRs page | Error "Failed to fetch jobs" has no retry action—user must refresh page | H9: Help users recover from errors | **3** | Screenshot shows error banner without "Try again" button |
| UX-3 | Dashboard | New user sees 3 cards with "0" stats but no onboarding guidance | H10: Help and documentation | **2** | All cards show 0 with no first-run state |
| UX-4 | Feedback page | "Submit Feedback" disabled with no explanation of why | H5: Error prevention | **2** | Button disabled when textarea empty, no hint shown |
| UX-5 | Feedback page | Empty state says "Start by submitting manual feedback or syncing GitHub issues" but CTA is hidden behind "Configure Sources" | H6: Recognition over recall | **2** | Primary action requires extra click to discover |
| UX-6 | Nav bar | "Billing - Coming soon" shown but disabled—adds clutter without value | H8: Aesthetic and minimalist design | **1** | Nav item visible but non-functional |
| UX-7 | Feedback tabs | "REDDIT - COMING SOON" disabled tab wastes horizontal space and sets false expectations | H8: Aesthetic and minimalist design | **1** | Tab visible but disabled |
| UX-8 | Clusters error | "Try again" is styled as plain text link, not clearly actionable | H4: Consistency and standards | **2** | Inconsistent with button styling elsewhere |
| UX-9 | Integrations | Toggle switches have no loading/success feedback after save | H1: Visibility of system status | **2** | No confirmation that config was saved |
| UX-10 | Sign-in page | Two "Sign in with GitHub" buttons visible (header + main)—redundant | H8: Aesthetic and minimalist design | **1** | Duplicate CTAs on same page |

---

## What's Working Well

| Aspect | Observation |
|--------|-------------|
| **Visual consistency** | Dark theme with emerald accents is cohesive across all pages |
| **Navigation** | Clear hierarchy, active state highlighted, logical grouping |
| **Keyboard accessibility** | Focus rings visible, logical tab order through nav -> content |
| **Empty state icons** | Friendly icons and messaging present (though could be more actionable) |
| **Integrations page** | Good information density, clear form labels, helpful hints |
| **Permissions transparency** | Sign-in page clearly explains OAuth scopes—builds trust |
| **Error visual treatment** | Red background gradient clearly signals error state |

---

## Accessibility Assessment

### Passing

- [x] Focus rings visible on interactive elements
- [x] Logical tab order (logo -> nav -> content -> footer)
- [x] Semantic HTML structure (headings, landmarks, buttons)
- [x] Color contrast appears adequate on primary text
- [x] Interactive elements have reasonable hit targets

### Needs Attention

- [ ] "Coming soon" badges may confuse screen readers (no `aria-disabled` context)
- [ ] Error messages should use `role="alert"` for screen reader announcement
- [ ] Form validation messages need `aria-describedby` association

---

## Heuristic Summary

| Heuristic | Rating | Notes |
|-----------|--------|-------|
| H1: Visibility of system status | Fair | Loading states present, but save confirmations missing |
| H2: Match real world | Good | Developer-friendly terminology |
| H3: User control | Good | Clear navigation, back button works |
| H4: Consistency | Fair | Button styles inconsistent (text link vs button) |
| H5: Error prevention | Fair | Disabled states exist but lack explanation |
| H6: Recognition over recall | Fair | Some CTAs hidden behind toggles |
| H7: Flexibility | N/A | No power-user features observed |
| H8: Aesthetic design | Good | Clean, minimal, appropriate for B2B |
| H9: Error recovery | Poor | Generic messages, inconsistent retry actions |
| H10: Help/documentation | Fair | Tooltips on integrations, but no onboarding |

---

## Priority Recommendations

### High Priority (Fix This Week)

1. **UX-1, UX-2**: Improve error states with specific messages + consistent retry actions
2. **UX-4, UX-5**: Make empty states actionable—surface primary CTAs directly

### Medium Priority (Fix This Sprint)

3. **UX-3**: Add first-run onboarding flow for new users
4. **UX-8, UX-9**: Button styling consistency + save confirmation feedback

### Low Priority (Backlog)

5. **UX-6, UX-7, UX-10**: Hide unshipped features, reduce visual clutter

---

## Screenshots Reference

Screenshots were captured during audit and are available in the browser session. Key observations:

1. **Landing page**: Clear value prop, good CTA hierarchy
2. **Sign-in**: Excellent permissions transparency
3. **Dashboard**: Clean but lacks first-run guidance
4. **Clusters error**: Generic message, text-link retry
5. **Feedback empty**: Good icon, but CTA behind toggle
6. **PRs error**: No retry button at all
7. **Integrations**: Best-designed page, good form UX

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2025-12-18 | Initial audit | Claude |
