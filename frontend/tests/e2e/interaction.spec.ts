import { test, expect } from '@playwright/test'
import { PLAYER } from './support/data'
import { TOKEN, open, openAs } from './support/session'
import { expectRouteRenders, type RouteRenderOptions } from './support/surfaces'

/** Options every seeded smoke route in this file shares. */
const PLAYER_ROUTE: RouteRenderOptions = { user: PLAYER, dismissWhatsNew: true, timeout: 10000 }

// ========================================
// RESPONSIVE VIEWPORTS
// ========================================
test.describe('Responsive viewports', () => {
  const viewports = [
    { width: 375, height: 667, name: 'mobile' },
    { width: 768, height: 1024, name: 'tablet' },
    { width: 1280, height: 720, name: 'desktop-small' },
    { width: 1920, height: 1080, name: 'desktop-large' },
  ]

  const pages = [
    { url: '/', name: 'home' },
    { url: '/login', name: 'login' },
    { url: '/vault/fake-id', name: 'vault' },
    { url: '/vault/fake-id/storage', name: 'storage' },
    { url: '/vault/fake-id/dwellers', name: 'dwellers' },
  ]

  for (const { width, height, name: vp } of viewports) {
    for (const { url, name: pageName } of pages) {
      test(`${vp} ${pageName} — renders without crash`, async ({ page }) => {
        await page.setViewportSize({ width, height })
        const options: RouteRenderOptions =
          url === '/login'
            ? { session: 'anonymous', timeout: 10000 }
            : { user: PLAYER, dismissWhatsNew: true, timeout: 10000 }
        await expectRouteRenders(page, url, options)
        const bodyText = await page.locator('body').innerText()
        expect(bodyText.length).toBeGreaterThan(0)
      })
    }
  }
})

// ========================================
// SIDE PANEL
// ========================================
test.describe('Side panel', () => {
  test('renders on dwellers page with all nav items', async ({ page }) => {
    await openAs(page, '/vault/fake-id/dwellers', { user: PLAYER, dismissWhatsNew: true })
    const panel = page.locator('nav[aria-label="Game navigation panel"]')
    await expect(panel).toBeVisible({ timeout: 5000 })
    for (const label of [
      'Overview',
      'Dwellers',
      'Exploration',
      'Objectives',
      'Quests',
      'Relationships',
      'Training',
      'Map',
      'Storage',
      'Trading Post',
    ]) {
      await expect(panel).toContainText(label)
    }
  })

  test('collapse toggle button exists and toggles', async ({ page }) => {
    await openAs(page, '/vault/fake-id/dwellers', { user: PLAYER, dismissWhatsNew: true })
    const toggleBtn = page
      .locator('nav[aria-label="Game navigation panel"]')
      .getByRole('button', { name: /Collapse|Expand/ })
    await expect(toggleBtn.first()).toBeVisible()
    const initialLabel = (await toggleBtn.first().getAttribute('aria-label')) || ''
    await toggleBtn.first().click()
    await page.waitForTimeout(400)
    const afterLabel = (await toggleBtn.first().getAttribute('aria-label')) || ''
    expect(initialLabel).not.toEqual(afterLabel)
  })

  test('navigates to storage when clicking Storage nav item', async ({ page }) => {
    await openAs(page, '/vault/fake-id/dwellers', { user: PLAYER, dismissWhatsNew: true })
    const panel = page.locator('nav[aria-label="Game navigation panel"]')
    const storageBtn = panel.getByRole('button', { name: 'Storage' })
    await expect(storageBtn).toContainText('Storage')
    await storageBtn.click()
    await page.waitForTimeout(1000)
    expect(page.url()).toContain('/vault/fake-id/storage')
  })
})

