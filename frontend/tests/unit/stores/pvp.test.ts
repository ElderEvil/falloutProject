import { afterEach, beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { createPinia, setActivePinia } from 'pinia'

// Mirrors tests/unit/stores/auth.test.ts: the store's only user-facing effect on failure is the
// error handler, so assert the ``showToast`` argument rather than mocking our own layers.
const { handleStoreErrorMock } = vi.hoisted(() => ({ handleStoreErrorMock: vi.fn() }))
vi.mock('@/core/utils/errorHandler', async () => {
  const actual = await vi.importActual<typeof import('@/core/utils/errorHandler')>(
    '@/core/utils/errorHandler'
  )
  return { ...actual, handleStoreError: handleStoreErrorMock }
})

const { listMock } = vi.hoisted(() => ({ listMock: vi.fn() }))
vi.mock('@/modules/pvp/services/pvpDuelService', () => ({
  pvpDuelService: {
    list: listMock,
    current: vi.fn().mockResolvedValue(null),
    get: vi.fn(),
    post: vi.fn(),
    accept: vi.fn(),
  },
}))

import { usePvpStore } from '@/modules/pvp/stores/pvp'

describe('pvp store load failures', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    handleStoreErrorMock.mockClear()
    listMock.mockReset()
    listMock.mockRejectedValue(new Error('boom'))
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('raises a toast when a player opens the board', async () => {
    const ok = await usePvpStore().load('vault-1')

    expect(ok).toBe(false)
    expect(handleStoreErrorMock).toHaveBeenCalledWith(expect.any(Error), 'Failed to load The Pit', true)
  })

  it('stays quiet when a passive caller asks for a silent load', async () => {
    const ok = await usePvpStore().load('vault-1', undefined, { silent: true })

    expect(ok).toBe(false)
    // A banner on the vault page must never toast a failed background fetch.
    expect(handleStoreErrorMock).toHaveBeenCalledWith(
      expect.any(Error),
      'Failed to load The Pit',
      false
    )
  })
})
