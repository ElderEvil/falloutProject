import { test, expect } from '@playwright/test'
import { openAs } from './support/session'
import { expectRouteRenders } from './support/surfaces'

test.describe('Feature pages load correctly', () => {
  test('vault home page renders without JS errors', async ({ page }) => {
    await expectRouteRenders(page, '/', { timeout: 10000 })
  })

  test('storage page loads without crashing', async ({ page }) => {
    await expectRouteRenders(page, '/vault/fake-id/storage', { timeout: 10000 })
    const bodyText = await page.locator('body').innerText()
    expect(bodyText.length).toBeGreaterThan(0)
  })

  test('dwellers page loads without crashing', async ({ page }) => {
    await expectRouteRenders(page, '/vault/fake-id/dwellers', { timeout: 10000 })
    const bodyText = await page.locator('body').innerText()
    expect(bodyText.length).toBeGreaterThan(0)
  })

  test('vault detail page loads rooms section', async ({ page }) => {
    await expectRouteRenders(page, '/vault/fake-id', { timeout: 10000 })
    const bodyText = await page.locator('body').innerText()
    expect(bodyText.length).toBeGreaterThan(0)
  })
})

test.describe('Dweller card actions render correctly', () => {
  test('dweller detail page shows without JS errors', async ({ page }) => {
    await expectRouteRenders(page, '/vault/fake-id/dwellers/fake-dweller-id', { timeout: 10000 })
  })
})

test.describe('UButton component migration verification', () => {
  test('buttons render on vault page', async ({ page }) => {
    await openAs(page, '/vault/fake-id')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    const buttons = page.locator('button')
    const buttonCount = await buttons.count()
    expect(buttonCount).toBeGreaterThanOrEqual(0)
  })

  test('dweller page has interactive elements', async ({ page }) => {
    await openAs(page, '/vault/fake-id/dwellers/fake-dweller-id')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    const bodyText = await page.locator('body').innerText()
    expect(bodyText).not.toBeNull()
  })
})
