import { afterEach, describe, expect, it, vi } from 'vite-plus/test'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import IncidentScene from '@/modules/rooms/components/IncidentScene.vue'
import type { Incident } from '@/modules/combat/models/incident'

// jsdom never evaluates media queries, so the reduced-motion contract is guarded
// at the source level — it is the only way to keep this a11y rule from silently rotting.
import sceneSource from '@/modules/rooms/components/IncidentScene.vue?raw'

const { playSound } = vi.hoisted(() => ({ playSound: vi.fn() }))
vi.mock('@/core/composables/useSound', () => ({ useSound: () => ({ playSound }) }))

const incident = (overrides: Partial<Incident> = {}): Incident =>
  ({
    id: 'incident-1',
    room_id: 'room-1',
    type: 'raider_attack',
    family: 'intrusion',
    objective: 'defeat',
    difficulty: 4,
    progress: { current: 30, target: 100, label: 'Threat' },
    risk: { kind: 'casualties', rooms_affected: 1 },
    response: { label: 'Send' },
    events: [],
    ...overrides,
  }) as Incident

const dweller = (overrides: Record<string, unknown> = {}) => ({
  id: 'd1',
  first_name: 'Alice',
  level: 5,
  health: 90,
  max_health: 100,
  age_group: 'adult',
  room_id: 'room-1',
  status: 'idle',
  combat_power: 42,
  ...overrides,
})

const teamEntry = (
  dwellerId: string,
  overrides: Record<string, unknown> = {}
): Record<string, unknown> => ({
  id: `t-${dwellerId}`,
  team_id: 'team-1',
  dweller_id: dwellerId,
  slot_number: 1,
  status: 'dispatched',
  created_at: null,
  updated_at: null,
  ...overrides,
})

const mountScene = (props: Record<string, unknown> = {}) =>
  mount(IncidentScene, { props: { incident: incident(), dwellers: [], ...props } })

const finalHit = {
  id: 'last',
  kind: 'hit',
  message: 'Final hit',
  data: null,
  action: { actor_id: 'd1', targets: [{ target_id: 'threat', damage: 1 }] },
}

const hazard = (overrides: Record<string, unknown> = {}) =>
  incident({ type: 'fire', family: 'hazard', objective: 'contain', ...overrides })

describe('Incident action playback', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('animates responders individually and changes only the hit target HP at impact', async () => {
    vi.useFakeTimers()
    const wrapper = mountScene({
      dwellers: [dweller({ health: 100 }), dweller({ id: 'd2', first_name: 'Bob', health: 100 })],
    })
    const attack = (id: string, actor: string, target: string, health: number | null = null) => ({
      id,
      kind: 'hit',
      message: 'Hit',
      data: null,
      action: {
        actor_id: actor,
        effect: 'strike' as const,
        skill: null,
        targets: [
          {
            target_id: target,
            damage: 10,
            health_before: health === null ? null : 100,
            health_after: health,
          },
        ],
      },
    })
    await wrapper.setProps({
      incident: incident({
        events: [
          attack('1', 'd1', 'threat'),
          attack('2', 'd2', 'threat'),
          attack('3', 'threat', 'd1', 90),
        ],
      }),
      dwellers: [dweller({ health: 90 }), dweller({ id: 'd2', first_name: 'Bob', health: 100 })],
    })
    const actors = wrapper.findAll('.incident-responder')
    expect(actors[0].attributes('aria-current')).toBe('true')
    expect(actors[1].attributes('aria-current')).toBeUndefined()
    expect(wrapper.text()).not.toContain('Alice: 90')
    expect(wrapper.findAll('.damage-number')).toHaveLength(0)
    expect(playSound).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(150)
    expect(playSound).toHaveBeenCalledExactlyOnceWith('incidentHit', 'sfx')
    expect(wrapper.findAll('.damage-number')).toHaveLength(1)
    await vi.advanceTimersByTimeAsync(200)
    expect(actors[1].attributes('aria-current')).toBe('true')
    await vi.advanceTimersByTimeAsync(499)
    expect(wrapper.text()).not.toContain('Alice: 90')
    await vi.advanceTimersByTimeAsync(1)
    expect(wrapper.text()).toContain('Alice: 90 of 100 HP')
    expect(actors[1].text()).not.toContain('-10')
    wrapper.unmount()
  })

  it('finishes only after the final resolved attack recovers', async () => {
    vi.useFakeTimers()
    const wrapper = mountScene({ dwellers: [dweller()] })
    await wrapper.setProps({
      incident: incident({ status: 'resolved', events: [finalHit] }),
    })
    expect(wrapper.emitted('playbackComplete')).toBeUndefined()
    await vi.advanceTimersByTimeAsync(350)
    expect(wrapper.emitted('playbackComplete')).toEqual([['incident-1']])
    wrapper.unmount()
  })

  it('keeps returning responders available for their final attacks', async () => {
    vi.useFakeTimers()
    const wrapper = mountScene({ dwellers: [dweller()] })
    // Helpers can return to their posting before the final journal refresh arrives.
    await wrapper.setProps({ dwellers: [] })
    expect(wrapper.text()).not.toContain('Alice')
    await wrapper.setProps({
      incident: incident({ status: 'resolved', events: [finalHit] }),
    })
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.get('.incident-responder').attributes('aria-current')).toBe('true')
    await vi.advanceTimersByTimeAsync(350)
    expect(wrapper.emitted('playbackComplete')).toEqual([['incident-1']])
    wrapper.unmount()
  })
})

