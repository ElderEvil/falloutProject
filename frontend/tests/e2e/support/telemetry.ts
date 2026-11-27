import type { Page } from '@playwright/test'

/** Messages that are expected when a spec runs without a live backend. */
export const NETWORK_NOISE = [
  'Request failed with status code',
  'Failed to load resource',
  'Network Error',
  'timeout of',
  'canceled',
]

/** True for real JS crashes (TypeError, ReferenceError, ...) and false for network noise. */
export const isRealJsError = (message: string): boolean =>
  !NETWORK_NOISE.some((prefix) => message.includes(prefix))

export interface ErrorLog {
  /** `console` messages of type error, verbatim. */
  console: string[]
  /** Uncaught page errors, prefixed with `PAGE ERROR:`. */
  page: string[]
  /** Console and page errors in arrival order. */
  all: string[]
  /** Page errors that are not network noise. */
  real: string[]
}

/**
 * Subscribes to the page's console and pageerror channels. The returned arrays
 * keep filling as the test runs, so specs assert on them after navigation.
 */
export function collectErrors(page: Page): ErrorLog {
  const log: ErrorLog = { console: [], page: [], all: [], real: [] }
  page.on('console', (message) => {
    if (message.type() !== 'error') return
    log.console.push(message.text())
    log.all.push(message.text())
  })
  page.on('pageerror', (error) => {
    const message = `PAGE ERROR: ${error.message}`
    log.page.push(message)
    log.all.push(message)
    if (isRealJsError(message)) log.real.push(message)
  })
  return log
}

/** Records native dialog messages and dismisses them, so a native confirm fails the spec. */
export function collectNativeDialogs(page: Page): string[] {
  const messages: string[] = []
  page.on('dialog', async (dialog) => {
    messages.push(dialog.message())
    await dialog.dismiss()
  })
  return messages
}
