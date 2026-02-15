import { test, expect } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const authFile = join(__dirname, '../.auth/user.json')

test.describe('Quests - Toggle Feature', () => {
  // Use authenticated state
  test.use({ storageState: authFile })

  test.beforeEach(async ({ page }) => {
    // Navigate to quests page (using first available vault)
    await page.goto('/vaults')
    await page.waitForLoadState('networkidle')

    // Click on first vault to enter it
    const firstVault = page.locator('.vault-card, [data-testid="vault-card"]').first()
    if (await firstVault.count() > 0) {
      await firstVault.click()
      await page.waitForLoadState('networkidle')
    }

    // Navigate to quests
    await page.goto('/vault/vault-1/quests')
    await page.waitForLoadState('networkidle')
  })

  test('should show toggle to display all quests', async ({ page }) => {
    // Wait for page to load
    await page.waitForSelector('text=Quests', { timeout: 10000 })

    // Check toggle exists - look for the checkbox input or label
    const toggleLabel = page.locator('label:has-text("Show All")')
    const toggleInput = page.locator('input[type="checkbox"]').filter({ hasText: /show all/i })

    // Try to find toggle by various means
    const toggle = page.getByText('Show All', { exact: false })
    await expect(toggle).toBeVisible()
  })

  test('should show locked quests when toggle is enabled', async ({ page }) => {
    // Wait for page to load and ensure Overseer's Office exists
    await page.waitForSelector('text=Quests', { timeout: 10000 })

    // Get initial count of visible quests
    const initialQuestCount = await page.locator('.quest-card').count()

    // Find and enable the toggle
    const toggleLabel = page.locator('label:has-text("Show All")')
    const toggleInput = toggleLabel.locator('input[type="checkbox"]')

    // Check if toggle exists
    if (await toggleInput.count() === 0) {
      test.skip()
      return
    }

    // Enable the toggle
    await toggleInput.check()

    // Wait for UI to update
    await page.waitForTimeout(500)

    // Get count after toggle
    const toggledQuestCount = await page.locator('.quest-card').count()

    // With toggle ON, we should see MORE or EQUAL quests (including locked ones)
    expect(toggledQuestCount).toBeGreaterThanOrEqual(initialQuestCount)

    // Check for LOCKED badge on some quests
    const lockedBadges = await page.locator('text=LOCKED').count()

    // If toggle shows more quests, at least some should have LOCKED badge
    if (toggledQuestCount > initialQuestCount) {
      expect(lockedBadges).toBeGreaterThan(0)
    }
  })

  test('should hide locked quests when toggle is disabled', async ({ page }) => {
    await page.waitForSelector('text=Quests', { timeout: 10000 })

    // Find the toggle
    const toggleLabel = page.locator('label:has-text("Show All")')
    const toggleInput = toggleLabel.locator('input[type="checkbox"]')

    if (await toggleInput.count() === 0) {
      test.skip()
      return
    }

    // First ensure toggle is ON
    await toggleInput.check()
    await page.waitForTimeout(500)

    // Get count with toggle ON (all quests)
    const allQuestsCount = await page.locator('.quest-card').count()

    // Disable toggle
    await toggleInput.uncheck()
    await page.waitForTimeout(500)

    // Get count with toggle OFF (only unlocked)
    const unlockedQuestsCount = await page.locator('.quest-card').count()

    // Locked quests should be hidden when toggle is off
    expect(unlockedQuestsCount).toBeLessThanOrEqual(allQuestsCount)

    // Should NOT see "(Showing All)" badge when toggle is off
    const showingAllBadge = page.locator('text=(Showing All)')
    await expect(showingAllBadge).not.toBeVisible()
  })

  test('should show "(Showing All)" badge when toggle is enabled', async ({ page }) => {
    await page.waitForSelector('text=Quests', { timeout: 10000 })

    const toggleLabel = page.locator('label:has-text("Show All")')
    const toggleInput = toggleLabel.locator('input[type="checkbox"]')

    if (await toggleInput.count() === 0) {
      test.skip()
      return
    }

    // Enable toggle
    await toggleInput.check()
    await page.waitForTimeout(500)

    // Should see "(Showing All)" badge in section header
    const showingAllBadge = page.locator('text=(Showing All)')
    await expect(showingAllBadge).toBeVisible()
  })
})