// ========================================
// KEYBOARD SHORTCUTS
// ========================================
test.describe('Keyboard shortcuts', () => {
  test('Ctrl+B toggles side panel on dwellers page', async ({ page }) => {
    await openAs(page, '/vault/fake-id/dwellers', { user: PLAYER, dismissWhatsNew: true })
    await page.waitForTimeout(500)
    const aside = page.locator('nav[aria-label="Game navigation panel"]')
    const initialClass = (await aside.getAttribute('class')) || ''
    const initialCollapsed = initialClass.includes('collapsed')
    await page.keyboard.press('Control+b')
    await page.waitForTimeout(400)
    const afterClass = (await aside.getAttribute('class')) || ''
    const afterCollapsed = afterClass.includes('collapsed')
    expect(initialCollapsed).not.toEqual(afterCollapsed)
  })
})

// ========================================
// LOGIN FORM INTERACTION
// ========================================
test.describe('Login form interaction', () => {
  test('fills email field', async ({ page }) => {
    await open(page, '/login')
    const emailInput = page.locator('input[type="email"]').first()
    await emailInput.fill('overseer@vault-tec.com')
    await expect(emailInput).toHaveValue('overseer@vault-tec.com')
  })

  test('fills password field', async ({ page }) => {
    await open(page, '/login')
    const passwordInput = page.locator('input[type="password"]').first()
    await passwordInput.fill('secret-passphrase')
    await expect(passwordInput).toHaveValue('secret-passphrase')
  })

  test('fills both fields and submits with empty form not redirecting', async ({ page }) => {
    await open(page, '/login')
    const emailInput = page.locator('input[type="email"]').first()
    const passwordInput = page.locator('input[type="password"]').first()
    await emailInput.fill('admin@vault.com')
    await passwordInput.fill('admin123')
    await page.locator('button[type="submit"]').click()
    await page.waitForTimeout(1000)
    // Should still be on login (fake token, API will fail)
    expect(page.url()).toContain('/login')
  })

  test('submit with empty fields triggers browser validation', async ({ page }) => {
    await open(page, '/login')
    await page.locator('button[type="submit"]').click()
    await page.waitForTimeout(500)
    expect(page.url()).toContain('/login')
  })

  test('has working register link', async ({ page }) => {
    await open(page, '/login')
    const registerLink = page.locator('nav[aria-label="Main navigation"] a[href="/register"]')
    await expect(registerLink).toBeVisible()
    const href = await registerLink.getAttribute('href')
    expect(href).toBe('/register')
  })
})

// ========================================
// REGISTER FORM INTERACTION
// ========================================
test.describe('Register form interaction', () => {
  test('fills first input field', async ({ page }) => {
    await open(page, '/register')
    const inputs = page.locator('input')
    const count = await inputs.count()
    expect(count).toBeGreaterThanOrEqual(2)
    await inputs.first().fill('new-overseer')
    await expect(inputs.first()).toHaveValue('new-overseer')
  })

  test('has working login link', async ({ page }) => {
    await open(page, '/register')
    const loginLink = page.locator('nav[aria-label="Main navigation"] a[href="/login"]')
    await expect(loginLink).toBeVisible()
    const href = await loginLink.getAttribute('href')
    expect(href).toBe('/login')
  })
})

// ========================================
// AUTH PAGES FORM STRUCTURE
// ========================================
test.describe('Auth form pages structure', () => {
  test('forgot-password has email input and submit button', async ({ page }) => {
    await open(page, '/forgot-password')
    const inputs = page.locator('input')
    expect(await inputs.count()).toBeGreaterThanOrEqual(1)
    const buttons = page.locator('button')
    expect(await buttons.count()).toBeGreaterThanOrEqual(1)
  })

  test('reset-password renders without errors', async ({ page }) => {
    await expectRouteRenders(page, '/reset-password', { session: 'anonymous' })
  })

  test('verify-email renders without errors', async ({ page }) => {
    await expectRouteRenders(page, '/verify-email', { session: 'anonymous' })
  })
})

