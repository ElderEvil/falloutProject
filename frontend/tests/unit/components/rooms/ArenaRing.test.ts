import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ArenaRing from '@/modules/rooms/components/ArenaRing.vue'
import { TooltipProvider } from '@/core/components/ui/tooltip'

const fighter = (id: string, name: string, health = 100) => ({
  id,
  name,
  health,
  max_health: 100,
  level: 5,
  power: 10,
  active_skill: null,
  creature_key: null,
  is_bot: false,
  side: 'A' as const,
  slot: 0,
})

const ringState = (teamA: unknown[], teamB: unknown[]) => ({
  room_id: 'room-1',
  next_attack_team: 'A',
  team_a: teamA,
  team_b: teamB,
})

const baseProps = {
  state: ringState([fighter('a1', 'Ada')], [fighter('b1', 'Brutus')]),
  attackingTeam: null,
  damageNumbers: [],
}

const mountRing = (props: Record<string, unknown> = {}) =>
  mount(ArenaRing, {
    props: { ...baseProps, ...props },
    global: { plugins: [TooltipProvider] },
  })

describe('ArenaRing fighter positions (issue #1086)', () => {
  it('centers single fighters in a duel: no lane-offset classes', () => {
    const wrapper = mountRing()
    const fighters = wrapper.findAll('.ring-fighter')
    expect(fighters).toHaveLength(2)
    for (const fighter of fighters) {
      expect(fighter.classes()).not.toContain('left-4')
      expect(fighter.classes()).not.toContain('right-4')
      expect(fighter.classes()).not.toContain('left-2')
      expect(fighter.classes()).not.toContain('right-2')
    }
    wrapper.unmount()
  })

  it('keeps mirrored lane offsets for two-fighter brawl lines', () => {
    const wrapper = mountRing({
      state: ringState(
        [fighter('a1', 'Ada'), fighter('a2', 'Ash')],
        [fighter('b1', 'Brutus'), fighter('b2', 'Bo')]
      ),
    })
    const fighters = wrapper.findAll('.ring-fighter')
    expect(fighters).toHaveLength(4)
    expect(fighters[0].classes()).toContain('left-4')
    expect(fighters[1].classes()).toContain('right-2')
    expect(fighters[2].classes()).toContain('right-4')
    expect(fighters[3].classes()).toContain('left-2')
    wrapper.unmount()
  })
})
