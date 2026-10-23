import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { createPinia, setActivePinia } from 'pinia'
import { useResponseStationStore } from '@/modules/rooms/stores/responseStation'
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

    await store.loadRoster('vault-1', 'token')

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

    const first = store.loadRoster('vault-1', 'token')
    await store.loadRoster('vault-2', 'token')
    finishOld(roster('vault-1'))
    await first

    expect(store.roster?.vault_id).toBe('vault-2')
    expect(store.isLoading).toBe(false)
  })

  it('surfaces a failed load with the extracted message and clears loading', async () => {
    vi.mocked(fetchResponseRoster).mockRejectedValue(new Error('Signal lost'))
    const store = useResponseStationStore()

    await store.loadRoster('vault-1', 'token')

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
    await store.loadRoster('vault-1', 'token')

    const first = store.setPlace('vault-1', 'fire', 'd1', false, 'token')
    const second = store.setPlace('vault-1', 'fire', 'd2', true, 'token')

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
    await store.loadRoster('vault-1', 'token')

    const pending = store.setPlace('vault-1', 'fire', 'd1', false, 'token')
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
    await store.loadRoster('vault-1', 'token')

    await store.setPlace('vault-1', 'fire', 'd1', false, 'token')

    expect(store.roster?.vault_id).toBe('vault-1')
    expect(mockToast.error).toHaveBeenCalledWith('Failed to update response team: Roster is busy')
  })

  it('reset clears roster state and loading', async () => {
    vi.mocked(fetchResponseRoster).mockResolvedValue(roster())
    const store = useResponseStationStore()
    await store.loadRoster('vault-1', 'token')

    store.reset()

    expect(store.roster).toBeNull()
    expect(store.error).toBeNull()
    expect(store.isLoading).toBe(false)
  })
})
