import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'
import { FEEDBACK_TIMING_MS } from '@/core/config/feedback'
import { useRoomRush } from '@/modules/rooms/composables/useRoomRush'
import type { Room, RoomRushResult } from '@/modules/rooms/models/room'

const { mockStore, notifyErrorOnce, playSound, stopSound, showFeedback } = vi.hoisted(() => ({
  mockStore: {
    fetchRushQuote: vi.fn(),
    rushRoom: vi.fn(),
  },
  notifyErrorOnce: vi.fn(),
  playSound: vi.fn(),
  stopSound: vi.fn(),
  showFeedback: vi.fn(),
}))

vi.mock('@/modules/rooms/stores/room', () => ({
  useRoomStore: () => mockStore,
}))

vi.mock('@/core/utils/errorHandler', () => ({
  getErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Unknown error'),
  notifyErrorOnce,
}))

vi.mock('@/core/composables/useSound', () => ({
  useSound: () => ({ playSound, stopSound }),
}))

vi.mock('@/core/composables/useVaultBoyFeedback', () => ({
  useVaultBoyFeedback: () => ({ show: showFeedback }),
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
  })

  it('does not load a quote until the rush popup opens', async () => {
    const state = useRoomRush(ref(room), ref('vault-1'), ref(true))
    await flushPromises()

    expect(mockStore.fetchRushQuote).not.toHaveBeenCalled()

    mockStore.fetchRushQuote.mockResolvedValueOnce(quote)
    state.requestRush()
    await flushPromises()

    expect(mockStore.fetchRushQuote).toHaveBeenCalledWith('room-1')
    expect(state.showRushDialog.value).toBe(true)
    expect(state.quote.value).toEqual(quote)
    expect(playSound).toHaveBeenCalledWith('rushMode', 'music')
  })

  it('does not fetch a quote while the room modal is closed', () => {
    useRoomRush(ref(room), ref('vault-1'), ref(false))

    expect(mockStore.fetchRushQuote).not.toHaveBeenCalled()
  })

  it('closes the popup and stops rush music on cancel', async () => {
    mockStore.fetchRushQuote.mockResolvedValueOnce(quote)
    const state = useRoomRush(ref(room), ref('vault-1'), ref(true))
    state.requestRush()
    await flushPromises()

    state.cancelRush()

    expect(state.showRushDialog.value).toBe(false)
    expect(state.quote.value).toBeNull()
    expect(stopSound).toHaveBeenCalledWith('rushMode')
  })

  it('delays the success cue and feedback, then plays the resource cue', async () => {
    mockStore.fetchRushQuote.mockResolvedValueOnce(quote)
    mockStore.rushRoom.mockResolvedValueOnce(result)
    const state = useRoomRush(ref(room), ref('vault-1'), ref(true))
    state.requestRush()
    await flushPromises()
    vi.useFakeTimers()

    try {
      await state.confirmRush()

      expect(mockStore.rushRoom).toHaveBeenCalledWith('room-1', 'vault-1')
      expect(mockStore.fetchRushQuote).toHaveBeenCalledTimes(1)
      expect(state.showRushDialog.value).toBe(false)
      expect(state.quote.value).toBeNull()
      expect(stopSound).toHaveBeenCalledWith('rushMode')
      expect(playSound).toHaveBeenCalledWith('rushGo', 'sfx')
      expect(showFeedback).not.toHaveBeenCalled()

      await vi.advanceTimersByTimeAsync(FEEDBACK_TIMING_MS.rushDelay)

      expect(playSound).toHaveBeenCalledWith('rushSuccess', 'sfx')
      expect(playSound).toHaveBeenCalledWith('resourceCollected', 'sfx')
      expect(showFeedback).toHaveBeenCalledWith(
        {
          animation: 'rush-success',
          title: 'RUSH OK',
          message: '+12 POWER · +120 CAPS · +10 HAPPINESS · +25 XP',
          vaultId: 'vault-1',
          durationMs: FEEDBACK_TIMING_MS.rushDuration,
        },
        { priority: true }
      )
    } finally {
      vi.useRealTimers()
    }
  })

  it('plays the failure cue without the resource cue after the delay', async () => {
    mockStore.fetchRushQuote.mockResolvedValueOnce(quote)
    mockStore.rushRoom.mockResolvedValueOnce({
      ...result,
      outcome: 'failure',
      payout: { power: 0, food: 0, water: 0, stimpack: 0, radaway: 0 },
      caps: 0,
      xp_per_worker: 0,
      happiness_delta: -10,
      incident_type: 'fire',
    })
    const state = useRoomRush(ref(room), ref('vault-1'), ref(true))
    state.requestRush()
    await flushPromises()
    vi.useFakeTimers()

    try {
      await state.confirmRush()
      expect(showFeedback).not.toHaveBeenCalled()

      await vi.advanceTimersByTimeAsync(FEEDBACK_TIMING_MS.rushDelay)

      expect(playSound).toHaveBeenCalledWith('rushFail', 'sfx')
      expect(playSound).not.toHaveBeenCalledWith('resourceCollected', 'sfx')
      expect(showFeedback).toHaveBeenCalledWith(
        expect.objectContaining({
          animation: 'rush-failure',
          title: 'RUSH FAIL',
          message: 'FIRE · −10 HAPPINESS',
          durationMs: FEEDBACK_TIMING_MS.rushDuration,
        }),
        { priority: true }
      )
    } finally {
      vi.useRealTimers()
    }
  })

  it('surfaces a quote failure inside the popup', async () => {
    mockStore.fetchRushQuote.mockRejectedValueOnce(new Error('Quote unavailable'))
    const state = useRoomRush(ref(room), ref('vault-1'), ref(true))
    state.requestRush()
    await flushPromises()

    expect(state.quote.value).toBeNull()
    expect(state.error.value).toBe('Quote unavailable')
    expect(state.isLoadingQuote.value).toBe(false)
    expect(state.showRushDialog.value).toBe(true)
  })

  it('keeps the popup open and reports a rush failure', async () => {
    mockStore.fetchRushQuote.mockResolvedValueOnce(quote)
    mockStore.rushRoom.mockRejectedValueOnce(new Error('Incident active'))
    const state = useRoomRush(ref(room), ref('vault-1'), ref(true))
    state.requestRush()
    await flushPromises()

    await state.confirmRush()

    expect(state.error.value).toBe('Incident active')
    expect(state.showRushDialog.value).toBe(true)
    expect(showFeedback).not.toHaveBeenCalled()
    expect(notifyErrorOnce).toHaveBeenCalled()
  })

  it('ignores an older quote after switching rooms', async () => {
    let resolveOld!: (value: typeof quote) => void
    mockStore.fetchRushQuote
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveOld = resolve
          })
      )
      .mockResolvedValueOnce({ ...quote, fail_chance: 45, success_chance: 55 })
    const selectedRoom = ref<Room | null>(room)
    const state = useRoomRush(selectedRoom, ref('vault-1'), ref(true))

    state.requestRush()
    selectedRoom.value = { ...room, id: 'room-2' }
    await flushPromises()
    state.requestRush()
    await flushPromises()

    expect(state.quote.value?.fail_chance).toBe(45)

    resolveOld(quote)
    await flushPromises()

    expect(state.quote.value?.fail_chance).toBe(45)
  })

  it('closes the popup when the parent room closes', async () => {
    mockStore.fetchRushQuote.mockResolvedValueOnce(quote)
    const open = ref(true)
    const state = useRoomRush(ref(room), ref('vault-1'), open)
    state.requestRush()
    await flushPromises()
    expect(state.showRushDialog.value).toBe(true)

    open.value = false
    await flushPromises()

    expect(state.showRushDialog.value).toBe(false)
  })

  it('ignores a rush response from a closed modal session', async () => {
    let resolveRush!: (value: RoomRushResult) => void
    mockStore.fetchRushQuote.mockResolvedValue(quote)
    mockStore.rushRoom.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveRush = resolve
        })
    )
    const open = ref(true)
    const state = useRoomRush(ref(room), ref('vault-1'), open)
    state.requestRush()
    await flushPromises()
    const pending = state.confirmRush()

    open.value = false
    await flushPromises()
    open.value = true
    await flushPromises()
    resolveRush(result)
    await pending

    expect(showFeedback).not.toHaveBeenCalled()
  })
})
