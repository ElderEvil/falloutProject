import { afterEach, describe, expect, it } from 'vite-plus/test'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import ArenaRing from '@/modules/rooms/components/ArenaRing.vue'
import type { ArenaFighter, ArenaRoomState } from '@/modules/rooms/api/arena'

enableAutoUnmount(afterEach)

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
    icon: 'gun-rifle',
    description: 'Extra attack on your next team turn.',
    charge: 100,
    queued: false,
  },
  ...overrides,
})
const state = (
  teamA = [fighter('Alpha'), fighter('Charlie')],
  teamB = [fighter('Bravo'), fighter('Delta')]
): ArenaRoomState => ({
  room_id: 'arena',
  room_name: 'Arena',
  tier: 3,
  mode: 'brawl',
  available_modes: ['duel', 'brawl', 'hunt'],
  fighter_a_id: teamA[0]?.id ?? null,
  fighter_b_id: teamB[0]?.id ?? null,
  team_a: teamA,
  team_b: teamB,
  fighters: [...teamA, ...teamB],
  roster: [],
  fight_ready: true,
  can_start: false,
  fight_started: true,
  match_done: false,
  next_attack_team: 'A',
  countdown_remaining: 0,
  winner_name: null,
  events: [],
})
const render = (room = state(), pendingSkills = new Set<string>(), skillEnabled = true) =>
  mount(ArenaRing, {
    props: { state: room, skillEnabled, pendingSkills, attackingTeam: null, damageNumbers: [] },
    attachTo: document.body,
  })

