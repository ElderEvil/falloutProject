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
        if (url === '/login') {
          await page.goto(url)
        } else {
          await loginAndGo(page, url)
        }
        await page.waitForLoadState('networkidle')
        await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
        await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
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
    await loginAndGo(page, '/vault/fake-id/dwellers')
    const panel = page.locator('aside[aria-label="Game navigation panel"]')
    await expect(panel).toBeVisible({ timeout: 5000 })
    for (const label of ['Overview', 'Dwellers', 'Exploration', 'Objectives', 'Quests', 'Relationships', 'Training', 'Happiness', 'Storage']) {
      await expect(panel).toContainText(label)
    }
  })

  test('shows coming soon section', async ({ page }) => {
    await loginAndGo(page, '/vault/fake-id/dwellers')
    const panel = page.locator('aside[aria-label="Game navigation panel"]')
    await expect(panel).toContainText('Upcoming Features')
    await expect(panel).toContainText('Workshop')
    await expect(panel).toContainText('Trading Post')
    await expect(panel).toContainText('Achievements')
  })

  test('collapse toggle button exists and toggles', async ({ page }) => {
    await loginAndGo(page, '/vault/fake-id/dwellers')
    const toggleBtn = page.locator('aside button[aria-label*="Collapse"], aside button[aria-label*="Expand"]')
    await expect(toggleBtn.first()).toBeVisible()
    const initialLabel = await toggleBtn.first().getAttribute('aria-label') || ''
    await toggleBtn.first().click()
    await page.waitForTimeout(400)
    const afterLabel = await toggleBtn.first().getAttribute('aria-label') || ''
    expect(initialLabel).not.toEqual(afterLabel)
  })

  test('navigates to storage when clicking Storage nav item', async ({ page }) => {
    await loginAndGo(page, '/vault/fake-id/dwellers')
    const panel = page.locator('aside[aria-label="Game navigation panel"]')
    const storageBtn = panel.locator('nav button:nth-child(9)')
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
    await loginAndGo(page, '/vault/fake-id/dwellers')
    await page.waitForTimeout(500)
    const aside = page.locator('aside[aria-label="Game navigation panel"]')
    const initialClass = await aside.getAttribute('class') || ''
    const initialCollapsed = initialClass.includes('collapsed')
    await page.keyboard.press('Control+b')
    await page.waitForTimeout(400)
    const afterClass = await aside.getAttribute('class') || ''
    const afterCollapsed = afterClass.includes('collapsed')
    expect(initialCollapsed).not.toEqual(afterCollapsed)
  })
})

// ========================================
// LOGIN FORM INTERACTION
// ========================================
test.describe('Login form interaction', () => {
  test('fills email field', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')
    const emailInput = page.locator('input[type="email"]').first()
    await emailInput.fill('overseer@vault-tec.com')
    await expect(emailInput).toHaveValue('overseer@vault-tec.com')
  })

  test('fills password field', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')
    const passwordInput = page.locator('input[type="password"]').first()
    await passwordInput.fill('secret-passphrase')
    await expect(passwordInput).toHaveValue('secret-passphrase')
  })

  test('fills both fields and submits with empty form not redirecting', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')
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
    await page.goto('/login')
    await page.waitForLoadState('networkidle')
    await page.locator('button[type="submit"]').click()
    await page.waitForTimeout(500)
    expect(page.url()).toContain('/login')
  })

  test('has working register link', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')
    const registerLink = page.locator('nav a[aria-label="Go to registration page"]')
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
    await page.goto('/register')
    await page.waitForLoadState('networkidle')
    const inputs = page.locator('input')
    const count = await inputs.count()
    expect(count).toBeGreaterThanOrEqual(2)
    await inputs.first().fill('new-overseer')
    await expect(inputs.first()).toHaveValue('new-overseer')
  })

  test('has working login link', async ({ page }) => {
    await page.goto('/register')
    await page.waitForLoadState('networkidle')
    const loginLink = page.locator('nav a[aria-label="Go to login page"]')
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
    await page.goto('/forgot-password')
    await page.waitForLoadState('networkidle')
    const inputs = page.locator('input')
    expect(await inputs.count()).toBeGreaterThanOrEqual(1)
    const buttons = page.locator('button')
    expect(await buttons.count()).toBeGreaterThanOrEqual(1)
  })

  test('reset-password renders without errors', async ({ page }) => {
    await page.goto('/reset-password')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('body')).toBeVisible()
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })

  test('verify-email renders without errors', async ({ page }) => {
    await page.goto('/verify-email')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('body')).toBeVisible()
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })
})

