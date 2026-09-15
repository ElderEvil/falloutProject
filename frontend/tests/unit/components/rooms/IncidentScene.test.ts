import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
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
  is_adult: true,
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

  it('renders the remaining threat count for a defeat objective', () => {
    const wrapper = mountScene({ incident: incident({ progress: { current: 30, target: 100, label: 'Threat' } }) })

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
    expect(backdrop.attributes('style')).toContain('https://cdn.test/room.png')
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

  it('falls back to the hazard icon for a non-fire containment incident', () => {
    const wrapper = mountScene({
      incident: incident({ type: 'radroach_infestation', family: 'infestation', objective: 'contain' }),
    })

    expect(wrapper.find('.hazard-flame').exists()).toBe(false)
    expect(wrapper.find('.hazard-icon').exists()).toBe(true)
  })

  it('stops the flame animation under prefers-reduced-motion', () => {
    expect(sceneSource).toMatch(
      /@media \(prefers-reduced-motion: reduce\) \{[\s\S]*?\.flame-outer,\s*\.flame-inner \{\s*animation: none;/
    )
  })
})
