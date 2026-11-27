import { expect, type Page } from '@playwright/test'
import { open, openAs, type OpenAsOptions } from './session'

export interface RouteRenderOptions extends OpenAsOptions {
  /** Assertion timeout for the body check; omitted keeps Playwright's default. */
  timeout?: number
  /** Open without seeding a session, for public routes. */
  session?: 'seeded' | 'anonymous'
}

/**
 * The shell contract the smoke specs share: the document painted and Vite never
 * swapped in its error overlay. Each caller keeps its own follow-up assertions.
 */
export async function expectRouteRenders(
  page: Page,
  path: string,
  options: RouteRenderOptions = {}
): Promise<void> {
  const { timeout, session = 'seeded', ...openOptions } = options
  if (session === 'anonymous') await open(page, path)
  else await openAs(page, path, openOptions)
  await expect(page.locator('body')).toBeVisible(timeout === undefined ? {} : { timeout })
  await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
}