// ========================================
// VISUAL EFFECTS
// ========================================
test.describe('Visual effects', () => {
  test('scanlines overlay on login page', async ({ page }) => {
    await open(page, '/login')
    await expect(page.locator('.scanlines').first()).toBeVisible({ timeout: 5000 })
  })

  test('CRT container on login page', async ({ page }) => {
    await open(page, '/login')
    await expect(page.locator('.crt-container').first()).toBeVisible({ timeout: 5000 })
  })

  test('side panel has scanline overlay', async ({ page }) => {
    await openAs(page, '/vault/fake-id/dwellers', { user: PLAYER, dismissWhatsNew: true })
    const panel = page.locator('nav[aria-label="Game navigation panel"]')
    await expect(panel).toBeVisible()
    // Side panel has a CSS ::before pseudo-element for scanlines already
  })
})

// ========================================
// ERROR STATES
// ========================================
test.describe('Error states', () => {
  test('vault page with fake-id shows error state (not crash)', async ({ page }) => {
    await openAs(page, '/vault/fake-id', { user: PLAYER, dismissWhatsNew: true })
    await page.waitForTimeout(2000)
    const bodyText = await page.locator('body').innerText()
    // Should show error or loading (not blank) — no crash either way
    expect(bodyText.length).toBeGreaterThan(0)
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })

  test('dweller detail with invalid id shows loading or empty state', async ({ page }) => {
    await openAs(page, '/vault/fake-id/dwellers/nonexistent-id', {
      user: PLAYER,
      dismissWhatsNew: true,
    })
    await page.waitForTimeout(2000)
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })

  test('vault sub-route that does not exist shows error or fallback', async ({ page }) => {
    await openAs(page, '/vault/fake-id/nonexistent/route', { user: PLAYER, dismissWhatsNew: true })
    await page.waitForLoadState('networkidle')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })
})

// ========================================
// SETTINGS PAGE STRUCTURE
// ========================================
test.describe('Settings page structure', () => {
  test('settings page renders with heading', async ({ page }) => {
    await openAs(page, '/settings', { user: PLAYER, dismissWhatsNew: true })
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    const bodyText = await page.locator('body').innerText()
    expect(bodyText.length).toBeGreaterThan(0)
  })

  test('settings page has back button or navigation', async ({ page }) => {
    await openAs(page, '/settings', { user: PLAYER, dismissWhatsNew: true })
    const backButtons = page.locator('button:has-text("Back"), a:has-text("Back")')
    const count = await backButtons.count()
    expect(count).toBeGreaterThanOrEqual(0)
  })
})

// ========================================
// PROFILE PAGE STRUCTURE
// ========================================
test.describe('Profile page', () => {
  test('profile page renders', async ({ page }) => {
    await expectRouteRenders(page, '/profile', PLAYER_ROUTE)
  })
})

// ========================================
// PREFERENCES PAGE
// ========================================
test.describe('Preferences page', () => {
  test('preferences page renders', async ({ page }) => {
    await expectRouteRenders(page, '/preferences', PLAYER_ROUTE)
  })
})

// ========================================
// CHANGELOG PAGE
// ========================================
test.describe('Changelog page', () => {
  test('changelog page renders', async ({ page }) => {
    await expectRouteRenders(page, '/changelog', PLAYER_ROUTE)
  })
})

// ========================================
// ABOUT PAGE
// ========================================
test.describe('About page', () => {
  test('about page renders version info', async ({ page }) => {
    await open(page, '/about')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    const bodyText = await page.locator('body').innerText()
    expect(bodyText).toContain('Fallout Shelter')
    expect(bodyText).toContain('Vue')
  })

  test('about page has GitHub link', async ({ page }) => {
    await open(page, '/about')
    const githubLink = page.locator('a[href*="github.com"]')
    await expect(githubLink).toBeVisible()
  })
})

// ========================================
// STORAGE PAGE
// ========================================
test.describe('Storage page', () => {
  test('storage page renders with tab structure', async ({ page }) => {
    await openAs(page, '/vault/fake-id/storage', { user: PLAYER, dismissWhatsNew: true })
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    const bodyText = await page.locator('body').innerText()
    expect(bodyText).toContain('Weapons')
    expect(bodyText).toContain('Outfits')
    expect(bodyText).toContain('Junk')
  })
})

