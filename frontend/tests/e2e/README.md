# E2E Testing with Playwright

> End-to-end testing for Fallout Shelter frontend - v2.10.2

## 📋 Overview

This directory contains Playwright E2E tests for verifying the Fallout Shelter frontend works correctly from a user's perspective.

## 🚀 Quick Start

### Prerequisites

1. Backend must be running at `http://localhost:8000`
2. Frontend must be running at `http://localhost:5173`

### Run E2E Tests

```bash
cd frontend

# Run all E2E tests
pnpm run test:e2e

# Run with UI (interactive mode)
pnpm run test:e2e:ui

# Setup authentication state (required before running authenticated tests)
pnpm run test:e2e:setup
```

### Test Files

| File                           | Description                                            |
| ------------------------------ | ------------------------------------------------------ |
| `specs/auth.e2e.spec.ts`       | Authentication flows (login, logout, protected routes) |
| `specs/navigation.e2e.spec.ts` | Navigation and routing tests                           |

## 📁 Structure

```text
tests/e2e/
├── specs/                  # Test specifications
│   ├── auth.e2e.spec.ts
│   └── navigation.e2e.spec.ts
├── fixtures/               # Test data and utilities
├── support/                # Support files and setup
│   └── e2e.setup.ts        # Authentication setup
├── .auth/                  # Storage state for authenticated tests
├── playwright.config.ts    # Playwright configuration
└── .gitignore
```

## 🔐 Environment Variables

> **Note**: Credentials must be provided via environment variables.
> The values below are local-only examples - do not use in staging/production.

| Variable            | Description                        | Default    |
| ------------------- | ---------------------------------- | ---------- |
| `E2E_USER_EMAIL`    | Test user email for authentication | (required) |
| `E2E_USER_PASSWORD` | Test user password                 | (required) |

## ⚙️ Configuration

See `playwright.config.ts` for:

- **Projects**: Chromium, Firefox, WebKit
- **Base URL**: `http://localhost:5173`
- **Retries**: 2 retries on CI, 0 locally
- **Web Server**: Dev server auto-start (disabled on CI)

## 🧪 Running in CI

E2E tests run automatically on:

- Every PR touching `frontend/**`
- Every push to `master` affecting frontend

### CI Secrets Required

```bash
E2E_USER_EMAIL     # Test account email
E2E_USER_PASSWORD # Test account password
```

## 🐛 Debugging

### View Test Traces

```bash
npx playwright show-trace test-results/
```

### Take Screenshots on Failure

Screenshots are automatically captured on test failures in CI.

### Record New Tests

```bash
pnpm run test:e2e:ui
```

Click "Record" to generate new test code interactively.

## 📝 Writing New Tests

### Basic Test Structure

```typescript
import { test, expect } from '@playwright/test'

test.describe('Feature', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/feature')
  })

  test('should do something', async ({ page }) => {
    await expect(page.getByRole('heading')).toHaveText('Expected Title')
  })
})
```

### Using Authentication State

```typescript
test.use({ storageState: 'tests/e2e/.auth/user.json' })

test('should access protected page', async ({ page }) => {
  await page.goto('/dashboard')
  await expect(page).toHaveURL(/\/dashboard/)
})
```

## 🎯 Best Practices

1. **Use locators efficiently**: Prefer `getByRole`, `getByLabel`, `getByText`
2. **Avoid waiting**: Use `expect().toBeVisible()` instead of `sleep()`
3. **Test critical paths**: Focus on user-facing workflows
4. **Isolate tests**: Each test should be independent
5. **Use Page Objects**: Extract reusable UI interactions

## 🔧 Troubleshooting

### "Target page, context, or browser closed"

```bash
# Increase timeout in playwright.config.ts
timeout: 60000
```

### "Element not found"

- Check if element is in a shadow DOM
- Wait for networkidle before interacting
- Use `force: true` for disabled elements

### Authentication failures

```bash
# Reset auth state
rm -rf tests/e2e/.auth/
pnpm run test:e2e:setup
```
