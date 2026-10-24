import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'
import { useRoomRush } from '@/modules/rooms/composables/useRoomRush'
import type { Room, RoomRushResult } from '@/modules/rooms/models/room'
import { useAuthStore } from '@/modules/auth/stores/auth'

const { mockStore, notifyErrorOnce, playSound } = vi.hoisted(() => ({
  mockStore: {
    fetchRushQuote: vi.fn(),
    rushRoom: vi.fn(),
  },
  notifyErrorOnce: vi.fn(),
  playSound: vi.fn(),
}))

vi.mock('@/modules/rooms/stores/room', () => ({
  useRoomStore: () => mockStore,
}))

vi.mock('@/core/utils/errorHandler', () => ({
  getErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Unknown error'),
  notifyErrorOnce,
}))

vi.mock('@/core/composables/useSound', () => ({
  useSound: () => ({ playSound }),
}))

const room = { id: 'room-1', name: 'Power Generator' } as Room
const quote = {
  can_rush: true,
  blocked_reason: null,
  fail_chance: 23,
  success_chance: 77,
  stacks: 2,
  max_stacks: 6,
  avg_ability: 8,
  avg_luck: 7,
  worker_count: 2,
  payout: { power: 12, food: 0, water: 0, stimpack: 0, radaway: 0 },
  caps_chance: 35,
  eligible_incidents: ['fire'],
  next_stack_penalty: 10,
}

const result: RoomRushResult = {
  outcome: 'success',
  payout: { power: 12, food: 0, water: 0, stimpack: 0, radaway: 0 },
  caps: 120,
  xp_per_worker: 25,
  happiness_delta: 10,
  incident_id: null,
  incident_type: null,
  stacks_after: 3,
  next_fail_chance: 33,
  message: 'The rush succeeded.',
}

describe('useRoomRush', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    useAuthStore().token = 'token'
  })

  it('loads the quote when the modal opens', async () => {
    mockStore.fetchRushQuote.mockResolvedValueOnce(quote)
    const { quote: current, isLoadingQuote } = useRoomRush(ref(room), ref('vault-1'), ref(true))

    await flushPromises()

    expect(mockStore.fetchRushQuote).toHaveBeenCalledWith('room-1', 'token')
    expect(current.value).toEqual(quote)
    expect(isLoadingQuote.value).toBe(false)
  })

  it('does not fetch a quote while the modal is closed', () => {
    useRoomRush(ref(room), ref('vault-1'), ref(false))

    expect(mockStore.fetchRushQuote).not.toHaveBeenCalled()
  })

  it('opens the confirmation only for a rushable quote', async () => {
    mockStore.fetchRushQuote.mockResolvedValueOnce(quote)
    const { requestRush, showConfirmation } = useRoomRush(ref(room), ref('vault-1'), ref(true))
    await flushPromises()

    requestRush()

    expect(showConfirmation.value).toBe(true)
  })

  it('submits the rush, keeps the result, and refreshes the quote', async () => {
    mockStore.fetchRushQuote
      .mockResolvedValueOnce(quote)
      .mockResolvedValueOnce({ ...quote, stacks: 3, fail_chance: 33, success_chance: 67 })
    mockStore.rushRoom.mockResolvedValueOnce(result)
    const {
      confirmRush,
      result: currentResult,
      quote: currentQuote,
    } = useRoomRush(ref(room), ref('vault-1'), ref(true))
    await flushPromises()

    await confirmRush()

    expect(mockStore.rushRoom).toHaveBeenCalledWith('room-1', 'token', 'vault-1')
    expect(playSound).toHaveBeenCalledWith('rushGo', 'sfx')
    expect(currentResult.value).toEqual(result)
    expect(currentQuote.value?.stacks).toBe(3)
    expect(currentQuote.value?.fail_chance).toBe(33)
    expect(mockStore.fetchRushQuote).toHaveBeenCalledTimes(2)
  })

  it('surfaces a quote failure', async () => {
    mockStore.fetchRushQuote.mockRejectedValueOnce(new Error('Quote unavailable'))
    const { error, quote: current } = useRoomRush(ref(room), ref('vault-1'), ref(true))

    await flushPromises()

    expect(current.value).toBeNull()
    expect(error.value).toBe('Quote unavailable')
  })

  it('reports a rush transport failure', async () => {
    mockStore.fetchRushQuote.mockResolvedValueOnce(quote)
    mockStore.rushRoom.mockRejectedValueOnce(new Error('Incident active'))
    const { confirmRush, error } = useRoomRush(ref(room), ref('vault-1'), ref(true))
    await flushPromises()

    await confirmRush()

    expect(error.value).toBe('Incident active')
    expect(notifyErrorOnce).toHaveBeenCalled()
  })
})
