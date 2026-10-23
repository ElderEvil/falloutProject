import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ArenaPreview from '@/modules/rooms/components/ArenaPreview.vue'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import type { ArenaFighter, ArenaRoomState } from '@/modules/rooms/api/arena'

const fighter = (id: string, overrides: Partial<ArenaFighter> = {}): ArenaFighter => ({
  id,
  name: id,
  level: 5,
  health: 80,
  max_health: 100,
  power: 10,
  is_creature: false,
  is_robot: false,
  active_skill: {
    name: 'Aimed Shot',
    description: 'Extra attack on your next team turn.',
    charge: 100,
    queued: false,
  },
  ...overrides,
})

const state = (overrides: Partial<ArenaRoomState> = {}): ArenaRoomState => ({
  room_id: 'arena',
  room_name: 'Arena',
  tier: 3,
  available_modes: ['duel', 'brawl', 'hunt'],
  mode: 'duel',
  next_attack_team: 'A',
  fighter_a_id: 'a',
  fighter_b_id: 'b',
  fighters: [fighter('a'), fighter('b')],
  team_a: [fighter('a')],
  team_b: [fighter('b')],
  roster: [],
  fight_ready: true,
  can_start: true,
  fight_started: false,
  match_done: false,
  countdown_remaining: 0,
  winner_name: null,
  events: [],
  ...overrides,
})

describe('ArenaPreview', () => {
  it('renders both teams and their meters in setup', () => {
    const wrapper = mount(ArenaPreview, { props: { state: state() } })

    expect(wrapper.find('.arena-preview').exists()).toBe(true)
    expect(wrapper.find('.arena-ring').exists()).toBe(false)
    expect(wrapper.text()).toContain('TEAM A')
    expect(wrapper.text()).toContain('TEAM B')
    expect(wrapper.findAll('.combatant-meters')).toHaveLength(2)
    expect(wrapper.get('[aria-label="Arena preview"]').text()).toContain('a')
    expect(wrapper.get('[aria-label="Arena preview"]').text()).toContain('b')
  })

  it('maps arena dwellers to body-size classes', () => {
    const teen = fighter('a', { age_group: 'teen', race: 'human' })
    const mutant = fighter('b', { age_group: 'adult', race: 'super_mutant' })
    const wrapper = mount(ArenaPreview, {
      props: { state: state({ team_a: [teen], team_b: [mutant] }) },
    })
    const exposed = wrapper.vm as unknown as { bodySizeFor: (fighter: typeof teen) => string }

    expect(exposed.bodySizeFor(teen)).toBe('small')
    expect(exposed.bodySizeFor(mutant)).toBe('large')
  })

  it('does not apply the curated portrait zoom in the arena', () => {
    const curated = fighter('a', { image_url: '/static/dweller_images/test.png' })
    const wrapper = mount(ArenaPreview, {
      props: { state: state({ team_a: [curated], team_b: [] }) },
    })

    expect(wrapper.findComponent(DwellerPortrait).props('zoom')).toBe(false)
  })

  it('shows silhouette slots for empty team positions', () => {
    const wrapper = mount(ArenaPreview, {
      props: {
        state: state({
          team_a: [],
          team_b: [],
          fighter_a_id: null,
          fighter_b_id: null,
          fighters: [],
        }),
      },
    })

    expect(wrapper.findAll('.arena-empty-slot')).toHaveLength(2)
    expect(wrapper.findAll('.arena-dweller-silhouette')).toHaveLength(2)
  })

  it('switches to the ring once the fight starts', () => {
    const wrapper = mount(ArenaPreview, {
      props: { state: state({ fight_started: true }) },
    })

    expect(wrapper.find('.arena-ring').exists()).toBe(true)
    expect(wrapper.find('.arena-preview').exists()).toBe(false)
    expect(wrapper.findAll('.fighter-meters')).toHaveLength(2)
  })

  it('keeps setup actions read-only', () => {
    const wrapper = mount(ArenaPreview, { props: { state: state() } })

    expect(
      wrapper.get('button[aria-label^="Use Aimed Shot for a"]').attributes('disabled')
    ).toBeDefined()
  })

  it('passes fighter skill activation through during the fight', async () => {
    const wrapper = mount(ArenaPreview, {
      props: { state: state({ fight_started: true }) },
    })

    await wrapper.get('button[aria-label^="Use Aimed Shot for a"]').trigger('click')

    expect(wrapper.emitted('skill')).toEqual([['a']])
  })
})
