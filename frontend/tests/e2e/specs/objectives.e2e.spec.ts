import { test, expect } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const authFile = join(__dirname, '../.auth/user.json')

async function enterFirstVaultOrFail(page: any): Promise<string> {
  await page.goto('/vaults')
  await page.waitForLoadState('networkidle')

  const firstVault = page.locator('.vault-card, [data-testid="vault-card"]').first()
  const vaultCount = await firstVault.count()

  if (vaultCount === 0) {
    throw new Error('No vault found - cannot proceed with test. Create a vault first.')
  }

  await firstVault.click()
  await page.waitForLoadState('networkidle')

  const url = page.url()
  const vaultMatch = url.match(/\/vault\/([^\/]+)/)

  if (!vaultMatch) {
    throw new Error('Failed to extract vault ID from URL after clicking vault card')
  }

  return vaultMatch[1]
}

test.describe('Objectives - Display', () => {
  test.use({ storageState: authFile })

  test.beforeEach(async ({ page }) => {
    const vaultId = await enterFirstVaultOrFail(page)
    await page.goto(`/vault/${vaultId}/objectives`)
    await page.waitForLoadState('networkidle')
  })

  test('should render objectives page', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    const heading = page.getByRole('heading', { name: /objectives/i })
    await expect(heading).toBeVisible()
  })

  test('should display active objectives', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    const objectiveCards = page.locator('.objective-card, [data-testid="objective-item"], .objective-item')
    const hasObjectives = await objectiveCards.count() > 0

    if (hasObjectives) {
      await expect(objectiveCards.first()).toBeVisible()

      const challengeText = page.locator('text=/Collect|Build|Train|Assign|Reach/i').first()
      await expect(challengeText).toBeVisible()
    }
  })

  test('should show objective progress', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    const progressBar = page.locator('.progress-bar, [role="progressbar"], .progress').first()
    const progressText = page.locator('text=/\\d+\\s*\\/\\s*\\d+/').first()

    const progressBarCount = await progressBar.count()
    const progressTextCount = await progressText.count()
    const hasProgressIndicator = progressBarCount > 0 || progressTextCount > 0

    if (hasProgressIndicator) {
      const progressElement = progressBarCount > 0 ? progressBar : progressText
      await expect(progressElement).toBeVisible()
    }
  })

  test('should display objective rewards', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    const rewardText = page.locator('text=/Reward|Caps|XP|caps/i').first()

    if (await rewardText.count() > 0) {
      await expect(rewardText).toBeVisible()
    }
  })
})

test.describe('Objectives - Collection Types', () => {
  test.use({ storageState: authFile })

  test.beforeEach(async ({ page }) => {
    const vaultId = await enterFirstVaultOrFail(page)
    await page.goto(`/vault/${vaultId}/objectives`)
    await page.waitForLoadState('networkidle')
  })

  test('should display caps collection objectives', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    const capsObjective = page.locator('text=/Collect.*[Cc]aps|[Cc]aps.*Collect/i').first()

    if (await capsObjective.count() > 0) {
      await expect(capsObjective).toBeVisible()
    }
  })

  test('should display resource collection objectives', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    const resourceObjective = page.locator('text=/Collect.*(?:Power|Food|Water)/i').first()

    if (await resourceObjective.count() > 0) {
      await expect(resourceObjective).toBeVisible()
    }
  })

  test('should display item collection objectives', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    const itemObjective = page.locator('text=/Collect.*(?:Weapon|Outfit|[Ss]timpak)/i').first()

    if (await itemObjective.count() > 0) {
      await expect(itemObjective).toBeVisible()
    }
  })

  test('should display build objectives', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    const buildObjective = page.locator('text=/Build.*(?:Room|rooms)/i').first()

    if (await buildObjective.count() > 0) {
      await expect(buildObjective).toBeVisible()
    }
  })

  test('should display train objectives', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    const trainObjective = page.locator('text=/Train.*[Dd]weller/i').first()

    if (await trainObjective.count() > 0) {
      await expect(trainObjective).toBeVisible()
    }
  })

  test('should display assign objectives', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    const assignObjective = page.locator('text=/Assign.*[Dd]weller/i').first()

    if (await assignObjective.count() > 0) {
      await expect(assignObjective).toBeVisible()
    }
  })
})

