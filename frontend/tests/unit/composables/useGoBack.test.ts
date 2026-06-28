import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// vi.hoisted ensures mock objects exist before vi.mock factory runs
const mocks = vi.hoisted(() => ({
  back: vi.fn(),
  replace: vi.fn(),
  route: {
    params: {} as Record<string, string | string[]>,
    meta: {} as Record<string, unknown>,
  },
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ back: mocks.back, replace: mocks.replace }),
  useRoute: () => mocks.route,
}))

import { useGoBack } from '@/core/composables/useGoBack'

function setHistoryLength(length: number): void {
  Object.defineProperty(window.history, 'length', {
    value: length,
    configurable: true,
    writable: true,
  })
}

describe('useGoBack', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.route.params = {}
    mocks.route.meta = {}
    Object.defineProperty(window.history, 'state', {
      value: null,
      configurable: true,
      writable: true,
    })
    setHistoryLength(1)
  })

  afterEach(() => {
    // Restore jsdom default history.length
    setHistoryLength(1)
  })

  it('calls router.back() when window.history.length > 1 and state has back', () => {
    Object.defineProperty(window.history, 'state', {
      value: { back: true },
      configurable: true,
      writable: true,
    })
    setHistoryLength(2)

    const { goBack } = useGoBack()
    goBack()

    expect(mocks.back).toHaveBeenCalledTimes(1)
    expect(mocks.replace).not.toHaveBeenCalled()
  })

  it('falls back to router.replace(meta.parentRoute) when history.length is 1', () => {
    setHistoryLength(1)
    mocks.route.meta = { parentRoute: '/vault/123' }

    const { goBack } = useGoBack()
    goBack()

    expect(mocks.replace).toHaveBeenCalledWith('/vault/123')
    expect(mocks.back).not.toHaveBeenCalled()
  })

  it('falls back to router.replace("/") when no meta.parentRoute and history.length is 1', () => {
    setHistoryLength(1)

    const { goBack } = useGoBack()
    goBack()

    expect(mocks.replace).toHaveBeenCalledWith('/')
    expect(mocks.back).not.toHaveBeenCalled()
  })

  it('interpolates route params in parentRoute', () => {
    setHistoryLength(1)
    mocks.route.meta = { parentRoute: '/vault/:id/dwellers' }
    mocks.route.params = { id: 'vault-789', dwellerId: 'dweller-123' }

    const { goBack } = useGoBack()
    goBack()

    expect(mocks.replace).toHaveBeenCalledWith('/vault/vault-789/dwellers')
    expect(mocks.back).not.toHaveBeenCalled()
  })

  it('falls back to router.replace("/") when interpolated path is empty due to missing params', () => {
    setHistoryLength(1)
    mocks.route.meta = { parentRoute: ':id' }  // fully param-based, becomes '' when id is missing
    mocks.route.params = {}

    const { goBack } = useGoBack()
    goBack()

    expect(mocks.replace).toHaveBeenCalledWith('/')
    expect(mocks.back).not.toHaveBeenCalled()
  })
})