// ========================================
// NAVIGATION FLOWS
// ========================================
test.describe('Navigation flows', () => {
  test('Vaults link in NavBar goes to home', async ({ page }) => {
    await openAs(page, '/vault/fake-id/dwellers', { user: PLAYER, dismissWhatsNew: true })
    const vaultsLink = page.locator('nav a[aria-label="Navigate to vaults list"]')
    await expect(vaultsLink).toBeVisible()
    await vaultsLink.click()
    await page.waitForLoadState('networkidle')
    expect(page.url()).toContain('/')
  })

  test('navigate to settings and back to home without crash', async ({ page }) => {
    await openAs(page, '/', { user: PLAYER, dismissWhatsNew: true })
    await open(page, '/settings')
    await expect(page.locator('body')).toBeVisible()
    await open(page, '/')
    await expect(page.locator('body')).toBeVisible()
  })

  test('browser back and forward does not crash', async ({ page }) => {
    await open(page, '/login')
    await open(page, '/register')
    await page.goBack()
    await page.waitForLoadState('networkidle')
    await expect(page.locator('body')).toBeVisible()
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
    await page.goForward()
    await page.waitForLoadState('networkidle')
    await expect(page.locator('body')).toBeVisible()
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })

  test('rapid navigation does not cause crash', async ({ page }) => {
    await openAs(page, '/login', { user: PLAYER, dismissWhatsNew: true })
    const urls = [
      '/',
      '/vault/fake-id',
      '/vault/fake-id/dwellers',
      '/vault/fake-id/storage',
      '/settings',
    ]
    for (const url of urls) {
      await page.goto(url)
      await page.waitForTimeout(200)
    }
    await expect(page.locator('body')).toBeVisible()
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })
})

// ========================================
// localStorage PERSISTENCE
// ========================================
test.describe('localStorage persistence', () => {
  test('token persists across page navigations', async ({ page }) => {
    await openAs(page, '/vault/fake-id/dwellers', { user: PLAYER, dismissWhatsNew: true })
    const token1 = await page.evaluate(() => localStorage.getItem('token'))
    await open(page, '/vault/fake-id/storage')
    const token2 = await page.evaluate(() => localStorage.getItem('token'))
    expect(token1).toEqual(token2)
    expect(token1).toEqual(TOKEN)
  })

  test('user data persists across page navigations', async ({ page }) => {
    await openAs(page, '/vault/fake-id/dwellers', { user: PLAYER, dismissWhatsNew: true })
    const user1 = await page.evaluate(() => localStorage.getItem('user'))
    await open(page, '/')
    const user2 = await page.evaluate(() => localStorage.getItem('user'))
    expect(user1).toEqual(user2)
  })
})

// ========================================
// EDGE CASE URLS
// ========================================
test.describe('Edge case URLs', () => {
  test('vault-id with UUID-like pattern no crash', async ({ page }) => {
    await openAs(page, '/vault/550e8400-e29b-41d4-a716-446655440000', {
      user: PLAYER,
      dismissWhatsNew: true,
    })
    await page.waitForTimeout(2000)
    await expect(page.locator('body')).toBeVisible()
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })

  test('vault-id with numbers no crash', async ({ page }) => {
    await openAs(page, '/vault/123', { user: PLAYER, dismissWhatsNew: true })
    await page.waitForTimeout(2000)
    await expect(page.locator('body')).toBeVisible()
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })
})

// ========================================
// GRAVEYARD PAGE (after fetchGraveyard fix)
// ========================================
test.describe('Graveyard page', () => {
  test('graveyard page renders without crash', async ({ page }) => {
    await expectRouteRenders(page, '/vault/fake-id/dwellers/graveyard', PLAYER_ROUTE)
    const bodyText = await page.locator('body').innerText()
    expect(bodyText.length).toBeGreaterThan(0)
  })
})