describe('IncidentScene', () => {
  it('shows only the dwellers stationed in the incident room', () => {
    const wrapper = mountScene({
      dwellers: [
        dweller({ id: 'd1', first_name: 'Alice', room_id: 'room-1' }),
        dweller({ id: 'd2', first_name: 'Bob', room_id: 'room-9' }),
      ],
    })

    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).not.toContain('Bob')
  })

  it('states when no responders are assigned', () => {
    expect(mountScene().text()).toContain('No responders assigned')
  })

  it.each([
    ['the responders strike', { damage_to_threat: 12 }, 'combat-lunge-right'],
    ['the threat strikes back', { damage_to_dwellers: 7 }, 'combat-lunge-left'],
  ])('lunges and flashes when %s', async (_label, data, lungeClass) => {
    const wrapper = mountScene({ dwellers: [dweller()] })

    await wrapper.setProps({
      incident: incident({ events: [{ id: 'e1', kind: 'round', message: 'Round.', data }] }),
    })
    await flushPromises()
    await nextTick()

    expect(wrapper.find(`.${lungeClass}`).exists()).toBe(true)
    expect(wrapper.find('.combat-impact').exists()).toBe(true)
    wrapper.unmount()
  })

  it('sums the latest round of per-attack hits for the floating damage', () => {
    const wrapper = mountScene({
      dwellers: [dweller()],
      incident: incident({
        events: [
          { id: 'e1', kind: 'turn', message: 'Responders attack', data: null },
          {
            id: 'e2',
            kind: 'hit',
            message: 'Raider hits Alice for 3',
            data: { damage_to_dwellers: 3 },
          },
          {
            id: 'e3',
            kind: 'hit',
            message: 'Raider hits Alice for 4',
            data: { damage_to_dwellers: 4 },
          },
        ],
      }),
    })

    expect(wrapper.find('.floating-effect').text()).toBe('-7')
  })

  it('renders the remaining threat count for a defeat objective', () => {
    const wrapper = mountScene({
      incident: incident({ progress: { current: 30, target: 100, label: 'Threat' } }),
    })

    expect(wrapper.text()).toContain('THREAT')
    expect(wrapper.text()).toContain('70 remaining')
    expect(wrapper.text()).not.toContain('ROOM HAZARD')
  })

  it('renders containment instead of an enemy row for a hazard objective', () => {
    const wrapper = mountScene({ incident: hazard() })

    expect(wrapper.text()).toContain('ROOM HAZARD')
    expect(wrapper.text()).not.toContain('remaining')
  })

  it('reports how many rooms the incident affects', () => {
    const wrapper = mountScene({
      incident: hazard({ risk: { kind: 'spread', rooms_affected: 3 } }),
    })

    expect(wrapper.text()).toContain('3 rooms affected')
  })

  it('paints the room backdrop when an image is available', () => {
    const backdrop = mountScene({ roomImageUrl: 'https://cdn.test/room.png' }).find(
      '.scene-backdrop'
    )

    expect(backdrop.exists()).toBe(true)
    expect(backdrop.attributes('src')).toBe('https://cdn.test/room.png')
  })

  it('falls back to grid art on detail-scene failure and hides a failed fallback', async () => {
    const wrapper = mountScene({ roomImageUrl: '/arena.webp', fallbackImageUrl: '/grid.png' })
    await wrapper.find('.scene-backdrop').trigger('error')
    expect(wrapper.find('.scene-backdrop').attributes('src')).toBe('/grid.png')
    await wrapper.find('.scene-backdrop').trigger('error')
    expect(wrapper.find('.scene-backdrop').exists()).toBe(false)
    await wrapper.setProps({ roomImageUrl: '/another.webp' })
    expect(wrapper.find('.scene-backdrop').attributes('src')).toBe('/another.webp')
  })

  it('burns an environmental flame cluster for a fire hazard', () => {
    const wrapper = mountScene({ incident: hazard() })

    const fire = wrapper.find('.hazard-fire')
    expect(fire.exists()).toBe(true)
    expect(fire.attributes('aria-hidden')).toBe('true')
    expect(wrapper.findAll('.hazard-flame')).toHaveLength(3)
    expect(wrapper.find('.hazard-icon').exists()).toBe(false)
  })

  it.each([
    ['raider_attack', 'Raider', '/raider_images/variants/', false],
    ['deathclaw_attack', 'Deathclaw', '/assembled/deathclaw.webp', true],
  ])('renders %s artwork with the right threat scale', (type, alt, src, scaled) => {
    const threat = mountScene({ incident: incident({ type }) }).get(`img[alt="${alt}"]`)

    expect(threat.attributes('src')).toContain(src)
    // Only creatures get the extra threat scale; humanoids keep the dweller frame.
    expect((threat.element.parentElement?.className ?? '').includes('sm:scale-125')).toBe(scaled)
  })

  it('uses creature artwork for a non-fire containment incident', () => {
    const wrapper = mountScene({
      incident: incident({
        type: 'radroach_infestation',
        family: 'infestation',
        objective: 'contain',
      }),
    })

    expect(wrapper.find('.hazard-flame').exists()).toBe(false)
    expect(wrapper.get('img[alt="Radroach"]').attributes('src')).toContain(
      '/assembled/radroach.webp'
    )
  })

  it('shows an equipped pet with the shared ground shadow', () => {
    const wrapper = mountScene({
      dwellers: [dweller({ pet: { name: 'Dogmeat', image_url: '/pet.png' } })],
    })

    const pet = wrapper.find('.combat-pet')
    expect(pet.exists()).toBe(true)
    expect(pet.find('img').attributes('src')).toContain('/pet.png')
    expect(pet.find('.actor-ground-shadow').exists()).toBe(true)
  })

  it('plays the resolution cue when an active scene finishes', async () => {
    const wrapper = mountScene({ incident: incident({ status: 'active' }), dwellers: [dweller()] })
    await wrapper.setProps({ incident: incident({ status: 'resolved' }) })

    expect(playSound).toHaveBeenCalledWith('incidentVictory', 'sfx')
    wrapper.unmount()
  })

  it('does not show helpers who moved out of the incident room', () => {
    const wrapper = mountScene({
      dwellers: [dweller({ room_id: 'room-9' })],
      team: [teamEntry('d1')],
    })

    expect(wrapper.text()).not.toContain('Alice')
    expect(wrapper.text()).not.toContain('DISPATCHED')
  })

  it('keeps room occupants visible even with an empty helper roster', () => {
    const wrapper = mountScene({ dwellers: [dweller()], team: [] })

    expect(wrapper.text()).not.toContain('No responders assigned')
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).not.toContain('RESIDENT')
  })

  it('stops the flame animation under prefers-reduced-motion', () => {
    expect(sceneSource).toMatch(
      /@media \(prefers-reduced-motion: reduce\) \{[\s\S]*?\.flame-outer,\s*\.flame-inner \{\s*animation: none;/
    )
  })

  it('shows only the responder name when they are unhurt', () => {
    const wrapper = mountScene({ dwellers: [dweller({ level: 12, health: 100 })] })

    expect(wrapper.get('.dweller-name-badge').text()).toBe('Alice')
    expect(wrapper.text()).not.toContain('POW')
    expect(wrapper.text()).not.toContain('Lv 12')
    expect(wrapper.find('.dweller-health').exists()).toBe(false)
  })

  it('adds a compact health bar to the name badge when a responder is hurt', () => {
    const wrapper = mountScene({ dwellers: [dweller({ health: 40 })] })

    expect(wrapper.get('.dweller-health-fill').attributes('style')).toContain('width: 40%')
    expect(wrapper.text()).toContain('Alice: 40 of 100 HP')
  })
})

