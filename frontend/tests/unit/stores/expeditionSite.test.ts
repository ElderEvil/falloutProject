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

  it('clearError clears the error', () => {
    const store = useExpeditionSiteStore()
    store.error = 'Some error'

    store.clearError()

    expect(store.error).toBeNull()
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
