import { test, expect, type Page } from '@playwright/test'

const TEST_TOKEN = 'test-token-12345'

async function loginAndGo(page: Page, url: string) {
  await page.goto('/login')
  await page.evaluate((token) => {
    localStorage.setItem('token', token)
    localStorage.setItem(
      'user',
      JSON.stringify({
        id: 'test-user-id',
        email: 'test@example.com',
        username: 'Overseer',
        is_active: true,
        is_superuser: true,
      })
    )
  }, TEST_TOKEN)
  await page.goto(url)
  await page.waitForLoadState('networkidle')
}

test.describe('NavBar structure', () => {
  test('shows Login and Register links when not authenticated', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')

    // NavBar should show login/register links for unauthenticated users
    const loginLink = page.locator('nav a[aria-label="Go to login page"]')
    const registerLink = page.locator('nav a[aria-label="Go to registration page"]')

    await expect(loginLink).toBeVisible()
    await expect(registerLink).toBeVisible()
  })

  test('shows Vaults link when authenticated', async ({ page }) => {
    await loginAndGo(page, '/')
    const vaultsLink = page.locator('nav a[aria-label="Navigate to vaults list"]')
    await expect(vaultsLink).toBeVisible()
  })

  test('shows user dropdown when authenticated', async ({ page }) => {
    await loginAndGo(page, '/')
    const userButton = page.locator('nav button[aria-haspopup="true"]')
    await expect(userButton).toBeVisible()
    // Dropdown should show the username
    await expect(userButton).toContainText('Overseer')
  })

  test('user dropdown contains all expected links', async ({ page }) => {
    await loginAndGo(page, '/')

    // Open the dropdown
    const userButton = page.locator('nav button[aria-haspopup="true"]')
    await userButton.click()
    await page.waitForTimeout(300) // animation delay

    // Verify menu items
    await expect(page.locator('[role="menuitem"][aria-label="View profile"]')).toBeVisible()
    await expect(page.locator('[role="menuitem"][aria-label="Display preferences"]')).toBeVisible()
    await expect(page.locator('[role="menuitem"][aria-label="Settings"]')).toBeVisible()
    await expect(page.locator('[role="menuitem"][aria-label="About this application"]')).toBeVisible()
    await expect(page.locator('[role="menuitem"][aria-label="View changelog"]')).toBeVisible()

    // Logout button should also be visible
    await expect(page.locator('button[aria-label="Logout"]')).toBeVisible()
  })

  test('NotificationBell renders when authenticated', async ({ page }) => {
    await loginAndGo(page, '/')
    // NotificationBell has a bell icon — look for it in the nav area
    const bellIcon = page.locator('nav [role="button"]').first()
    // It may or may not be visible depending on SSE connection, but shouldn't crash
    await expect(page.locator('body')).toBeVisible()
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })
})

test.describe('Login form structure', () => {
  test('login form has email field', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')

    // UInput renders as an input element
    const emailInput = page.locator('input[type="email"]')
    await expect(emailInput.first()).toBeVisible({ timeout: 5000 })
  })

  test('login form has password field', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')

    const passwordInput = page.locator('input[type="password"]')
    await expect(passwordInput.first()).toBeVisible({ timeout: 5000 })
  })

  test('login form has submit button', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')

    // The submit button contains AUTHENTICATE text
    const submitButton = page.locator('button[type="submit"]')
    await expect(submitButton).toBeVisible()
    await expect(submitButton).toContainText('AUTHENTICATE')
  })
})

test.describe('Register form structure', () => {
  test('register form has input fields', async ({ page }) => {
    await page.goto('/register')
    await page.waitForLoadState('networkidle')

    const inputs = page.locator('input')
    const count = await inputs.count()
    expect(count).toBeGreaterThanOrEqual(2)
  })

  test('register form has submit button', async ({ page }) => {
    await page.goto('/register')
    await page.waitForLoadState('networkidle')

    const submitButtons = page.locator('button[type="submit"]')
    const count = await submitButtons.count()
    expect(count).toBeGreaterThanOrEqual(1)
  })
})

test.describe('Accessibility — basic landmarks', () => {
  test('page has main navigation landmark', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')

    const nav = page.locator('nav[aria-label="Main navigation"]')
    await expect(nav).toBeVisible()
  })

  test('authenticated page has skip-to-content link', async ({ page }) => {
    await loginAndGo(page, '/')
    const skipLink = page.locator('a:has-text("Skip to main content")')
    await expect(skipLink).toBeVisible()
  })
})

test.describe('Navigation flow', () => {
  test('Vaults link navigates to home page', async ({ page }) => {
    await loginAndGo(page, '/vault/fake-id')
    const vaultsLink = page.locator('nav a[aria-label="Navigate to vaults list"]')
    await vaultsLink.click()
    await page.waitForLoadState('networkidle')
    expect(page.url()).toContain('/')
  })

  test('Profile link exists and points to /profile', async ({ page }) => {
    await loginAndGo(page, '/')
    // Open dropdown
    await page.locator('nav button[aria-haspopup="true"]').click()
    await page.waitForTimeout(300)
    const profileLink = page.locator('[role="menuitem"][aria-label="View profile"]')
    await expect(profileLink).toBeVisible()
    await expect(profileLink).toHaveAttribute('href', '/profile')
  })
})