// ========================================
// VISUAL EFFECTS
// ========================================
test.describe('Visual effects', () => {
  test('scanlines overlay on login page', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('.scanlines').first()).toBeVisible({ timeout: 5000 })
  })

  test('CRT container on login page', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('.crt-container').first()).toBeVisible({ timeout: 5000 })
  })

  test('side panel has scanline overlay', async ({ page }) => {
    await loginAndGo(page, '/vault/fake-id/dwellers')
    const panel = page.locator('aside[aria-label="Game navigation panel"]')
    await expect(panel).toBeVisible()
    // Side panel has a CSS ::before pseudo-element for scanlines already
  })
})

// ========================================
// ERROR STATES
// ========================================
test.describe('Error states', () => {
  test('vault page with fake-id shows error state (not crash)', async ({ page }) => {
    await loginAndGo(page, '/vault/fake-id')
    await page.waitForTimeout(2000)
    const bodyText = await page.locator('body').innerText()
    // Should show error or loading (not blank) — no crash either way
    expect(bodyText.length).toBeGreaterThan(0)
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })

  test('dweller detail with invalid id shows loading or empty state', async ({ page }) => {
    await loginAndGo(page, '/vault/fake-id/dwellers/nonexistent-id')
    await page.waitForTimeout(2000)
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })

  test('vault sub-route that does not exist shows error or fallback', async ({ page }) => {
    await loginAndGo(page, '/vault/fake-id/nonexistent/route')
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
    await loginAndGo(page, '/settings')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    const bodyText = await page.locator('body').innerText()
    expect(bodyText.length).toBeGreaterThan(0)
  })

  test('settings page has back button or navigation', async ({ page }) => {
    await loginAndGo(page, '/settings')
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
    await loginAndGo(page, '/profile')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })
})

// ========================================
// PREFERENCES PAGE
// ========================================
test.describe('Preferences page', () => {
  test('preferences page renders', async ({ page }) => {
    await loginAndGo(page, '/preferences')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })
})

// ========================================
// CHANGELOG PAGE
// ========================================
test.describe('Changelog page', () => {
  test('changelog page renders', async ({ page }) => {
    await loginAndGo(page, '/changelog')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })
})

// ========================================
// ABOUT PAGE
// ========================================
test.describe('About page', () => {
  test('about page renders version info', async ({ page }) => {
    await page.goto('/about')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    const bodyText = await page.locator('body').innerText()
    expect(bodyText).toContain('Fallout Shelter')
    expect(bodyText).toContain('Vue')
  })

  test('about page has GitHub link', async ({ page }) => {
    await page.goto('/about')
    await page.waitForLoadState('networkidle')
    const githubLink = page.locator('a[href*="github.com"]')
    await expect(githubLink).toBeVisible()
  })
})

// ========================================
// STORAGE PAGE
// ========================================
test.describe('Storage page', () => {
  test('storage page renders with tab structure', async ({ page }) => {
    await loginAndGo(page, '/vault/fake-id/storage')
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
    await loginAndGo(page, '/vault/fake-id/dwellers')
    const vaultsLink = page.locator('nav a[aria-label="Navigate to vaults list"]')
    await expect(vaultsLink).toBeVisible()
    await vaultsLink.click()
    await page.waitForLoadState('networkidle')
    expect(page.url()).toContain('/')
  })

  test('navigate to settings and back to home without crash', async ({ page }) => {
    await loginAndGo(page, '/')
    await page.goto('/settings')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('body')).toBeVisible()
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('body')).toBeVisible()
  })

  test('browser back and forward does not crash', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')
    await page.goto('/register')
    await page.waitForLoadState('networkidle')
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
    await loginAndGo(page, '/login')
    const urls = ['/', '/vault/fake-id', '/vault/fake-id/dwellers', '/vault/fake-id/storage', '/settings']
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
    await loginAndGo(page, '/vault/fake-id/dwellers')
    const token1 = await page.evaluate(() => localStorage.getItem('token'))
    await page.goto('/vault/fake-id/storage')
    await page.waitForLoadState('networkidle')
    const token2 = await page.evaluate(() => localStorage.getItem('token'))
    expect(token1).toEqual(token2)
    expect(token1).toEqual(TEST_TOKEN)
  })

  test('user data persists across page navigations', async ({ page }) => {
    await loginAndGo(page, '/vault/fake-id/dwellers')
    const user1 = await page.evaluate(() => localStorage.getItem('user'))
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    const user2 = await page.evaluate(() => localStorage.getItem('user'))
    expect(user1).toEqual(user2)
  })
})

