import { fileURLToPath } from 'node:url'
import type { Page, Route } from '@playwright/test'

/** The subset of `route.fulfill` the specs use. */
export interface ApiReply {
  json?: unknown
  body?: string
  status?: number
  contentType?: string
  headers?: Record<string, string>
}

export type ApiResponder = (route: Route, url: URL) => ApiReply | Promise<ApiReply>

/**
 * One mocked endpoint. Stubs are tried in order and the first match answers, so
 * specific paths must come before the prefix/contains catch-alls, exactly like
 * the hand-written `if` chains these replace.
 */
export interface ApiStub {
  /** Exact pathname. */
  path?: string
  /** Pathname prefix. */
  prefix?: string
  /** Suffix of the full URL (query string included). */
  suffix?: string
  /** Substring of the full URL. */
  contains?: string
  /** Pattern tested against the pathname. */
  pattern?: RegExp
  /** Request method(s) this stub answers; any method when omitted. */
  method?: string | string[]
  /** Escape hatch for anything the fields above cannot express. */
  when?: (url: URL, route: Route) => boolean
  reply: ApiReply | ApiResponder
}

export interface ApiMockOptions {
  /** Answer for requests no stub claims: a reply, `'array'` for `[]`, or `'throw'`. */
  fallback?: ApiReply | 'array' | 'throw'
  /** Called for every request that reaches the mock, claimed or not. */
  onRequest?: (route: Route, url: URL) => void
}

/** A JSON reply; 200 unless a status is given. */
export const json = (body: unknown, status?: number): ApiReply =>
  status === undefined ? { json: body } : { status, json: body }

/** An empty server-sent-events stream, which keeps the app's stream client quiet. */
export const sse = (): ApiReply => ({
  contentType: 'text/event-stream',
  body: ': connected\n\n',
})

/** The stock stand-in artwork: a green square, sized for the surface under test. */
export const greenSvg = (width = 100, height = 100): ApiReply => ({
  contentType: 'image/svg+xml',
  body:
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">` +
    `<rect width="${width}" height="${height}" fill="green"/></svg>`,
})

const methodMatches = (stub: ApiStub, method: string): boolean =>
  stub.method === undefined ||
  (Array.isArray(stub.method) ? stub.method.includes(method) : stub.method === method)

const stubMatches = (stub: ApiStub, url: URL, route: Route): boolean => {
  if (!methodMatches(stub, route.request().method())) return false
  if (stub.when) return stub.when(url, route)
  const href = url.href
  if (stub.path !== undefined) return url.pathname === stub.path
  if (stub.prefix !== undefined) return url.pathname.startsWith(stub.prefix)
  if (stub.suffix !== undefined) return href.endsWith(stub.suffix)
  if (stub.contains !== undefined) return href.includes(stub.contains)
  if (stub.pattern !== undefined) return stub.pattern.test(url.pathname)
  return true
}

/**
 * Mocks every `/api/v1/**` request from one ordered table. Replaces the
 * per-file `page.route` handlers that repeated the same `if (path === ...)`
 * chains in each spec.
 */
export async function mockApi(
  page: Page,
  stubs: ApiStub[],
  options: ApiMockOptions = {}
): Promise<void> {
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    options.onRequest?.(route, url)

    for (const stub of stubs) {
      if (!stubMatches(stub, url, route)) continue
      const reply = typeof stub.reply === 'function' ? await stub.reply(route, url) : stub.reply
      return route.fulfill(reply)
    }

    if (options.fallback === 'throw') {
      throw new Error(`Unhandled API request: ${route.request().method()} ${url.pathname}`)
    }
    return route.fulfill(options.fallback === 'array' ? json([]) : (options.fallback ?? json({})))
  })
}

/** Resolves a `backend/app/static/<relative>` asset for `route.fulfill({ path })`. */
export const staticFile = (relative: string): string =>
  // This file lives in frontend/tests/e2e/support, so four traversals reach the repo root.
  fileURLToPath(new URL(`../../../../backend/app/static/${relative}`, import.meta.url))

export interface StaticOptions {
  /** Substring of the request URL -> file under `backend/app/static`. */
  map?: Record<string, string>
  /** File served when no `map` entry matches. */
  fallback?: string
}

/**
 * Serves `/static/**` from the backend's real assets. Harness fixtures request
 * portraits, pets and rooms the browser cannot fetch without a backend, so the
 * specs answer them with the files the app ships.
 */
export async function serveStatic(page: Page, options: StaticOptions = {}): Promise<void> {
  const map = options.map ?? {}
  const fallback = options.fallback ?? 'dweller_thumbnails/base/FOS_Dw_Default_Human_Female.webp'
  await page.route('**/static/**', (route) => {
    // The browser percent-encodes names with spaces ("FOS%20American%20Shorthair.png");
    // decode before matching so map keys stay the human-readable asset names.
    const href = decodeURIComponent(route.request().url())
    const needle = Object.keys(map).find((candidate) => href.includes(candidate))
    return route.fulfill({ path: staticFile(needle === undefined ? fallback : map[needle]!) })
  })
}

/** Answers every `/static/**` request with the stock green SVG. */
export async function servePlaceholderArt(page: Page, art: ApiReply = greenSvg()): Promise<void> {
  await page.route('**/static/**', (route) => route.fulfill(art))
}

/** Drops every `/static/**` request, which is how the specs simulate missing art. */
export async function blockStatic(page: Page): Promise<void> {
  await page.route('**/static/**', (route) => route.abort())
}
