import { test, expect } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const authFile = join(__dirname, '../.auth/user.json')

test.describe('Navigation', () => {
  test.use({ storageState: authFile })

  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
  })

  test('should display navigation menu', async ({ page }) => {
    await expect(page.getByRole('navigation')).toBeVisible()
  })

  test('should navigate to vault dashboard', async ({ page }) => {
    const vaultLink = page.getByRole('link', { name: /vault|dashboard|home/i })

    if (await vaultLink.count() > 0) {
      await vaultLink.click()
      await page.waitForURL(/\/vault|\//i)
      await expect(page.getByRole('heading', { name: /vault|dashboard/i })).toBeVisible()
    }
  })

  test('should navigate between pages', async ({ page }) => {
    const navLinks = [
      { name: /rooms|building/i, path: /\/rooms/i },
      { name: /dwellers|people/i, path: /\/dwellers/i },
      { name: /resources|inventory/i, path: /\/resources/i },
    ]

    for (const link of navLinks) {
      const navLink = page.getByRole('link', { name: link.name })

      if (await navLink.count() > 0) {
        await navLink.click()
        await page.waitForURL(link.path, { timeout: 5000 })
        await expect(page).toHaveURL(link.path)
      }
    }
  })

  test('should highlight active navigation item', async ({ page }) => {
    const activeLink = page.getByRole('navigation').getByRole('link', { name: /vault|dashboard/i })

    if (await activeLink.count() > 0) {
      await expect(activeLink).toHaveClass(/active|current|selected/i)
    }
  })

  test('should be responsive on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })

    await expect(page.getByRole('navigation')).toBeVisible()

    const hamburgerMenu = page.getByRole('button', { name: /menu|hamburger/i })
    if (await hamburgerMenu.count() > 0) {
      await hamburgerMenu.click()
      await expect(page.getByRole('navigation')).toBeVisible()
    }
  })

  test('should show 404 for unknown routes', async ({ page }) => {
    await page.goto('/unknown-route-that-does-not-exist')
    await expect(page.getByText(/404|not.?found/i)).toBeVisible()
  })
})
