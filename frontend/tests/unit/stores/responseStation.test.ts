import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { createPinia, setActivePinia } from 'pinia'
import { useResponseStationStore } from '@/modules/rooms/stores/responseStation'
import { useAuthStore } from '@/modules/auth/stores/auth'
import {
  fetchResponseRoster,
  updateResponseTeamPlace,
} from '@/modules/rooms/services/responseStationService'
import type { ContaminationTeamRead } from '@/modules/contamination-team/models/contaminationTeam'

vi.mock('@/modules/rooms/services/responseStationService', () => ({
  fetchResponseRoster: vi.fn(),
  updateResponseTeamPlace: vi.fn(),
}))

const mockToast = {
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
  info: vi.fn(),
  show: vi.fn(),
  remove: vi.fn(),
  toasts: { value: [] },
}

vi.mock('@/core/composables/useToast', () => ({ useToast: () => mockToast }))

const roster = (vaultId = 'vault-1'): ContaminationTeamRead => ({
  vault_id: vaultId,
  teams: [
    {
      team: 'fire',
      active: [{ dweller_id: 'd1', status: 'active', name: 'Ash', level: 9 }],
      reserve: [],
    },
    { team: 'radiation', active: [], reserve: [] },
  ],
})

describe('useResponseStationStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('discards a roster response that belongs to another vault', async () => {
    vi.mocked(fetchResponseRoster).mockResolvedValue(roster('vault-2'))
    const store = useResponseStationStore()

    await store.loadRoster('vault-1')

    expect(store.roster).toBeNull()
    expect(store.isLoading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('keeps the newest vault’s roster when an older load resolves later', async () => {
    let finishOld!: (value: ContaminationTeamRead) => void
    vi.mocked(fetchResponseRoster)
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finishOld = resolve
          })
      )
      .mockResolvedValueOnce(roster('vault-2'))
    const store = useResponseStationStore()

    const first = store.loadRoster('vault-1')
    await store.loadRoster('vault-2')
    finishOld(roster('vault-1'))
    await first

    expect(store.roster?.vault_id).toBe('vault-2')
    expect(store.isLoading).toBe(false)
  })

  it('discards a roster response that resolves after the session changed', async () => {
    const auth = useAuthStore()
    let finish!: (value: ContaminationTeamRead) => void
    vi.mocked(fetchResponseRoster).mockReturnValueOnce(
      new Promise((resolve) => {
        finish = resolve
      })
    )
    const store = useResponseStationStore()

    const pending = store.loadRoster('vault-1')
    auth.sessionGeneration += 1
    finish(roster('vault-1'))
    await pending

    expect(store.roster).toBeNull()
    expect(store.error).toBeNull()
    expect(store.isLoading).toBe(false)
  })

  it('surfaces a failed load with the extracted message and clears loading', async () => {
    vi.mocked(fetchResponseRoster).mockRejectedValue(new Error('Signal lost'))
    const store = useResponseStationStore()

    await store.loadRoster('vault-1')

    expect(store.error).toBe('Signal lost')
    expect(store.roster).toBeNull()
    expect(store.isLoading).toBe(false)
  })

  it('serializes roster mutations and tracks the busy member', async () => {
    vi.mocked(fetchResponseRoster).mockResolvedValue(roster())
    let finishPlace!: (value: ContaminationTeamRead) => void
    vi.mocked(updateResponseTeamPlace).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finishPlace = resolve
        })
    )
    const store = useResponseStationStore()
    await store.loadRoster('vault-1')

    const first = store.setPlace('vault-1', 'fire', 'd1', false)
    const second = store.setPlace('vault-1', 'fire', 'd2', true)

    expect(updateResponseTeamPlace).toHaveBeenCalledTimes(1)
    expect(store.busyDwellerIds).toEqual(['d1'])

    finishPlace(roster())
    await Promise.all([first, second])

    expect(store.busyDwellerIds).toEqual([])
    expect(store.roster?.vault_id).toBe('vault-1')
  })

  it('drops a mutation response that lands after the roster was reset', async () => {
    vi.mocked(fetchResponseRoster).mockResolvedValue(roster())
    let finishPlace!: (value: ContaminationTeamRead) => void
    vi.mocked(updateResponseTeamPlace).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finishPlace = resolve
        })
    )
    const store = useResponseStationStore()
    await store.loadRoster('vault-1')

    const pending = store.setPlace('vault-1', 'fire', 'd1', false)
    store.reset()
    finishPlace(roster())
    await pending

    expect(store.roster).toBeNull()
    expect(store.busyDwellerIds).toEqual([])
  })

  it('keeps the roster and reports the failure when a mutation errors', async () => {
    vi.mocked(fetchResponseRoster).mockResolvedValue(roster())
    vi.mocked(updateResponseTeamPlace).mockRejectedValue(new Error('Roster is busy'))
    const store = useResponseStationStore()
    await store.loadRoster('vault-1')

    await store.setPlace('vault-1', 'fire', 'd1', false)

    expect(store.roster?.vault_id).toBe('vault-1')
    expect(mockToast.error).toHaveBeenCalledWith('Failed to update response team: Roster is busy')
  })

  it('reset clears roster state and loading', async () => {
    vi.mocked(fetchResponseRoster).mockResolvedValue(roster())
    const store = useResponseStationStore()
    await store.loadRoster('vault-1')

    store.reset()

    expect(store.roster).toBeNull()
    expect(store.error).toBeNull()
    expect(store.isLoading).toBe(false)
  })

  it.each(['session', 'reset'] as const)(
    'ignores a mutation failure after %s invalidation',
    async (change) => {
      const { promise, reject } = Promise.withResolvers<ContaminationTeamRead>()
      vi.mocked(updateResponseTeamPlace).mockReturnValueOnce(promise)
      const auth = useAuthStore()
      const store = useResponseStationStore()
      const pending = store.setPlace('vault-1', 'fire', 'd1', true)
      if (change === 'session') auth.sessionGeneration++
      else store.reset()
      reject(new Error('Old failure'))
      await pending
      expect(mockToast.error).not.toHaveBeenCalled()
      expect(store.busyDwellerIds).toEqual([])
    }
  )
})
