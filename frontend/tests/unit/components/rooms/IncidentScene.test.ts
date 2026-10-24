import { describe, expect, it } from 'vite-plus/test'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import IncidentScene from '@/modules/rooms/components/IncidentScene.vue'
import type { Incident } from '@/modules/combat/models/incident'

// jsdom never evaluates media queries, so the reduced-motion contract is guarded
// at the source level — it is the only way to keep this a11y rule from silently rotting.
import sceneSource from '@/modules/rooms/components/IncidentScene.vue?raw'

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

  it('burns a two-layer flame for a fire hazard', () => {
    const wrapper = mountScene({
      incident: incident({ type: 'fire', family: 'hazard', objective: 'contain' }),
    })

    const flame = wrapper.find('.hazard-flame')
    expect(flame.exists()).toBe(true)
    expect(flame.attributes('aria-hidden')).toBe('true')
    expect(wrapper.find('.flame-outer').exists()).toBe(true)
    expect(wrapper.find('.flame-inner').exists()).toBe(true)
    expect(wrapper.find('.hazard-icon').exists()).toBe(false)
  })

  it('uses the generated raider sprite for raider attacks', () => {
    const wrapper = mountScene()

    expect(wrapper.get('img[alt="Raider"]').attributes('src')).toContain('/assembled/raider.webp')
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
    expect(wrapper.text()).toContain('RESIDENT')
  })

  it('stops the flame animation under prefers-reduced-motion', () => {
    expect(sceneSource).toMatch(
      /@media \(prefers-reduced-motion: reduce\) \{[\s\S]*?\.flame-outer,\s*\.flame-inner \{\s*animation: none;/
    )
  })

  it('shows the level of each combatant alongside their power', () => {
    const wrapper = mountScene({
      dwellers: [dweller({ id: 'd1', first_name: 'Alice', level: 12 })],
    })

    expect(wrapper.text()).toContain('POW 42')
    expect(wrapper.text()).toContain('Lv 12')
  })
})

describe('Incident room preview', () => {
  it('uses real responder artwork and a labelled health meter', () => {
    const wrapper = mountScene({
      dwellers: [dweller({ thumbnail_url: '/static/portraits/alice.png' })],
    })
    expect(wrapper.get('img[alt="Alice"]').attributes('src')).toContain(
      '/static/portraits/alice.png'
    )
    expect(
      wrapper.get('[role="progressbar"][aria-label="Alice health"]').attributes('aria-valuenow')
    ).toBe('90')
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
    expect(wrapper.text()).toContain('DISPATCHED')
    expect(wrapper.text()).not.toContain('No responders assigned')
  })
})
