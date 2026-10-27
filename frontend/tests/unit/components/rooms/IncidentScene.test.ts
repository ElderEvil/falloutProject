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

const mountScene = (props: Record<string, unknown> = {}) =>
  mount(IncidentScene, {
    props: { incident: incident(), dwellers: [], ...props },
  })

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
      incident: incident({
        status: 'resolved',
        events: [
          {
            id: 'last',
            kind: 'hit',
            message: 'Final hit',
            data: null,
            action: { actor_id: 'd1', targets: [{ target_id: 'threat', damage: 1 }] },
          },
        ],
      }),
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
      incident: incident({
        status: 'resolved',
        events: [
          {
            id: 'last',
            kind: 'hit',
            message: 'Final hit',
            data: null,
            action: { actor_id: 'd1', targets: [{ target_id: 'threat', damage: 1 }] },
          },
        ],
      }),
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

  it('lunges the attacker and flashes the target when a round lands', async () => {
    const wrapper = mountScene({
      dwellers: [dweller({ id: 'd1', first_name: 'Alice' })],
    })

    await wrapper.setProps({
      incident: incident({
        events: [
          { id: 'e1', kind: 'round', message: 'Trade fire.', data: { damage_to_threat: 12 } },
        ],
      }),
    })
    await flushPromises()
    await nextTick()

    expect(wrapper.find('.combat-lunge-right').exists()).toBe(true)
    expect(wrapper.find('.combat-impact').exists()).toBe(true)
    wrapper.unmount()
  })

  it('flashes the defenders and lunges the threat when they take damage', async () => {
    const wrapper = mountScene({
      dwellers: [dweller({ id: 'd1', first_name: 'Alice' })],
    })

    await wrapper.setProps({
      incident: incident({
        events: [
          { id: 'e1', kind: 'round', message: 'They hit back.', data: { damage_to_dwellers: 7 } },
        ],
      }),
    })
    await flushPromises()
    await nextTick()

    expect(wrapper.find('.combat-lunge-left').exists()).toBe(true)
    expect(wrapper.find('.combat-impact').exists()).toBe(true)
    wrapper.unmount()
  })

  it('sums the latest round of per-attack hits for the floating damage', () => {
    const wrapper = mountScene({
      dwellers: [dweller({ id: 'd1', first_name: 'Alice' })],
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
    const wrapper = mountScene({
      incident: incident({ type: 'fire', family: 'hazard', objective: 'contain' }),
    })

    expect(wrapper.text()).toContain('ROOM HAZARD')
    expect(wrapper.text()).not.toContain('remaining')
  })

  it('reports how many rooms the incident affects', () => {
    const wrapper = mountScene({
      incident: incident({
        type: 'fire',
        family: 'hazard',
        objective: 'contain',
        risk: { kind: 'spread', rooms_affected: 3 },
      }),
    })

    expect(wrapper.text()).toContain('3 rooms affected')
  })

  it('paints the room backdrop when an image is available', () => {
    const wrapper = mountScene({ roomImageUrl: 'https://cdn.test/room.png' })
    const backdrop = wrapper.find('.scene-backdrop')

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

  it('omits the backdrop when no image is available', () => {
    expect(mountScene().find('.scene-backdrop').exists()).toBe(false)
  })

  it('burns an environmental flame cluster for a fire hazard', () => {
    const wrapper = mountScene({
      incident: incident({ type: 'fire', family: 'hazard', objective: 'contain' }),
    })

    const fire = wrapper.find('.hazard-fire')
    expect(fire.exists()).toBe(true)
    expect(fire.attributes('aria-hidden')).toBe('true')
    expect(wrapper.findAll('.hazard-flame')).toHaveLength(3)
    expect(wrapper.find('.flame-outer').exists()).toBe(true)
    expect(wrapper.find('.flame-inner').exists()).toBe(true)
    expect(wrapper.find('.hazard-icon').exists()).toBe(false)
    expect(fire.find('.combatant-motion').exists()).toBe(false)
  })

  it('uses the generated raider sprite for raider attacks', () => {
    const wrapper = mountScene()

    const raider = wrapper.get('img[alt="Raider"]')
    expect(raider.attributes('src')).toContain('/raider_images/variants/')
    // Humanoids keep the dweller frame; only creatures get the extra threat scale.
    expect(raider.element.parentElement?.className).not.toContain('scale-125')
  })

  it('gives creatures the extra threat scale', () => {
    const wrapper = mountScene({
      incident: incident({ type: 'deathclaw_attack', family: 'intrusion', objective: 'defeat' }),
    })

    const creature = wrapper.get('img[alt="Deathclaw"]')
    expect(creature.element.parentElement?.className).toContain('sm:scale-125')
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

  it('does not show helpers who moved out of the incident room', () => {
    const wrapper = mountScene({
      dwellers: [dweller({ id: 'd1', first_name: 'Alice', room_id: 'room-9' })],
      team: [
        {
          id: 't1',
          team_id: 'team-1',
          dweller_id: 'd1',
          slot_number: 1,
          status: 'dispatched',
          created_at: null,
          updated_at: null,
        },
      ],
    })

    expect(wrapper.text()).not.toContain('Alice')
    expect(wrapper.text()).not.toContain('DISPATCHED')
  })

  it('keeps room occupants visible even with an empty helper roster', () => {
    const wrapper = mountScene({
      dwellers: [dweller({ id: 'd1', first_name: 'Alice', room_id: 'room-1' })],
      team: [],
    })

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
    const wrapper = mountScene({
      dwellers: [dweller({ id: 'd1', first_name: 'Alice', level: 12, health: 100 })],
    })

    expect(wrapper.get('.dweller-name-badge').text()).toBe('Alice')
    expect(wrapper.text()).not.toContain('POW')
    expect(wrapper.text()).not.toContain('Lv 12')
    expect(wrapper.find('.dweller-health').exists()).toBe(false)
  })

  it('adds a compact health bar to the name badge when a responder is hurt', () => {
    const wrapper = mountScene({
      dwellers: [dweller({ id: 'd1', first_name: 'Alice', health: 40, max_health: 100 })],
    })

    expect(wrapper.get('.dweller-health-fill').attributes('style')).toContain('width: 40%')
    expect(wrapper.text()).toContain('Alice: 40 of 100 HP')
  })
})

describe('Incident room preview', () => {
  it('uses real responder artwork under the name badge', () => {
    const wrapper = mountScene({
      dwellers: [dweller({ thumbnail_url: '/static/portraits/alice.png' })],
    })
    expect(wrapper.get('img[alt="Alice"]').attributes('src')).toContain(
      '/static/portraits/alice.png'
    )
    expect(wrapper.get('.dweller-name-badge').text()).toBe('Alice')
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
    const wrapper = mountScene({
      team: [
        {
          id: 't1',
          team_id: 'team-1',
          dweller_id: 'missing',
          slot_number: 2,
          status: 'dispatched',
          created_at: null,
          updated_at: null,
        },
      ],
    })
    expect(wrapper.text()).toContain('Responder 2')
    expect(wrapper.text()).not.toContain('DISPATCHED')
    expect(wrapper.text()).not.toContain('No responders assigned')
  })
})
