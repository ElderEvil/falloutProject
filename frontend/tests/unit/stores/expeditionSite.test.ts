import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import {
  useExpeditionSiteStore,
  SITE_TERMINAL_STATUSES,
  isTerminal,
} from '@/modules/exploration/stores/expeditionSite'
import { expeditionSiteApi } from '@/modules/exploration/api/expeditionSite'
import type { AvailableSiteView, SiteRoomView } from '@/modules/exploration/api/expeditionSite'

vi.mock('@/modules/exploration/api/expeditionSite')

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() }),
}))

const mockSite: AvailableSiteView = {
  id: 'red_rocket',
  name: 'Red Rocket',
  flavor: 'A lonely gas station at the edge of the wastes.',
  min_dweller_level: 3,
  room_total: 4,
}

const mockRoom: SiteRoomView = {
  exploration_id: 'exploration-1',
  site_id: 'red_rocket',
  site_name: 'Red Rocket',
  room_index: 0,
  room_total: 4,
  room_name: 'Forecourt',
  flavor: 'A lonely gas station at the edge of the wastes.',
  node: {
    kind: 'choice',
    prompt: 'A radroach scuttles out from behind the pump.',
    options: [
      { id: 'opt-1', label: 'Fight it off', stat: 'strength', difficulty: 3, success_odds: 0.8 },
    ],
  },
  can_retreat: true,
  status: 'in_room',
  finale_paid: false,
}