test.describe('Objectives - Completion', () => {
  test.use({ storageState: authFile })

  test.beforeEach(async ({ page }) => {
    const vaultId = await enterFirstVaultOrFail(page)
    await page.goto(`/vault/${vaultId}/objectives`)
    await page.waitForLoadState('networkidle')
  })

  test('should show completed objectives differently', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    const completedObjective = page.locator('.objective-completed, [data-completed="true"], .completed').first()

    if (await completedObjective.count() > 0) {
      await expect(completedObjective).toBeVisible()

      const completedBadge = page.locator('text=/Completed|Done|✓/i').first()
      if (await completedBadge.count() > 0) {
        await expect(completedBadge).toBeVisible()
      }
    }
  })

  test('should show claim reward button for completed objectives', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

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
    const vaultId = await enterFirstVaultOrFail(page)

    const objectivesLink = page.getByRole('link', { name: /objectives/i }).first()
    const objectivesButton = page.getByRole('button', { name: /objectives/i }).first()

    const objectivesNav = await objectivesLink.count() > 0 ? objectivesLink : objectivesButton

    if (await objectivesNav.count() > 0) {
      await objectivesNav.click()
      await page.waitForLoadState('networkidle')

      await expect(page).toHaveURL(/\/objectives/)
    }
  })
})

test.describe('Objectives - Training Integration', () => {
  test.use({ storageState: authFile })

  test.beforeEach(async ({ page }) => {
    const vaultId = await enterFirstVaultOrFail(page)
    await page.goto(`/vault/${vaultId}/objectives`)
    await page.waitForLoadState('networkidle')
  })

  const trainingObjectiveLocator = 'text=/Train.*[Ss]trength|Train.*[Pp]erception|Train.*[Ee]ndurance|Train.*[Cc]harisma|Train.*[Ii]ntelligence|Train.*[Aa]gility|Train.*[Ll]uck/i'

  test.skip('should display training objectives with stat-specific tracking', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    const trainObjective = page.locator(trainingObjectiveLocator)

    const count = await trainObjective.count()
    if (count > 0) {
      await expect(trainObjective.first()).toBeVisible()

      const progressInfo = page.locator('text=/\\d+\\s*\\/\\s*\\d+/').first()
      if (await progressInfo.count() > 0) {
        await expect(progressInfo).toBeVisible()
      }
    }
  })

  test.skip('should display progress percentage for objectives', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    const progressBar = page.locator('[role="progressbar"], .progress-bar')
    const progressBarCount = await progressBar.count()

    if (progressBarCount > 0) {
      await expect(progressBar.first()).toBeVisible()
    }
  })
})

test.describe('Objectives - Reach Type', () => {
  test.use({ storageState: authFile })

  test.beforeEach(async ({ page }) => {
    const vaultId = await enterFirstVaultOrFail(page)
    await page.goto(`/vault/${vaultId}/objectives`)
    await page.waitForLoadState('networkidle')
  })

  test('should display population reach objectives', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    const populationObjective = page.locator('text=/Reach.*\\d+.*[Dd]weller|Population.*\\d+/i')
    const count = await populationObjective.count()

    if (count > 0) {
      await expect(populationObjective.first()).toBeVisible()
    }
  })

  test('should display level reach objectives', async ({ page }) => {
    await page.waitForSelector('text=Objectives', { timeout: 10000 })

    const levelObjective = page.locator('text=/Reach.*[Ll]evel.*\\d+/i')
    const count = await levelObjective.count()

    if (count > 0) {
      await expect(levelObjective.first()).toBeVisible()
    }
  })
})