describe('Incident room preview', () => {
  it('uses real responder artwork under the name badge, anchored to the lane floor', () => {
    const wrapper = mountScene({
      dwellers: [dweller({ thumbnail_url: '/static/portraits/alice.png' })],
    })

    expect(wrapper.get('img[alt="Alice"]').attributes('src')).toContain(
      '/static/portraits/alice.png'
    )
    expect(wrapper.get('.dweller-name-badge').text()).toBe('Alice')
    expect(wrapper.get('.incident-dweller-portrait').attributes('style')).toContain(
      'object-position: center bottom'
    )
    expect(wrapper.find('[role="progressbar"][aria-label="Alice health"]').exists()).toBe(false)
  })

  it('shows creature artwork instead of repeated threat glyphs', () => {
    const wrapper = mountScene({ incident: incident({ type: 'deathclaw_attack' }) })

    expect(wrapper.get('img[alt="Deathclaw"]').attributes('src')).toContain(
      '/assembled/deathclaw.webp'
    )
    expect(wrapper.text()).toContain('70 remaining')
  })

  it('retains a dispatched responder when their dweller data has not loaded', () => {
    const wrapper = mountScene({ team: [teamEntry('missing', { slot_number: 2 })] })

    expect(wrapper.text()).toContain('Responder 2')
    expect(wrapper.text()).not.toContain('DISPATCHED')
    expect(wrapper.text()).not.toContain('No responders assigned')
  })

  it('caps the lane at six readable fighters and reports the hidden helpers', () => {
    const dwellers = Array.from({ length: 8 }, (_, index) =>
      dweller({ id: `d${index}`, first_name: `Defender${index}` })
    )
    const wrapper = mountScene({ dwellers })

    expect(wrapper.findAll('.incident-responder')).toHaveLength(6)
    expect(wrapper.text()).toContain('RESPONDERS · 8')
    const overflow = wrapper.get('.incident-overflow')
    expect(overflow.text()).toBe('+2')
    expect(overflow.attributes('aria-label')).toContain('Defender6')
    expect(overflow.attributes('aria-label')).toContain('Defender7')
  })

  it('scales a large dweller with the same body ratio as the room preview', () => {
    const wrapper = mountScene({
      dwellers: [
        dweller({
          thumbnail_url: '/static/portraits/mutant.png',
          visual_attributes: { race: 'super_mutant' },
        }),
      ],
    })

    expect(wrapper.get('.incident-actor').attributes('style')).toContain(
      '--dweller-body-scale: 1.18'
    )
  })
})
