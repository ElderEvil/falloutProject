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
import { useAuthStore } from '@/modules/auth/stores/auth'

const boardEntry = (duelId: string) =>
  ({
    duel_id: duelId,
    challenger_vault_name: `Vault ${duelId}`,
    party_size: 2,
    member_names: ['Ana', 'Bo'],
    power_band: 'mid',
    expires_at: new Date().toISOString(),
  }) as never

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

  it('marks which vault the loaded state belongs to', async () => {
    listMock.mockReset()
    listMock.mockResolvedValue([boardEntry('duel-1')])

    const store = usePvpStore()
    expect(await store.load('vault-1')).toBe(true)

    expect(store.stateVaultId).toBe('vault-1')
    expect(store.board).toHaveLength(1)
  })

  it('drops the previous vault state instead of showing it under the new vault', async () => {
    listMock.mockReset()
    listMock.mockResolvedValue([boardEntry('duel-1')])
    const store = usePvpStore()
    await store.load('vault-1')

    let release: (v: never[]) => void = () => undefined
    listMock.mockReturnValue(new Promise((resolve) => (release = resolve as (v: never[]) => void)))
    const pending = store.load('vault-2')

    // Nothing from vault-1 may survive the switch, even before vault-2 resolves.
    expect(store.board).toEqual([])
    expect(store.stateVaultId).toBeNull()

    release([] as never[])
    await pending
    expect(store.stateVaultId).toBe('vault-2')
  })

  it('ignores a load that started before the session was replaced', async () => {
    listMock.mockReset()
    const auth = useAuthStore()
    let release: (v: never[]) => void = () => undefined
    listMock.mockReturnValue(new Promise((resolve) => (release = resolve as (v: never[]) => void)))

    const store = usePvpStore()
    const pending = store.load('vault-1')
    // Logout/login while the request is in flight: the result belongs to the old account.
    auth.sessionGeneration++

    release([boardEntry('stale')] as never[])
    expect(await pending).toBe(false)
    expect(store.board).toEqual([])
    expect(store.stateVaultId).toBeNull()
  })
})
