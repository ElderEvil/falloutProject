import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { useAuthStore } from '@/modules/auth/stores/auth'
import type { ArenaRoomState } from '@/modules/rooms/api/arena'
import { useArenaRoom } from '@/modules/rooms/composables/useArenaRoom'

const mocks = vi.hoisted(() => ({
  fetchState: vi.fn(),
  getRoom: vi.fn(),
  playSound: vi.fn(),
}))

vi.mock('@/modules/rooms/stores/arena', () => ({
  useArenaStore: () => ({
    fetchState: mocks.fetchState,
    getRoom: mocks.getRoom,
  }),
}))

vi.mock('@/core/composables/useSound', () => ({
  useSound: () => ({ playSound: mocks.playSound }),
}))

describe('useArenaRoom attack feedback', () => {
  const room = ref<ArenaRoomState>({} as ArenaRoomState)
  let controller: ReturnType<typeof useArenaRoom>
  let wrapper: ReturnType<typeof mount>

  beforeEach(() => {
    vi.useFakeTimers()
    setActivePinia(createPinia())
    room.value = {
      team_a: [{ id: 'fighter-a', health: 100, active_skill: null }],
      team_b: [{ id: 'fighter-b', health: 100, active_skill: null }],
      events: [],
      countdown_remaining: 0,
      fight_started: true,
      match_done: false,
    } as unknown as ArenaRoomState
    mocks.fetchState.mockResolvedValue(true)
    mocks.getRoom.mockImplementation(() => room.value)
    useAuthStore().token = 'test-token'
  })

  afterEach(() => {
    wrapper?.unmount()
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('clears the attacker and team highlight after the action recovers', async () => {
    const Harness = defineComponent({
      setup() {
        controller = useArenaRoom('vault-1', 'arena-1')
        return () => null
      },
    })
    wrapper = mount(Harness)
    await flushPromises()

    room.value = {
      ...room.value,
      team_b: [{ ...room.value.team_b[0], health: 90 }],
      events: [
        {
          id: 'event-1',
          kind: 'hit',
          actor_id: 'fighter-a',
          message: 'Hit',
          action: {
            actor_id: 'fighter-a',
            effect: 'strike',
            skill: null,
            targets: [{ target_id: 'fighter-b', damage: 10, health_before: 100, health_after: 90 }],
          },
          timestamp: new Date().toISOString(),
        },
      ],
    } as ArenaRoomState
    await controller.refresh()

    expect(controller.attackingFighterId.value).toBe('fighter-a')
    expect(controller.attackingTeam.value).toBe('A')

    await vi.advanceTimersByTimeAsync(350)

    expect(controller.attackingFighterId.value).toBeNull()
    expect(controller.attackingTeam.value).toBeNull()
  })

  it('holds displayed HP until the corresponding attack impacts', async () => {
    wrapper = mount(
      defineComponent({
        setup() {
          controller = useArenaRoom('vault-1', 'arena-1')
          return () => null
        },
      })
    )
    await flushPromises()

    room.value = {
      ...room.value,
      team_b: [{ ...room.value.team_b[0], health: 90 }],
      events: [
        {
          id: 'impact-1',
          round_seq: 1,
          kind: 'hit',
          actor_id: 'fighter-a',
          message: 'Hit',
          action: {
            actor_id: 'fighter-a',
            effect: 'strike',
            skill: null,
            targets: [{ target_id: 'fighter-b', damage: 10, health_before: 100, health_after: 90 }],
          },
        },
      ],
    } as ArenaRoomState
    await controller.refresh()

    expect(controller.roomState.value?.team_b[0].health).toBe(100)
    expect(controller.damageNumbers.value).toEqual([])
    await vi.advanceTimersByTimeAsync(150)
    expect(controller.roomState.value?.team_b[0].health).toBe(90)
    expect(controller.damageNumbers.value).toEqual([
      expect.objectContaining({ fighterId: 'fighter-b', amount: 10 }),
    ])
  })

  it('keeps the ring visible and delays the finish cue until the final action recovers', async () => {
    wrapper = mount(
      defineComponent({
        setup() {
          controller = useArenaRoom('vault-1', 'arena-1')
          return () => null
        },
      })
    )
    await flushPromises()
    room.value = {
      ...room.value,
      match_done: true,
      fight_started: false,
      team_b: [{ ...room.value.team_b[0], health: 0 }],
      events: [
        {
          id: 'last-hit',
          round_seq: 1,
          kind: 'hit',
          message: 'KO',
          actor_id: 'fighter-a',
          action: {
            actor_id: 'fighter-a',
            targets: [{ target_id: 'fighter-b', damage: 100, health_before: 100, health_after: 0 }],
          },
        },
        { id: 'finish', kind: 'finish', round_seq: 1, message: 'Done' },
      ],
    } as ArenaRoomState
    await controller.refresh()
    expect(controller.roomState.value?.match_done).toBe(false)
    expect(controller.roomState.value?.fight_started).toBe(true)
    expect(mocks.playSound).not.toHaveBeenCalledWith('arenaFinish')
    await vi.advanceTimersByTimeAsync(150)
    expect(controller.roomState.value?.team_b[0].health).toBe(0)
    expect(controller.damageNumbers.value[0].amount).toBe(100)
    await vi.advanceTimersByTimeAsync(200)
    expect(controller.roomState.value?.match_done).toBe(true)
    expect(mocks.playSound).toHaveBeenCalledWith('arenaFinish')
  })
})
