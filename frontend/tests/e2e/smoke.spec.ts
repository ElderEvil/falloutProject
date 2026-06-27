import { test, expect } from '@playwright/test'

test.describe('Smoke tests', () => {
  test('app loads and shows the landing page', async ({ page }) => {
    await page.goto('/')
    // The page should load without crashing — check for a key element
    // The landing page typically has a "Fallout Shelter" heading or login form
    await expect(page.locator('body')).toBeVisible()
    // Check that no JavaScript error overlay is present
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })

  test('login page has email and password fields', async ({ page }) => {
    await page.goto('/login')
    // Check for email input — might be type="email" or name="email"
    const emailInput = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i]')
    const passwordInput = page.locator('input[type="password"]')

    await expect(emailInput.first()).toBeVisible({ timeout: 5000 })
    await expect(passwordInput.first()).toBeVisible({ timeout: 5000 })
  })
})
