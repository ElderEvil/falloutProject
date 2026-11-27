import type { Page } from '@playwright/test'
import { setAuthToken, TEST_USER, type TestUser } from '../fixtures/auth'

export const TOKEN = 'test-token-12345'
export const DETERMINISTIC_TOKEN = 'deterministic-e2e-token'

export interface SessionSeed {
  token?: string
  user?: TestUser
}

/** Writes the auth store keys on the current origin; the page must already be on the app. */
export async function seedSession(page: Page, seed: SessionSeed = {}): Promise<void> {
  await setAuthToken(page, seed.token ?? TOKEN, seed.user ?? TEST_USER)
}

/**
 * Seeds the store from an init script so the app's first guard pass already sees
 * the session (`initialization` freezes at store creation).
 */
export async function seedSessionBeforeLoad(page: Page, seed: SessionSeed = {}): Promise<void> {
  await page.addInitScript(
    ([token, user]) => {
      localStorage.setItem('token', token)
      localStorage.setItem('user', JSON.stringify(user))
    },
    [seed.token ?? TOKEN, seed.user ?? TEST_USER] as const
  )
}

/** Opens `path` and waits for the app's fetches to settle. */
export async function open(page: Page, path: string): Promise<void> {
  await page.goto(path)
  await page.waitForLoadState('networkidle')
}

/** Dismisses the first-run "What's New" modal if it mounted. */
export async function dismissWhatsNew(page: Page): Promise<void> {
  const dismiss = page.getByRole('button', { name: 'Got it!' })
  if (await dismiss.isVisible()) await dismiss.click()
}

export interface OpenAsOptions extends SessionSeed {
  /** Click through the changelog modal that can race the first nav. */
  dismissWhatsNew?: boolean
  /** Wait for `networkidle` after the final navigation (default true). */
  settle?: boolean
}

/**
 * Signs in by writing the auth store on `/login`, then opens `path`. The login
 * stop is required: localStorage cannot be written on `about:blank`.
 */
export async function openAs(page: Page, path: string, options: OpenAsOptions = {}): Promise<void> {
  await page.goto('/login')
  await seedSession(page, options)
  if (options.settle === false) await page.goto(path)
  else await open(page, path)
  if (options.dismissWhatsNew) await dismissWhatsNew(page)
}

export const fixturePath = (fixture: string, query = ''): string =>
  `/tests/e2e/fixtures/${fixture}.html${query}`

/** Opens a component harness page under `tests/e2e/fixtures`. */
export async function openFixture(
  page: Page,
  fixture: string,
  query = '',
  options: { waitUntil?: 'load' | 'domcontentloaded' } = {}
): Promise<void> {
  await page.goto(fixturePath(fixture, query), { waitUntil: options.waitUntil })
}
