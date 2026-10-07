import { vi, type Mock } from 'vitest'

/**
 * Shared factory mocks for the most-copied `vi.mock` blocks in the unit suite
 * (issue #909, item 1). Each factory returns the exact module shape a test
 * replaces, so files drop their hand-rolled copies instead of restating spies.
 *
 * Import-order contract — `vi.mock` is hoisted above every import, so a factory
 * body runs while the test file's sibling imports are still resolving:
 *
 * - `createToastMock` is called at module scope and referenced through a nested
 *   arrow (`{ useToast: () => mockToast }`), which is order-independent.
 * - `createAxiosMock`, `createRouterMock` and `createIconifyMock` are called
 *   *inside* the `vi.mock` factory, so this helper's import must appear before
 *   the first import that pulls in the mocked module or the component under
 *   test (put it directly after the `vitest` import).
 */

export interface ToastSpies {
  success: Mock
  error: Mock
  warning: Mock
  info: Mock
}

/**
 * Fresh spies matching the `useToast()` public API.
 *
 * ```ts
 * const mockToast = createToastMock()
 * vi.mock('@/core/composables/useToast', () => ({ useToast: () => mockToast }))
 * ```
 */
export function createToastMock(overrides: Partial<ToastSpies> = {}): ToastSpies {
  return {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
    ...overrides,
  }
}

export interface AxiosClientSpies {
  get: Mock
  post: Mock
  put: Mock
  patch: Mock
  delete: Mock
  request: Mock
}

/**
 * Module-namespace mock for `@/core/plugins/axios` (the default export is the
 * axios client).
 *
 * ```ts
 * vi.mock('@/core/plugins/axios', () => createAxiosMock())
 * vi.mock('@/core/plugins/axios', () => createAxiosMock({ post: myPostSpy }))
 * ```
 */
export function createAxiosMock(overrides: Partial<AxiosClientSpies> = {}): {
  default: AxiosClientSpies
} {
  return {
    default: {
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
      patch: vi.fn(),
      delete: vi.fn(),
      request: vi.fn(),
      ...overrides,
    },
  }
}

export interface RouterMockOptions {
  params?: Record<string, unknown>
  query?: Record<string, unknown>
  path?: string
  meta?: Record<string, unknown>
  push?: Mock
  replace?: Mock
  back?: Mock
  go?: Mock
}

/**
 * Module-namespace mock for `vue-router` with inert `RouterLink`/`RouterView`
 * stubs. Covers the `useRoute`/`useRouter` shapes the suite hand-rolls; pass
 * spies for navigation methods that a test asserts on.
 *
 * ```ts
 * vi.mock('vue-router', () => createRouterMock({ params: { id: 'vault-1' } }))
 * vi.mock('vue-router', () => createRouterMock({ push: mockPush, path: '/about' }))
 * ```
 */
export function createRouterMock(options: RouterMockOptions = {}): Record<string, unknown> {
  const { params = {}, query = {}, path, meta, push, replace, back, go } = options
  const route: Record<string, unknown> = { params, query }
  if (path !== undefined) {
    route.path = path
  }
  if (meta !== undefined) {
    route.meta = meta
  }
  const router = {
    push: push ?? vi.fn(),
    replace: replace ?? vi.fn(),
    back: back ?? vi.fn(),
    go: go ?? vi.fn(),
  }
  return {
    RouterLink: { name: 'RouterLink', props: ['to'], template: '<a><slot /></a>' },
    RouterView: { name: 'RouterView', template: '<div><slot /></div>' },
    useRoute: () => route,
    useRouter: () => router,
  }
}

/** The dominant hand-rolled iconify stub: a `<span class="icon-mock">`. */
export const DEFAULT_ICONIFY_TEMPLATE = '<span class="icon-mock" :data-icon="icon"></span>'

export interface IconifyMockOptions {
  template?: string
  props?: string[]
  name?: string
}

/**
 * Module-namespace mock for `@iconify/vue`. The iconify stub is intentionally
 * per-file (not global) because the suite uses ~10 different templates that
 * tests can assert on; pass the file's existing template to preserve behaviour.
 *
 * ```ts
 * vi.mock('@iconify/vue', () => createIconifyMock())
 * vi.mock('@iconify/vue', () => createIconifyMock({ template: '<i />' }))
 * ```
 */
export function createIconifyMock(options: IconifyMockOptions = {}): Record<string, unknown> {
  const { template = DEFAULT_ICONIFY_TEMPLATE, props = ['icon'], name = 'Icon' } = options
  return { Icon: { name, props, template } }
}
