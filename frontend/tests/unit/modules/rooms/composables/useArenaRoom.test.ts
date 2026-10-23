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

  it('clears the team highlight during the gap between queued attacks', async () => {
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
      events: [
        {
          id: 'event-1',
          kind: 'hit',
          actor_id: 'fighter-a',
          message: 'Hit',
          timestamp: new Date().toISOString(),
        },
      ],
    } as ArenaRoomState
    await controller.refresh()

    expect(controller.attackingFighterId.value).toBe('fighter-a')
    expect(controller.attackingTeam.value).toBe('A')

    await vi.advanceTimersByTimeAsync(320)

    expect(controller.attackingFighterId.value).toBeNull()
    expect(controller.attackingTeam.value).toBeNull()
  })
})
