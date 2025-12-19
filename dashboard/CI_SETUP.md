# CI/CD Setup

This document describes the CI/CD setup for the Soulcaster dashboard.

## What's Configured

### GitHub Actions Workflow (`.github/workflows/ci.yml`)

Runs automatically on:

- Push to `main` or `data_ingestion` branches
- Pull requests to `main` or `data_ingestion` branches

### Checks Performed

1. **Prettier Format Check** - Ensures consistent code formatting
2. **TypeScript Type Check** - Catches type errors before deployment
3. **Build Check** - Ensures the Next.js app builds successfully

### Non-Blocking vs Blocking

During the hackathon, these checks are configured as **informational only**:

- ✅ **Type Check** - Blocking (prevents build failures)
- ✅ **Build** - Blocking (prevents deploy failures)
- ⚠️ **Format Check** - Non-blocking (won't prevent merge, just warns)

**ESLint** is temporarily disabled due to a Next.js 16 + ESLint 9 configuration issue. Type-check and Prettier provide sufficient coverage for the hackathon.

## Local Development Commands

```bash
# Auto-format all code
npm run format

# Check if code is formatted correctly
npm run format:check

# Run TypeScript type checking
npm run type-check

# Run all CI checks locally
npm run format:check && npm run type-check
```

## Prettier Configuration

Located in `.prettierrc`:

- Single quotes
- 2-space indentation
- 100-character line width
- Trailing commas (ES5)
- Semicolons enabled

## Post-Hackathon Improvements

To make checks stricter after the hackathon:

1. Remove `continue-on-error: true` from the GitHub Actions workflow
2. Add branch protection rules requiring status checks to pass
3. Fix ESLint configuration (migrate to ESLint 9 format or downgrade eslint-config-next)
4. Consider adding:
   - Unit tests
   - E2E tests
   - Security scanning
   - Bundle size analysis

## Troubleshooting

### Format Check Fails

Run `npm run format` to auto-fix formatting issues.

### Type Check Fails

Fix TypeScript errors in your code. Common issues:

- Missing type annotations
- Incorrect type usage
- Import errors

### Build Fails

Check for:

- Missing environment variables
- Import errors
- Syntax errors
- Missing dependencies

## Environment Variables Required for CI

Add these secrets to your GitHub repository:

- `UPSTASH_REDIS_REST_URL` - Your Upstash Redis URL
- `UPSTASH_REDIS_REST_TOKEN` - Your Upstash Redis token