describe('Expedition Site Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('fetchAvailableSites populates availableSites', async () => {
    vi.mocked(expeditionSiteApi.listAvailableSites).mockResolvedValue([mockSite])
    const store = useExpeditionSiteStore()

    const result = await store.fetchAvailableSites('exploration-1')

    expect(expeditionSiteApi.listAvailableSites).toHaveBeenCalledWith('exploration-1')
    expect(result).toEqual([mockSite])
    expect(store.availableSites).toEqual([mockSite])
    expect(store.isLoading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('enterSite stores the returned room', async () => {
    vi.mocked(expeditionSiteApi.enterSite).mockResolvedValue(mockRoom)
    const store = useExpeditionSiteStore()

    const result = await store.enterSite('exploration-1', 'red_rocket')

    expect(expeditionSiteApi.enterSite).toHaveBeenCalledWith('exploration-1', 'red_rocket')
    expect(result).toEqual(mockRoom)
    expect(store.room).toEqual(mockRoom)
  })

  it('resolveNode updates room', async () => {
    const nextRoom = { ...mockRoom, room_index: 1, room_name: 'Storefront' }
    vi.mocked(expeditionSiteApi.resolveNode).mockResolvedValue(nextRoom)
    const store = useExpeditionSiteStore()

    const result = await store.resolveNode('exploration-1', 'opt-1')

    expect(expeditionSiteApi.resolveNode).toHaveBeenCalledWith('exploration-1', 'opt-1')
    expect(result).toEqual(nextRoom)
    expect(store.room).toEqual(nextRoom)
  })

  it('retreat stores the returned room', async () => {
    const retreatedRoom = { ...mockRoom, status: 'retreated' }
    vi.mocked(expeditionSiteApi.retreatSite).mockResolvedValue(retreatedRoom)
    const store = useExpeditionSiteStore()

    const result = await store.retreat('exploration-1')

    expect(expeditionSiteApi.retreatSite).toHaveBeenCalledWith('exploration-1')
    expect(result).toEqual(retreatedRoom)
    expect(store.room).toEqual(retreatedRoom)
  })

  it('fetchCurrentRoom returns null without error when no run is open', async () => {
    vi.mocked(expeditionSiteApi.getCurrentRoom).mockResolvedValue(null)
    const store = useExpeditionSiteStore()

    const result = await store.fetchCurrentRoom('exploration-1')

    expect(result).toBeNull()
    expect(store.room).toBeNull()
    expect(store.error).toBeNull()
    expect(store.isLoading).toBe(false)
  })

  it('fetchCurrentRoom stores the current room when a run is open', async () => {
    vi.mocked(expeditionSiteApi.getCurrentRoom).mockResolvedValue(mockRoom)
    const store = useExpeditionSiteStore()

    const result = await store.fetchCurrentRoom('exploration-1')

    expect(result).toEqual(mockRoom)
    expect(store.room).toEqual(mockRoom)
  })

  it('sets error and rethrows on API rejection', async () => {
    vi.mocked(expeditionSiteApi.listAvailableSites).mockRejectedValue(new Error('boom'))
    const store = useExpeditionSiteStore()

    await expect(store.fetchAvailableSites('exploration-1')).rejects.toThrow('boom')

    expect(store.error).toBe('Failed to load available expedition sites')
    expect(store.isLoading).toBe(false)
  })

  it('clears a previous error when retrying', async () => {
    vi.mocked(expeditionSiteApi.listAvailableSites).mockResolvedValue([mockSite])
    const store = useExpeditionSiteStore()
    store.error = 'Some error'

    await store.fetchAvailableSites('exploration-1')

    expect(store.error).toBeNull()
    expect(store.availableSites).toEqual([mockSite])
  })

  it('reset clears room, availableSites, and error', async () => {
    vi.mocked(expeditionSiteApi.listAvailableSites).mockResolvedValue([mockSite])
    vi.mocked(expeditionSiteApi.enterSite).mockResolvedValue(mockRoom)
    const store = useExpeditionSiteStore()
    await store.fetchAvailableSites('exploration-1')
    await store.enterSite('exploration-1', 'red_rocket')
    store.error = 'Some error'

    store.reset()

    expect(store.room).toBeNull()
    expect(store.availableSites).toEqual([])
    expect(store.error).toBeNull()
  })

  it('scopes room state to the exploration id and resets on a different one', async () => {
    vi.mocked(expeditionSiteApi.enterSite).mockResolvedValue(mockRoom)
    const store = useExpeditionSiteStore()

    await store.enterSite('exploration-1', 'red_rocket')
    expect(store.room).toEqual(mockRoom)
    expect(store.currentExplorationId).toBe('exploration-1')

    const otherRoom = { ...mockRoom, exploration_id: 'exploration-2' }
    vi.mocked(expeditionSiteApi.enterSite).mockResolvedValue(otherRoom)
    store.error = 'stale error'
    await store.enterSite('exploration-2', 'red_rocket')

    expect(store.room).toEqual(otherRoom)
    expect(store.error).toBeNull()
    expect(store.currentExplorationId).toBe('exploration-2')
  })

  it('clears a stale room before acting on a different exploration even on failure', async () => {
    vi.mocked(expeditionSiteApi.enterSite).mockResolvedValue(mockRoom)
    const store = useExpeditionSiteStore()
    await store.enterSite('exploration-1', 'red_rocket')
    expect(store.room).toEqual(mockRoom)

    vi.mocked(expeditionSiteApi.resolveNode).mockRejectedValue(new Error('boom'))
    await expect(store.resolveNode('exploration-2')).rejects.toThrow('boom')

    expect(store.room).toBeNull()
    expect(store.error).toBe('Failed to resolve expedition node')
    expect(store.currentExplorationId).toBe('exploration-2')
  })

  it('scopes fetchCurrentRoom to the exploration id', async () => {
    vi.mocked(expeditionSiteApi.enterSite).mockResolvedValue(mockRoom)
    const store = useExpeditionSiteStore()
    await store.enterSite('exploration-1', 'red_rocket')

    vi.mocked(expeditionSiteApi.getCurrentRoom).mockResolvedValue(null)
    await store.fetchCurrentRoom('exploration-2')

    expect(store.room).toBeNull()
    expect(store.currentExplorationId).toBe('exploration-2')
  })

  it('ignores an old explorer response that arrives after the new one', async () => {
    let finishOld!: (room: SiteRoomView | null) => void
    vi.mocked(expeditionSiteApi.getCurrentRoom)
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finishOld = resolve
          })
      )
      .mockResolvedValueOnce({ ...mockRoom, exploration_id: 'exploration-2' })
    const store = useExpeditionSiteStore()

    const oldRequest = store.fetchCurrentRoom('exploration-1')
    await store.fetchCurrentRoom('exploration-2')
    finishOld(mockRoom)
    await oldRequest

    expect(store.currentExplorationId).toBe('exploration-2')
    expect(store.room?.exploration_id).toBe('exploration-2')
  })

  it('ignores a pending response after reset', async () => {
    let finish!: (room: SiteRoomView | null) => void
    vi.mocked(expeditionSiteApi.getCurrentRoom).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve
        })
    )
    const store = useExpeditionSiteStore()
    const request = store.fetchCurrentRoom('exploration-1')

    store.reset()
    finish(mockRoom)
    await request

    expect(store.room).toBeNull()
    expect(store.currentExplorationId).toBeNull()
  })

  it('reset clears the scoped exploration id', async () => {
    vi.mocked(expeditionSiteApi.enterSite).mockResolvedValue(mockRoom)
    const store = useExpeditionSiteStore()
    await store.enterSite('exploration-1', 'red_rocket')

    store.reset()

    expect(store.currentExplorationId).toBeNull()
  })

  it('isTerminal flags terminal statuses', () => {
    expect(SITE_TERMINAL_STATUSES).toEqual(['retreated', 'cleared', 'died'])
    expect(isTerminal('retreated')).toBe(true)
    expect(isTerminal('cleared')).toBe(true)
    expect(isTerminal('died')).toBe(true)
    expect(isTerminal('entered')).toBe(false)
    expect(isTerminal('in_room')).toBe(false)
    expect(isTerminal('unknown')).toBe(false)
  })
})
