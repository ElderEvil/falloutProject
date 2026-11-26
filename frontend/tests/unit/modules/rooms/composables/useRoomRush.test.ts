import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ref, type Ref } from 'vue'
import { FEEDBACK_TIMING_MS } from '@/core/config/feedback'
import { useRoomRush } from '@/modules/rooms/composables/useRoomRush'
import type { Room, RoomRushResult } from '@/modules/rooms/models/room'

const { mockStore, notifyErrorOnce, playSound, stopSound, showFeedback } = vi.hoisted(() => ({
  mockStore: { fetchRushQuote: vi.fn(), rushRoom: vi.fn() },
  notifyErrorOnce: vi.fn(),
  playSound: vi.fn(),
  stopSound: vi.fn(),
  showFeedback: vi.fn(),
}))

vi.mock('@/modules/rooms/stores/room', () => ({ useRoomStore: () => mockStore }))

vi.mock('@/core/utils/errorHandler', () => ({
  getErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Unknown error'),
  notifyErrorOnce,
}))

vi.mock('@/core/composables/useSound', () => ({ useSound: () => ({ playSound, stopSound }) }))
vi.mock('@/core/composables/useVaultBoyFeedback', () => ({
  useVaultBoyFeedback: () => ({ show: showFeedback }),
}))

const room = { id: 'room-1', name: 'Power Generator' } as Room
const emptyPayout = { power: 0, food: 0, water: 0, stimpack: 0, radaway: 0 }
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
  payout: { ...emptyPayout, power: 12 },
  caps_chance: 35,
  eligible_incidents: ['fire'],
  next_stack_penalty: 10,
}

const result: RoomRushResult = {
  outcome: 'success',
  payout: { ...emptyPayout, power: 12 },
  caps: 120,
  xp_per_worker: 25,
  happiness_delta: 10,
  incident_id: null,
  incident_type: null,
  stacks_after: 3,
  next_fail_chance: 33,
  message: 'The rush succeeded.',
}

const failure: RoomRushResult = {
  ...result,
  outcome: 'failure',
  payout: emptyPayout,
  caps: 0,
  xp_per_worker: 0,
  happiness_delta: -10,
  incident_type: 'fire',
}

const deferred = <T>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((settle) => (resolve = settle))
  return { promise, resolve }
}

/** Mount the composable with the rush dialog already open on `quoteReply`. */
const openRush = async (
  quoteReply: typeof quote = quote,
  {
    open = ref(true),
    selected = ref<Room | null>(room),
  }: { open?: Ref<boolean>; selected?: Ref<Room | null> } = {}
) => {
  mockStore.fetchRushQuote.mockResolvedValueOnce(quoteReply)
  const state = useRoomRush(selected, ref('vault-1'), open)
  state.requestRush()
  await flushPromises()
  return state
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
    const state = await openRush()

    state.cancelRush()

    expect(state.showRushDialog.value).toBe(false)
    expect(state.quote.value).toBeNull()
    expect(stopSound).toHaveBeenCalledWith('rushMode')
  })

  it.each([
    {
      label: 'success',
      outcome: result,
      cue: 'rushSuccess',
      animation: 'rush-success',
      title: 'RUSH OK',
      message: '+12 POWER · +120 CAPS · +10 HAPPINESS · +25 XP',
      resourceCue: true,
    },
    {
      label: 'failure',
      outcome: failure,
      cue: 'rushFail',
      animation: 'rush-failure',
      title: 'RUSH FAIL',
      message: 'FIRE · −10 HAPPINESS',
      resourceCue: false,
    },
  ])('delays the $label cue and feedback', async (row) => {
    const state = await openRush()
    mockStore.rushRoom.mockResolvedValueOnce(row.outcome)
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

      expect(playSound).toHaveBeenCalledWith(row.cue, 'sfx')
      expect(playSound.mock.calls.some(([key]) => key === 'resourceCollected')).toBe(
        row.resourceCue
      )
      expect(showFeedback).toHaveBeenCalledWith(
        expect.objectContaining({
          animation: row.animation,
          title: row.title,
          message: row.message,
          vaultId: 'vault-1',
          durationMs: FEEDBACK_TIMING_MS.rushDuration,
        }),
        { priority: true }
      )
    } finally {
      vi.useRealTimers()
    }
  })

  it('surfaces a quote failure inside the popup', async () => {
    const state = useRoomRush(ref(room), ref('vault-1'), ref(true))
    mockStore.fetchRushQuote.mockRejectedValueOnce(new Error('Quote unavailable'))
    state.requestRush()
    await flushPromises()

    expect(state.quote.value).toBeNull()
    expect(state.error.value).toBe('Quote unavailable')
    expect(state.isLoadingQuote.value).toBe(false)
    expect(state.showRushDialog.value).toBe(true)
  })

  it('keeps the popup open and reports a rush failure', async () => {
    const state = await openRush()
    mockStore.rushRoom.mockRejectedValueOnce(new Error('Incident active'))

    await state.confirmRush()

    expect(state.error.value).toBe('Incident active')
    expect(state.showRushDialog.value).toBe(true)
    expect(showFeedback).not.toHaveBeenCalled()
    expect(notifyErrorOnce).toHaveBeenCalled()
  })

  it('ignores an older quote after switching rooms', async () => {
    const old = deferred<typeof quote>()
    mockStore.fetchRushQuote
      .mockImplementationOnce(() => old.promise)
      .mockResolvedValueOnce({ ...quote, fail_chance: 45, success_chance: 55 })
    const selectedRoom = ref<Room | null>(room)
    const state = useRoomRush(selectedRoom, ref('vault-1'), ref(true))

    state.requestRush()
    selectedRoom.value = { ...room, id: 'room-2' }
    await flushPromises()
    state.requestRush()
    await flushPromises()

    expect(state.quote.value?.fail_chance).toBe(45)

    old.resolve(quote)
    await flushPromises()

    expect(state.quote.value?.fail_chance).toBe(45)
  })

  it.each([
    ['resources_full', 'Vault storage for this resource is full.'],
    ['no_yield', 'This rush would produce nothing right now.'],
  ])('refuses a blocked quote (%s) with its message', async (blockedReason, message) => {
    const state = await openRush({
      ...quote,
      can_rush: false,
      blocked_reason: blockedReason,
      payout: emptyPayout,
    })

    expect(state.blockedMessage.value).toBe(message)
    await state.confirmRush()
    expect(mockStore.rushRoom).not.toHaveBeenCalled()
  })

  it('closes the popup when the parent room closes', async () => {
    const open = ref(true)
    const state = await openRush(quote, { open })
    expect(state.showRushDialog.value).toBe(true)

    open.value = false
    await flushPromises()

    expect(state.showRushDialog.value).toBe(false)
  })

  it('ignores a rush response from a closed modal session', async () => {
    const rush = deferred<RoomRushResult>()
    mockStore.fetchRushQuote.mockResolvedValue(quote)
    mockStore.rushRoom.mockImplementationOnce(() => rush.promise)
    const open = ref(true)
    const state = useRoomRush(ref(room), ref('vault-1'), open)
    state.requestRush()
    await flushPromises()
    const pending = state.confirmRush()

    open.value = false
    await flushPromises()
    open.value = true
    await flushPromises()
    rush.resolve(result)
    await pending

    expect(showFeedback).not.toHaveBeenCalled()
  })
})
