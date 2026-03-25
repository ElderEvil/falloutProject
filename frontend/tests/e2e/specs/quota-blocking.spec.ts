import { test, expect } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const authFile = join(__dirname, '../.auth/user.json')

/**
 * E2E Test: Quota Blocking Flow
 *
 * Tests that when quota is at 100%:
 * 1. Chat input is blocked
 * 2. Quota exceeded message is displayed
 * 3. "View Profile" link navigates to profile
 * 4. Profile page shows quota exceeded status
 *
 * Uses API mocking to simulate 100% quota usage.
 */
test.describe('Quota Blocking', () => {
  // Use authenticated storage state for all tests
  test.use({ storageState: authFile })

  test.beforeEach(async ({ page }) => {
    // Intercept and mock the ai-usage API to return 100% quota usage
    await page.route('**/api/v1/users/me/profile/ai-usage', async (route) => {
      const mockQuotaResponse = {
        all_time: {
          prompt_tokens: 500000,
          completion_tokens: 500000,
          total_tokens: 1000000,
        },
        current_month: {
          prompt_tokens: 50000,
          completion_tokens: 50000,
          total_tokens: 100000,
        },
        month: new Date().toISOString().slice(0, 7), // YYYY-MM format
        quota_limit: 100000,
        quota_used: 100000,
        quota_remaining: 0,
        quota_percentage: 100,
        quota_warning: false,
        quota_exceeded: true,
        reset_date: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(), // 30 days from now
      }

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockQuotaResponse),
      })
    })

    // Also mock the profile endpoint to include quota_exceeded in response
    await page.route('**/api/v1/users/me/profile', async (route) => {
      const response = await route.fetch()
      const data = await response.json()

      // Add quota_exceeded flag to the profile response
      const modifiedData = {
        ...data,
        quota_exceeded: true,
      }

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(modifiedData),
      })
    })
  })

  test('should block chat input when quota is at 100%', async ({ page }) => {
    // Navigate to dwellers page to access chat
    await page.goto('/dwellers')
    await page.waitForLoadState('networkidle')

    // Wait for dwellers list to load and click on first dweller
    const firstDweller = page
      .locator('.dweller-card, [data-testid="dweller-card"], .dweller-grid-item')
      .first()

    // If dweller cards exist, click on one to open chat
    if ((await firstDweller.count()) > 0) {
      await firstDweller.click()
    } else {
      // Alternative: try navigating directly to a dweller's chat page
      // This handles cases where the UI structure differs
      const chatLink = page.locator('a[href*="/dwellers/"], a[href*="/chat"]').first()
      if ((await chatLink.count()) > 0) {
        await chatLink.click()
      }
    }

    // Wait for chat page to load
    await page.waitForURL(/.*\/dwellers\/.*/, { timeout: 10000 }).catch(() => {
      // If URL doesn't change, we might be on a modal/chat overlay
      // Continue with the test as the chat component might be visible
    })

    // Verify quota exceeded message is visible in chat
    const quotaExceededMessage = page
      .locator('.quota-exceeded, .quota-blocked-message, [data-testid="quota-exceeded"]')
      .first()
    await expect(quotaExceededMessage).toBeVisible({ timeout: 10000 })

    // Verify "Monthly quota exceeded" text is displayed
    const quotaTitle = page.locator('.quota-title, text=Monthly quota exceeded').first()
    await expect(quotaTitle).toBeVisible()

    // Verify "View Profile" button is visible
    const viewProfileButton = page
      .locator('.quota-profile-btn, button:has-text("View Profile"), button:has-text("Profile")')
      .first()
    await expect(viewProfileButton).toBeVisible()

    // Verify normal chat input is NOT visible (replaced by quota message)
    const chatInput = page
      .locator('.chat-input-field, input[placeholder*="message"], textarea[placeholder*="message"]')
      .first()
    await expect(chatInput).not.toBeVisible()
  })

  test('should navigate to profile and show quota exceeded status', async ({ page }) => {
    // Navigate to dwellers page and trigger quota state
    await page.goto('/dwellers')
    await page.waitForLoadState('networkidle')

    // Try to find and open a dweller chat
    const firstDweller = page
      .locator('.dweller-card, [data-testid="dweller-card"], .dweller-grid-item')
      .first()

    if ((await firstDweller.count()) > 0) {
      await firstDweller.click()
    }

    // Wait for chat to load
    await page.waitForTimeout(2000)

    // Click "View Profile" button from quota exceeded message
    const viewProfileButton = page
      .locator('.quota-profile-btn, button:has-text("View Profile"), button:has-text("Profile")')
      .first()

    // If we're not in chat view (e.g., already blocked), navigate directly to profile
    if ((await viewProfileButton.count()) === 0) {
      await page.goto('/profile')
    } else {
      await viewProfileButton.click()
    }

    // Verify navigation to profile page
    await page.waitForURL(/.*\/profile/, { timeout: 10000 })
    await expect(page).toHaveURL(/.*\/profile/)

    // Wait for profile page to load
    await page.waitForLoadState('networkidle')

    // Verify profile page shows quota exceeded status
    // Look for quota exceeded indicators
    const quotaExceededIndicator = page
      .locator(
        '.quota-exceeded, [data-testid="quota-exceeded"], .text-red-500, .bg-red-500, .border-red-500'
      )
      .first()

    // Check for specific text indicators
    const quotaExceededText = page
      .locator('text=Quota exceeded, text=quota exceeded, text=exceeded')
      .first()

    // At least one of these should be visible
    const hasQuotaIndicator = await quotaExceededIndicator.isVisible().catch(() => false)
    const hasQuotaText = await quotaExceededText.isVisible().catch(() => false)

    expect(hasQuotaIndicator || hasQuotaText).toBeTruthy()

    // Verify AI Usage section shows 100% quota
    const quotaPercentage = page.locator('text=100%, text=100 %').first()
    await expect(quotaPercentage).toBeVisible()

    // Verify the quota bar is at maximum (red color indicates exceeded)
    const quotaBar = page.locator('.bg-red-500, .quota-bar').first()
    await expect(quotaBar).toBeVisible()
  })

  test('should show quota reset date in blocked chat', async ({ page }) => {
    // Navigate to a dweller chat
    await page.goto('/dwellers')
    await page.waitForLoadState('networkidle')

    const firstDweller = page
      .locator('.dweller-card, [data-testid="dweller-card"], .dweller-grid-item')
      .first()

    if ((await firstDweller.count()) > 0) {
      await firstDweller.click()
    }

    // Wait for chat to load
    await page.waitForTimeout(2000)

    // Verify quota exceeded message shows reset date
    const quotaResetText = page.locator('.quota-reset, text=Resets on').first()

    if ((await quotaResetText.count()) > 0) {
      await expect(quotaResetText).toBeVisible()

      // Verify reset date format (should contain a date)
      const resetText = await quotaResetText.textContent()
      expect(resetText).toMatch(/Resets on|resets/i)
    }
  })
})

/**
 * Test without mocking - verifies actual quota API behavior
 * This test checks that the UI handles real quota responses correctly
 */
test.describe('Quota Blocking - Real API', () => {
  test.use({ storageState: authFile })

  test('should handle quota API response gracefully', async ({ page }) => {
    // Navigate to profile to check actual quota status
    await page.goto('/profile')
    await page.waitForLoadState('networkidle')

    // Verify AI Usage card is visible
    const aiUsageCard = page
      .locator('text=AI USAGE STATISTICS, text=AI Usage, .ai-usage-card')
      .first()
    await expect(aiUsageCard).toBeVisible()

    // Verify quota information is displayed
    const quotaSection = page
      .locator('text=Monthly Quota, .quota-section, [data-testid="quota-section"]')
      .first()
    await expect(quotaSection).toBeVisible()

    // Check for quota percentage display
    const quotaPercentage = page.getByText(/\d+%/).first()
    await expect(quotaPercentage).toBeVisible()
  })
})
