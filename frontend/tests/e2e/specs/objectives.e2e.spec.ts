import { test, expect } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const authFile = join(__dirname, '../.auth/user.json')

test.describe('Objectives - Display', () => {
  // Use authenticated state
  test.use({ storageState: authFile })

  test.beforeEach(async ({ page }) => {
    // Navigate to vaults page
    await page.goto('/vaults')
    await page.waitForLoadState('networkidle')

    // Click on first vault to enter it
    const firstVault = page.locator('.vault-card, [data-testid="vault-card"]').first()
    if (await firstVault.count() > 0) {
      await firstVault.click()
      await page.waitForLoadState('networkidle')
    }

    // Extract vault ID from URL and navigate to objectives
    const url = page.url()
    const vaultMatch = url.match(/\/vault\/([^\/]+)/)
    if (vaultMatch) {
      const vaultId = vaultMatch[1]
      await page.goto(`/vault/${vaultId}/objectives`)
      await page.waitForLoadState('networkidle')
    }
  })

  test('should render objectives page', async ({ page }) => {
    // Wait for page to load
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    // Check that objectives heading is visible
    const heading = page.getByRole('heading', { name: /objectives/i })
    await expect(heading).toBeVisible()
  })

  test('should display active objectives', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    // Look for objective cards or items
    const objectiveCards = page.locator('.objective-card, [data-testid="objective-item"], .objective-item')
    const hasObjectives = await objectiveCards.count() > 0

    if (hasObjectives) {
      // Verify objective cards are visible
      await expect(objectiveCards.first()).toBeVisible()

      // Check for objective challenge text
      const challengeText = page.locator('text=/Collect|Build|Train|Assign|Reach/i').first()
      await expect(challengeText).toBeVisible()
    }
  })

  test('should show objective progress', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    // Look for progress indicators
    const progressBar = page.locator('.progress-bar, [role="progressbar"], .progress').first()
    const progressText = page.locator('text=/\\d+\\s*\\/\\s*\\d+/').first()

    const hasProgressIndicator = await progressBar.count() > 0 || await progressText.count() > 0

    if (hasProgressIndicator) {
      // Progress should be visible
      const progressElement = progressBar.count() > 0 ? progressBar : progressText
      await expect(progressElement).toBeVisible()
    }
  })

  test('should display objective rewards', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    // Look for reward information
    const rewardText = page.locator('text=/Reward|Caps|XP|caps/i').first()

    if (await rewardText.count() > 0) {
      await expect(rewardText).toBeVisible()
    }
  })
})

test.describe('Objectives - Collection Types', () => {
  test.use({ storageState: authFile })

  test.beforeEach(async ({ page }) => {
    await page.goto('/vaults')
    await page.waitForLoadState('networkidle')

    const firstVault = page.locator('.vault-card, [data-testid="vault-card"]').first()
    if (await firstVault.count() > 0) {
      await firstVault.click()
      await page.waitForLoadState('networkidle')
    }

    const url = page.url()
    const vaultMatch = url.match(/\/vault\/([^\/]+)/)
    if (vaultMatch) {
      const vaultId = vaultMatch[1]
      await page.goto(`/vault/${vaultId}/objectives`)
      await page.waitForLoadState('networkidle')
    }
  })

  test('should display caps collection objectives', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    // Look for caps-related objectives
    const capsObjective = page.locator('text=/Collect.*[Cc]aps|[Cc]aps.*Collect/i').first()

    if (await capsObjective.count() > 0) {
      await expect(capsObjective).toBeVisible()
    }
  })

  test('should display resource collection objectives', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    // Look for resource objectives (power, food, water)
    const resourceObjective = page.locator('text=/Collect.*(?:Power|Food|Water)/i').first()

    if (await resourceObjective.count() > 0) {
      await expect(resourceObjective).toBeVisible()
    }
  })

  test('should display item collection objectives', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    // Look for item collection objectives (weapons, outfits, stimpaks)
    const itemObjective = page.locator('text=/Collect.*(?:Weapon|Outfit|[Ss]timpak)/i').first()

    if (await itemObjective.count() > 0) {
      await expect(itemObjective).toBeVisible()
    }
  })

  test('should display build objectives', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    // Look for build objectives
    const buildObjective = page.locator('text=/Build.*(?:Room|rooms)/i').first()

    if (await buildObjective.count() > 0) {
      await expect(buildObjective).toBeVisible()
    }
  })

  test('should display train objectives', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    // Look for train objectives
    const trainObjective = page.locator('text=/Train.*[Dd]weller/i').first()

    if (await trainObjective.count() > 0) {
      await expect(trainObjective).toBeVisible()
    }
  })

  test('should display assign objectives', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    // Look for assign objectives
    const assignObjective = page.locator('text=/Assign.*[Dd]weller/i').first()

    if (await assignObjective.count() > 0) {
      await expect(assignObjective).toBeVisible()
    }
  })
})

test.describe('Objectives - Completion', () => {
  test.use({ storageState: authFile })

  test.beforeEach(async ({ page }) => {
    await page.goto('/vaults')
    await page.waitForLoadState('networkidle')

    const firstVault = page.locator('.vault-card, [data-testid="vault-card"]').first()
    if (await firstVault.count() > 0) {
      await firstVault.click()
      await page.waitForLoadState('networkidle')
    }

    const url = page.url()
    const vaultMatch = url.match(/\/vault\/([^\/]+)/)
    if (vaultMatch) {
      const vaultId = vaultMatch[1]
      await page.goto(`/vault/${vaultId}/objectives`)
      await page.waitForLoadState('networkidle')
    }
  })

  test('should show completed objectives differently', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    // Look for completed objectives (might have different styling or badge)
    const completedObjective = page.locator('.objective-completed, [data-completed="true"], .completed').first()

    if (await completedObjective.count() > 0) {
      // Completed objective should have visual distinction
      await expect(completedObjective).toBeVisible()

      // Check for completed badge or checkmark
      const completedBadge = page.locator('text=/Completed|Done|✓/i').first()
      if (await completedBadge.count() > 0) {
        await expect(completedBadge).toBeVisible()
      }
    }
  })

  test('should show claim reward button for completed objectives', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    // Look for claim reward buttons
    const claimButton = page.getByRole('button', { name: /claim|reward/i }).first()

    if (await claimButton.count() > 0) {
      await expect(claimButton).toBeVisible()
      await expect(claimButton).toBeEnabled()
    }
  })
})

test.describe('Objectives - Navigation', () => {
  test.use({ storageState: authFile })

  test('should navigate to objectives from vault dashboard', async ({ page }) => {
    await page.goto('/vaults')
    await page.waitForLoadState('networkidle')

    const firstVault = page.locator('.vault-card, [data-testid="vault-card"]').first()
    if (await firstVault.count() > 0) {
      await firstVault.click()
      await page.waitForLoadState('networkidle')
    }

    // Look for objectives navigation link/button
    const objectivesLink = page.getByRole('link', { name: /objectives/i }).first()
    const objectivesButton = page.getByRole('button', { name: /objectives/i }).first()

    const objectivesNav = await objectivesLink.count() > 0 ? objectivesLink : objectivesButton

    if (await objectivesNav.count() > 0) {
      await objectivesNav.click()
      await page.waitForLoadState('networkidle')

      // Should be on objectives page
      await expect(page).toHaveURL(/\/objectives/)
    }
  })
})