describe('Arena ring', () => {
  it('shows equipped pets beside their owners without adding combatants or meters', async () => {
    const wrapper = render(
      state(
        [
          fighter('Alpha', {
            pet: { name: 'CX404', image_url: '/static/pet_images/FOS CX404.png' },
          }),
        ],
        [fighter('Bravo')]
      )
    )
    expect(wrapper.get('img[alt="CX404, Alpha’s pet"]').exists()).toBe(true)
    expect(wrapper.findAll('.ring-fighter')).toHaveLength(2)
    expect(wrapper.findAll('.fighter-meters')).toHaveLength(2)
    await wrapper.get('img[alt="CX404, Alpha’s pet"]').trigger('error')
    await flushPromises()
    expect(wrapper.find('img[alt="CX404, Alpha’s pet"]').exists()).toBe(false)
    expect(wrapper.get('[role="img"][aria-label="CX404, Alpha’s pet"]').exists()).toBe(true)
    await wrapper.setProps({
      state: state(
        [
          fighter('Alpha', {
            pet: {
              name: 'American Shorthair',
              image_url: '/static/pet_images/FOS American Shorthair.png',
            },
          }),
        ],
        [fighter('Bravo')]
      ),
    })
    expect(wrapper.get('img[alt="American Shorthair, Alpha’s pet"]').exists()).toBe(true)
    expect(wrapper.find('[aria-label="CX404, Alpha’s pet"]').exists()).toBe(false)
  })

  it('anchors dweller portraits at the top so faces remain visible', () => {
    const room = state(
      [fighter('Alpha', { thumbnail_url: '/static/dwellers/alpha.webp' })],
      [fighter('Bravo')]
    )
    const wrapper = render(room)

    expect(wrapper.get('img[alt="Alpha"]').attributes('style')).toContain(
      'object-position: center top'
    )
  })

  it('floats the health and skill meters above the fighter portrait', () => {
    const wrapper = render(
      state([fighter('Alpha', { thumbnail_url: '/static/dwellers/alpha.webp' })])
    )
    const plate = wrapper.get('.fighter-meters')
    const portrait = wrapper.get('.fighter-portrait')

    expect(plate.element.nextElementSibling).toBe(portrait.element)
    expect(portrait.find('img[alt="Alpha"]').exists()).toBe(true)
    expect(plate.get('[role="progressbar"][aria-label="Alpha HP"]').exists()).toBe(true)
    expect(plate.get('[role="progressbar"][aria-label="Alpha skill charge"]').exists()).toBe(true)
  })

  it('animates only the current attacker and skips dead fighters', () => {
    const room = state([fighter('Alpha')], [fighter('Bravo', { health: 0 })])
    const wrapper = mount(ArenaRing, {
      props: {
        state: room,
        skillEnabled: true,
        pendingSkills: new Set<string>(),
        attackingTeam: null,
        attackingFighterId: 'Alpha',
        damageNumbers: [],
      },
      attachTo: document.body,
    })

    const actors = wrapper.findAll('.ring-fighter')
    expect(actors[0].attributes('aria-current')).toBe('true')
    expect(actors[1].attributes('aria-current')).toBeUndefined()
  })

  it('skips the attack animation for a knocked-out attacker', () => {
    const room = state([fighter('Alpha', { health: 0 })], [fighter('Bravo')])
    const wrapper = mount(ArenaRing, {
      props: {
        state: room,
        skillEnabled: true,
        pendingSkills: new Set<string>(),
        attackingTeam: null,
        attackingFighterId: 'Alpha',
        damageNumbers: [],
      },
      attachTo: document.body,
    })

    expect(wrapper.findAll('.ring-fighter')[0].attributes('aria-current')).toBeUndefined()
  })

  it('places each ready dweller activation on its paired target and emits the attacker ID', async () => {
    const wrapper = render()
    const marker = wrapper.get('button[aria-label="Use Aimed Shot from Alpha on Bravo"]')
    expect(marker.get('[data-skill-icon]').attributes('data-skill-icon')).toBe('gun-rifle')
    await marker.trigger('click')
    expect(wrapper.emitted('skill')).toEqual([['Alpha']])
    expect(wrapper.find('button[aria-label="Use Aimed Shot from Charlie on Delta"]').exists()).toBe(
      true
    )
    expect(wrapper.get('[aria-label="Alpha HP"]').attributes('aria-valuenow')).toBe('80')
  })

  it.each(['uncharged', 'queued', 'pending', 'knocked out', 'countdown', 'finished'])(
    'hides target activation when %s',
    (reason) => {
      const alpha = fighter('Alpha')
      if (reason === 'uncharged') alpha.active_skill!.charge = 99
      if (reason === 'queued') alpha.active_skill!.queued = true
      if (reason === 'knocked out') alpha.health = 0
      const room = state([alpha], [fighter('Bravo', { active_skill: null })])
      if (reason === 'finished') room.match_done = true
      const wrapper = render(
        room,
        new Set(reason === 'pending' ? ['Alpha'] : []),
        !['countdown', 'finished'].includes(reason)
      )
      expect(wrapper.find('button[aria-label^="Use Aimed Shot from Alpha"]').exists()).toBe(false)
      expect(
        wrapper.get('button[aria-label^="Use Aimed Shot for Alpha"]').attributes('disabled')
      ).toBeDefined()
    }
  )

  it('shares the surviving target after a KO and removes markers immediately while pending', async () => {
    const room = state(undefined, [fighter('Bravo', { health: 0 }), fighter('Delta')])
    const wrapper = render(room)
    expect(wrapper.findAll('button[aria-label$="on Delta"]')).toHaveLength(2)
    await wrapper.setProps({ pendingSkills: new Set(['Alpha']) })
    expect(wrapper.find('button[aria-label^="Use Aimed Shot from Alpha"]').exists()).toBe(false)
    expect(wrapper.find('button[aria-label="Use Aimed Shot from Charlie on Delta"]').exists()).toBe(
      true
    )
  })

  it('shows the animated countdown over the preview and removes it when combat starts', async () => {
    const room = { ...state(), countdown_remaining: 3 }
    const wrapper = render(room, new Set(), false)
    expect(wrapper.get('[role="status"]').text()).toMatch(/STARTING IN\s*3/)
    await wrapper.setProps({ state: { ...room, countdown_remaining: 2 } })
    expect(wrapper.get('.countdown-number').text()).toBe('2')
    await wrapper.setProps({ state: { ...room, countdown_remaining: 0 }, skillEnabled: true })
    expect(wrapper.find('.countdown-number').exists()).toBe(false)
  })

  it('exposes themed skill tooltips with the attacker, skill and target', async () => {
    const wrapper = render()
    await wrapper.get('button[aria-label="Use Aimed Shot from Alpha on Bravo"]').trigger('focus')
    await flushPromises()
    const tooltip = document.body.querySelector('[data-slot="tooltip-content"]')!
    expect(tooltip.textContent).toContain('Alpha · Aimed Shot')
    expect(tooltip.textContent).toContain('Activate skill against Bravo')
    expect(
      wrapper.get('button[aria-label="Use Aimed Shot from Alpha on Bravo"]').attributes('title')
    ).toBeUndefined()
  })
})
