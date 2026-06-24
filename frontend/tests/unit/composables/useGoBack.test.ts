import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// vi.hoisted ensures mock objects exist before vi.mock factory runs
const mocks = vi.hoisted(() => ({
  back: vi.fn(),
  push: vi.fn(),
  route: {
    params: {} as Record<string, string | string[]>,
    meta: {} as Record<string, unknown>,
  },
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ back: mocks.back, push: mocks.push }),
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
    setHistoryLength(1)
  })

  afterEach(() => {
    // Restore jsdom default history.length
    setHistoryLength(1)
  })

  it('calls router.back() when window.history.length > 1', () => {
    setHistoryLength(2)

    const { goBack } = useGoBack()
    goBack()

    expect(mocks.back).toHaveBeenCalledTimes(1)
    expect(mocks.push).not.toHaveBeenCalled()
  })

  it('falls back to router.push(meta.parentRoute) when history.length is 1', () => {
    setHistoryLength(1)
    mocks.route.meta = { parentRoute: '/vault/123' }

    const { goBack } = useGoBack()
    goBack()

    expect(mocks.push).toHaveBeenCalledWith('/vault/123')
    expect(mocks.back).not.toHaveBeenCalled()
  })

  it('falls back to router.push("/") when no meta.parentRoute and history.length is 1', () => {
    setHistoryLength(1)

    const { goBack } = useGoBack()
    goBack()

    expect(mocks.push).toHaveBeenCalledWith('/')
    expect(mocks.back).not.toHaveBeenCalled()
  })

  it('interpolates route params in parentRoute', () => {
    setHistoryLength(1)
    mocks.route.meta = { parentRoute: '/vault/:id/dwellers' }
    mocks.route.params = { id: 'vault-789', dwellerId: 'dweller-123' }

    const { goBack } = useGoBack()
    goBack()

    expect(mocks.push).toHaveBeenCalledWith('/vault/vault-789/dwellers')
    expect(mocks.back).not.toHaveBeenCalled()
  })
})