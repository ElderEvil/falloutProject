import { afterEach, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import SiteCombatScene from '@/modules/exploration/components/SiteCombatScene.vue'
import type { SiteRoomView } from '@/modules/exploration/api/expeditionSite'

const { playSound } = vi.hoisted(() => ({ playSound: vi.fn() }))
vi.mock('@/core/composables/useSound', () => ({ useSound: () => ({ playSound }) }))
afterEach(() => {
  vi.useRealTimers()
  vi.clearAllMocks()
})

it.each([
  [null, 'incidentHit', 150],
  ['Aimed Shot', 'arenaSkill', 250],
] as const)(
  'plays %s at impact without replaying history or duplicate snapshots',
  async (skill, sound, windup) => {
    vi.useFakeTimers()
    const room: SiteRoomView = {
      exploration_id: 'exp',
      site_id: 'mart',
      site_name: 'Mart',
      room_index: 0,
      room_total: 1,
      room_name: 'Mart',
      flavor: 'Supplies ahead.',
      node: { kind: 'combat', prompt: 'Fight' },
      can_retreat: true,
      status: 'in_room',
      outcome: null,
      finale_paid: false,
      dweller_health: 50,
      dweller_max_health: 50,
      combat_state: {
        round: 0,
        fighters: [],
        events: [{ id: '0', message: 'Ready', action: null }],
      },
    }
    const wrapper = mount(SiteCombatScene, {
      props: { room, running: true, loading: false },
      global: { stubs: { ArenaRing: true } },
    })
    expect(playSound).not.toHaveBeenCalled()
    const updated: SiteRoomView = {
      ...room,
      combat_state: {
        ...room.combat_state!,
        round: 1,
        events: [
          ...room.combat_state!.events,
          {
            id: '1',
            message: 'Attack',
            action: { actor_id: 'lucy', actor_body: 'human', effect: 'shot', skill, targets: [] },
          },
        ],
      },
    }
    await wrapper.setProps({ room: updated })
    await vi.advanceTimersByTimeAsync(windup - 1)
    expect(playSound).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    expect(playSound).toHaveBeenCalledExactlyOnceWith(sound, 'sfx')
    await wrapper.setProps({ room: structuredClone(updated) })
    await vi.advanceTimersByTimeAsync(600)
    expect(playSound).toHaveBeenCalledTimes(1)
    await wrapper.setProps({
      room: {
        ...updated,
        combat_state: {
          ...updated.combat_state!,
          events: [
            ...updated.combat_state!.events,
            { ...updated.combat_state!.events[1]!, id: '2' },
          ],
        },
      },
    })
    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(600)
    expect(playSound).toHaveBeenCalledTimes(1)
  }
)