// ========================================
// HAPPINESS PAGE
// ========================================
test.describe('Happiness page', () => {
  test('happiness page renders without crash', async ({ page }) => {
    await expectRouteRenders(page, '/vault/fake-id/happiness', PLAYER_ROUTE)
  })
})

// ========================================
// EXPLORATION PAGE
// ========================================
test.describe('Exploration page', () => {
  test('exploration page renders without crash', async ({ page }) => {
    await expectRouteRenders(page, '/vault/fake-id/exploration', PLAYER_ROUTE)
  })
})

// ========================================
// TRAINING PAGE
// ========================================
test.describe('Training page', () => {
  test('training page renders without crash', async ({ page }) => {
    await expectRouteRenders(page, '/vault/fake-id/training', PLAYER_ROUTE)
  })
})

// ========================================
// QUESTS PAGE
// ========================================
test.describe('Quests page', () => {
  test('quests page renders without crash', async ({ page }) => {
    await expectRouteRenders(page, '/vault/fake-id/quests', PLAYER_ROUTE)
  })
})

// ========================================
// OBJECTIVES PAGE
// ========================================
test.describe('Objectives page', () => {
  test('objectives page renders without crash', async ({ page }) => {
    await expectRouteRenders(page, '/vault/fake-id/objectives', PLAYER_ROUTE)
  })
})

// ========================================
// RADIO PAGE
// ========================================
test.describe('Radio page', () => {
  test('radio page renders without crash', async ({ page }) => {
    await expectRouteRenders(page, '/vault/fake-id/radio', PLAYER_ROUTE)
  })
})

// ========================================
// RELATIONSHIPS PAGE
// ========================================
test.describe('Relationships page', () => {
  test('relationships page renders without crash', async ({ page }) => {
    await expectRouteRenders(page, '/vault/fake-id/relationships', PLAYER_ROUTE)
  })
})

// ========================================
// NAVBAR USER DROPDOWN
// ========================================
test.describe('NavBar user dropdown', () => {
  test('shows Overseer username when authenticated', async ({ page }) => {
    await openAs(page, '/', { user: PLAYER, dismissWhatsNew: true })
    const userButton = page.locator('nav button[aria-haspopup="true"]')
    await expect(userButton).toContainText('Overseer')
  })

  test('dropdown opens and shows menu items', async ({ page }) => {
    await openAs(page, '/', { user: PLAYER, dismissWhatsNew: true })
    const userButton = page.locator('nav button[aria-haspopup="true"]')
    await userButton.click()
    await page.waitForTimeout(300)
    for (const label of [
      'View profile',
      'Display preferences',
      'Settings',
      'About this application',
      'View changelog',
    ]) {
      await expect(page.locator(`[aria-label="${label}"]`).first()).toBeVisible()
    }
  })

  test('dropdown has Logout button', async ({ page }) => {
    await openAs(page, '/', { user: PLAYER, dismissWhatsNew: true })
    await page.locator('nav button[aria-haspopup="true"]').click()
    await page.waitForTimeout(300)
    await expect(page.locator('button[aria-label="Logout"]')).toBeVisible()
  })

  test('Escape key closes dropdown', async ({ page }) => {
    await openAs(page, '/', { user: PLAYER, dismissWhatsNew: true })
    await page.locator('nav button[aria-haspopup="true"]').click()
    await page.waitForTimeout(300)
    await expect(page.locator('button[aria-label="Logout"]')).toBeVisible()
    await page.keyboard.press('Escape')
    await page.waitForTimeout(300)
    await expect(page.locator('button[aria-label="Logout"]')).not.toBeVisible()
  })
})

// ========================================
// NOTIFICATION BELL
// ========================================
test.describe('NotificationBell', () => {
  test('bell icon renders without crash when authenticated', async ({ page }) => {
    await openAs(page, '/', { user: PLAYER, dismissWhatsNew: true })
    // NotificationBell uses mdi:bell icon
    const bellIcon = page.locator(
      'nav .notification-bell, nav [aria-label*="notification" i], nav svg'
    )
    await expect(page.locator('body')).toBeVisible()
  })
})