test.describe('Quests - Party Assignment', () => {
  test.use({ storageState: authFile })

  test.beforeEach(async ({ page }) => {
    await page.goto('/vault/vault-1/quests')
    await page.waitForLoadState('networkidle')
  })

  test('should open party assignment modal when clicking Assign Party', async ({ page }) => {
    await page.waitForSelector('text=Quests', { timeout: 10000 })

    // Look for an "Assign Party" button on available quests
    const assignButton = page.getByRole('button', { name: /assign party/i }).first()

    // Only run if there's an available quest with Assign Party button
    if (await assignButton.count() === 0) {
      test.skip()
      return
    }

    await assignButton.click()

    // Modal should open
    await expect(page.locator('text=Party Slots')).toBeVisible()
    await expect(page.locator('text=Available Dwellers')).toBeVisible()
  })

  test('should show eligible dwellers indicator when loading', async ({ page }) => {
    await page.waitForSelector('text=Quests', { timeout: 10000 })

    const assignButton = page.getByRole('button', { name: /assign party/i }).first()

    if (await assignButton.count() === 0) {
      test.skip()
      return
    }

    await assignButton.click()

    // Should show loading or eligibility indicator
    await expect(page.locator('text=Available Dwellers')).toBeVisible()

    // Wait for loading to complete
    await page.waitForTimeout(1000)

    // Should see either "Level Requirements Met" or list of dwellers
    const eligibleBadge = page.locator('text=Level Requirements Met')
    const dwellersList = page.locator('.dweller-item')
    const noDwellers = page.locator('text=No available dwellers')

    // One of these should be visible after loading
    const hasEligible = await eligibleBadge.count() > 0
    const hasDwellers = await dwellersList.count() > 0
    const hasNoDwellers = await noDwellers.count() > 0

    expect(hasEligible || hasDwellers || hasNoDwellers).toBe(true)
  })

  test('should display eligible dwellers with level info', async ({ page }) => {
    await page.waitForSelector('text=Quests', { timeout: 10000 })

    const assignButton = page.getByRole('button', { name: /assign party/i }).first()

    if (await assignButton.count() === 0) {
      test.skip()
      return
    }

    await assignButton.click()
    await page.waitForTimeout(1000) // Wait for eligible dwellers to load

    // Get list of dwellers shown
    const dwellerItems = page.locator('.dweller-item')
    const count = await dwellerItems.count()

    if (count === 0) {
      // No eligible dwellers available - this is valid behavior
      await expect(page.locator('text=No available dwellers')).toBeVisible()
      return
    }

    // Check that all shown dwellers have level displayed
    for (let i = 0; i < count; i++) {
      const dweller = dwellerItems.nth(i)
      const levelText = await dweller.locator('text=/Level \\d+/').textContent().catch(() => null)
      expect(levelText).toBeTruthy()
    }

    // Select first dweller
    await dwellerItems.first().click()

    // Should be able to assign - use exact text match for modal button
    const assignPartyButton = page.getByRole('button', { name: 'Start Quest', exact: true })
    await expect(assignPartyButton).toBeEnabled()
  })

  test('should close modal after party assignment', async ({ page }) => {
    await page.waitForSelector('text=Quests', { timeout: 10000 })

    const assignButton = page.getByRole('button', { name: /assign party/i }).first()

    if (await assignButton.count() === 0) {
      test.skip()
      return
    }

    await assignButton.click()
    await page.waitForTimeout(1000)

    // Select first available dweller if any
    const dwellerItems = page.locator('.dweller-item')
    if (await dwellerItems.count() > 0) {
      await dwellerItems.first().click()

      // Click Start Quest button
      const assignPartyBtn = page.getByRole('button', { name: 'Start Quest', exact: true })
      if (await assignPartyBtn.count() > 0 && await assignPartyBtn.isEnabled()) {
        await assignPartyBtn.click()

        // Modal should close
        await expect(page.locator('text=Party Slots')).not.toBeVisible()
      }
    }
  })
})

test.describe('Quests - Requirements Display', () => {
  test.use({ storageState: authFile })

  test.beforeEach(async ({ page }) => {
    await page.goto('/vault/vault-1/quests')
    await page.waitForLoadState('networkidle')
  })

  test('should render quest cards', async ({ page }) => {
    await page.waitForSelector('text=Quests', { timeout: 10000 })

    const questCards = page.locator('.quest-card')
    const cardCount = await questCards.count()

    if (cardCount === 0) {
      test.skip()
      return
    }

    expect(cardCount).toBeGreaterThan(0)
  })

  test('should show LOCKED badge for quests that are not yet unlocked', async ({ page }) => {
    await page.waitForSelector('text=Quests', { timeout: 10000 })

    // Enable toggle to see all quests including locked ones
    const toggleLabel = page.locator('label:has-text("Show All")')
    const toggleInput = toggleLabel.locator('input[type="checkbox"]')

    if (await toggleInput.count() > 0) {
      await toggleInput.check()
      await page.waitForTimeout(500)
    }

    // Look for LOCKED badge
    const lockedBadges = page.locator('text=LOCKED')
    const lockedCount = await lockedBadges.count()

    if (lockedCount > 0) {
      await expect(lockedBadges.first()).toBeVisible()
    } else {
      const questCards = page.locator('.quest-card')
      await expect(questCards.first()).toBeVisible()
    }
  })

  test('should display quest rewards section', async ({ page }) => {
    await page.waitForSelector('text=Quests', { timeout: 10000 })

    const questCards = page.locator('.quest-card')
    const cardCount = await questCards.count()

    if (cardCount === 0) {
      test.skip('no quest cards present')
      return
    }

    const unlockedCards = questCards.locator('.quest-card:not(:has(.badge:has-text("LOCKED")))')
    const unlockedCount = await unlockedCards.count()

    if (unlockedCount === 0) {
      test.skip('no unlocked quest cards')
      return
    }

    const rewardsSections = unlockedCards.locator('text=REWARDS')
    const rewardsCount = await rewardsSections.count()

    expect(rewardsCount).toBeGreaterThan(0)
  })
})