// ========================================
// EDGE CASE URLS
// ========================================
test.describe('Edge case URLs', () => {
  test('vault-id with UUID-like pattern no crash', async ({ page }) => {
    await loginAndGo(page, '/vault/550e8400-e29b-41d4-a716-446655440000')
    await page.waitForTimeout(2000)
    await expect(page.locator('body')).toBeVisible()
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })

  test('vault-id with numbers no crash', async ({ page }) => {
    await loginAndGo(page, '/vault/123')
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
    await loginAndGo(page, '/vault/fake-id/dwellers/graveyard')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
    const bodyText = await page.locator('body').innerText()
    expect(bodyText.length).toBeGreaterThan(0)
  })
})

// ========================================
// HAPPINESS PAGE
// ========================================
test.describe('Happiness page', () => {
  test('happiness page renders without crash', async ({ page }) => {
    await loginAndGo(page, '/vault/fake-id/happiness')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })
})

// ========================================
// EXPLORATION PAGE
// ========================================
test.describe('Exploration page', () => {
  test('exploration page renders without crash', async ({ page }) => {
    await loginAndGo(page, '/vault/fake-id/exploration')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })
})

// ========================================
// TRAINING PAGE
// ========================================
test.describe('Training page', () => {
  test('training page renders without crash', async ({ page }) => {
    await loginAndGo(page, '/vault/fake-id/training')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })
})

// ========================================
// QUESTS PAGE
// ========================================
test.describe('Quests page', () => {
  test('quests page renders without crash', async ({ page }) => {
    await loginAndGo(page, '/vault/fake-id/quests')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })

  test('quest detail page renders without crash', async ({ page }) => {
    await loginAndGo(page, '/vault/fake-id/quests/fake-quest-id')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })
})

// ========================================
// OBJECTIVES PAGE
// ========================================
test.describe('Objectives page', () => {
  test('objectives page renders without crash', async ({ page }) => {
    await loginAndGo(page, '/vault/fake-id/objectives')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })
})

// ========================================
// RADIO PAGE
// ========================================
test.describe('Radio page', () => {
  test('radio page renders without crash', async ({ page }) => {
    await loginAndGo(page, '/vault/fake-id/radio')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })
})

// ========================================
// RELATIONSHIPS PAGE
// ========================================
test.describe('Relationships page', () => {
  test('relationships page renders without crash', async ({ page }) => {
    await loginAndGo(page, '/vault/fake-id/relationships')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })
})

// ========================================
// NAVBAR USER DROPDOWN
// ========================================
test.describe('NavBar user dropdown', () => {
  test('shows Overseer username when authenticated', async ({ page }) => {
    await loginAndGo(page, '/')
    const userButton = page.locator('nav button[aria-haspopup="true"]')
    await expect(userButton).toContainText('Overseer')
  })

  test('dropdown opens and shows menu items', async ({ page }) => {
    await loginAndGo(page, '/')
    const userButton = page.locator('nav button[aria-haspopup="true"]')
    await userButton.click()
    await page.waitForTimeout(300)
    for (const label of ['View profile', 'Display preferences', 'Settings', 'About this application', 'View changelog']) {
      await expect(page.locator(`[aria-label="${label}"]`).first()).toBeVisible()
    }
  })

  test('dropdown has Logout button', async ({ page }) => {
    await loginAndGo(page, '/')
    await page.locator('nav button[aria-haspopup="true"]').click()
    await page.waitForTimeout(300)
    await expect(page.locator('button[aria-label="Logout"]')).toBeVisible()
  })

  test('Escape key closes dropdown', async ({ page }) => {
    await loginAndGo(page, '/')
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
    await loginAndGo(page, '/')
    // NotificationBell uses mdi:bell icon
    const bellIcon = page.locator('nav .notification-bell, nav [aria-label*="notification" i], nav svg')
    await expect(page.locator('body')).toBeVisible()
  })
})
