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

const render = (
  room = state(),
  {
    pendingSkills = new Set<string>(),
    skillEnabled = true,
    attackingFighterId = null as string | null,
  } = {}
) =>
  mount(ArenaRing, {
    props: {
      state: room,
      skillEnabled,
      pendingSkills,
      attackingTeam: null,
      attackingFighterId,
      damageNumbers: [],
    },
    attachTo: document.body,
  })

const attackButton = (wrapper: ReturnType<typeof render>, from: string, on: string) =>
  wrapper.get(`button[aria-label="Use Aimed Shot from ${from} on ${on}"]`)

describe('Arena ring', () => {
  it('shows equipped pets beside their owners without adding combatants or meters', async () => {
    const withPet = (pet: { name: string; image_url: string }) =>
      state([fighter('Alpha', { pet })], [fighter('Bravo')])
    const wrapper = render(
      withPet({ name: 'CX404', image_url: '/static/pet_images/FOS CX404.png' })
    )
    expect(wrapper.get('img[alt="CX404, Alpha’s pet"]').exists()).toBe(true)
    expect(wrapper.findAll('.ring-fighter')).toHaveLength(2)
    expect(wrapper.findAll('.fighter-meters')).toHaveLength(2)

    await wrapper.get('img[alt="CX404, Alpha’s pet"]').trigger('error')
    await flushPromises()
    expect(wrapper.find('img[alt="CX404, Alpha’s pet"]').exists()).toBe(false)
    expect(wrapper.get('[role="img"][aria-label="CX404, Alpha’s pet"]').exists()).toBe(true)

    await wrapper.setProps({
      state: withPet({
        name: 'American Shorthair',
        image_url: '/static/pet_images/FOS American Shorthair.png',
      }),
    })
    expect(wrapper.get('img[alt="American Shorthair, Alpha’s pet"]').exists()).toBe(true)
    expect(wrapper.find('[aria-label="CX404, Alpha’s pet"]').exists()).toBe(false)
  })

  it('anchors dweller portraits at the top so faces remain visible', () => {
    const wrapper = render(
      state(
        [fighter('Alpha', { thumbnail_url: '/static/dwellers/alpha.webp' })],
        [fighter('Bravo')]
      )
    )

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

  it.each([
    ['a live attacker', 80, true],
    ['a knocked-out attacker', 0, false],
  ])('animates only the current attacker, never %s', (_label, health, current) => {
    const wrapper = render(
      state([fighter('Alpha', { health })], [fighter('Bravo', { health: 0 })]),
      {
        attackingFighterId: 'Alpha',
      }
    )

    const actors = wrapper.findAll('.ring-fighter')
    expect(actors[0].attributes('aria-current')).toBe(current ? 'true' : undefined)
    expect(actors[1].attributes('aria-current')).toBeUndefined()
  })

  it('places each ready dweller activation on its paired target and emits the attacker ID', async () => {
    const wrapper = render()
    const marker = attackButton(wrapper, 'Alpha', 'Bravo')
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
      const wrapper = render(room, {
        pendingSkills: new Set(reason === 'pending' ? ['Alpha'] : []),
        skillEnabled: !['countdown', 'finished'].includes(reason),
      })

      expect(wrapper.find('button[aria-label^="Use Aimed Shot from Alpha"]').exists()).toBe(false)
      expect(
        wrapper.get('button[aria-label^="Use Aimed Shot for Alpha"]').attributes('disabled')
      ).toBeDefined()
    }
  )

  it('shares the surviving target after a KO and removes markers immediately while pending', async () => {
    const wrapper = render(state(undefined, [fighter('Bravo', { health: 0 }), fighter('Delta')]))
    expect(wrapper.findAll('button[aria-label$="on Delta"]')).toHaveLength(2)

    await wrapper.setProps({ pendingSkills: new Set(['Alpha']) })

    expect(wrapper.find('button[aria-label^="Use Aimed Shot from Alpha"]').exists()).toBe(false)
    expect(wrapper.find('button[aria-label="Use Aimed Shot from Charlie on Delta"]').exists()).toBe(
      true
    )
  })

  it('shows the animated countdown over the preview and removes it when combat starts', async () => {
    const room = { ...state(), countdown_remaining: 3 }
    const wrapper = render(room, { skillEnabled: false })
    expect(wrapper.get('[role="status"]').text()).toMatch(/STARTING IN\s*3/)

    await wrapper.setProps({ state: { ...room, countdown_remaining: 2 } })
    expect(wrapper.get('.countdown-number').text()).toBe('2')

    await wrapper.setProps({ state: { ...room, countdown_remaining: 0 }, skillEnabled: true })
    expect(wrapper.find('.countdown-number').exists()).toBe(false)
  })

  it('exposes themed skill tooltips with the attacker, skill and target', async () => {
    const wrapper = render()
    await attackButton(wrapper, 'Alpha', 'Bravo').trigger('focus')
    await flushPromises()

    const tooltip = document.body.querySelector('[data-slot="tooltip-content"]')!
    expect(tooltip.textContent).toContain('Alpha · Aimed Shot')
    expect(tooltip.textContent).toContain('Activate skill against Bravo')
    expect(attackButton(wrapper, 'Alpha', 'Bravo').attributes('title')).toBeUndefined()
  })
})
