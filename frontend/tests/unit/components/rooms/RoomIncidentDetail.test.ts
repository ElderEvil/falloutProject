import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import RoomIncidentDetail from '@/modules/rooms/components/RoomIncidentDetail.vue'
import type { Incident } from '@/modules/combat/models/incident'

const assignResponders = vi.fn()

vi.mock('@/modules/combat/stores/incident', () => ({
  useIncidentStore: () => ({ assignResponders }),
}))

vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => ({ token: 'test-token' }),
}))

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
    response: { label: 'Send defenders' },
    events: [],
    ...overrides,
  }) as Incident

const dweller = (overrides: Record<string, unknown> = {}) => ({
  id: 'd1',
  first_name: 'Alice',
  last_name: 'Smith',
  level: 5,
  health: 90,
  max_health: 100,
  is_adult: true,
  room_id: 'room-2',
  status: 'idle',
  combat_power: 10,
  ...overrides,
})

const mountDetail = (props: Record<string, unknown> = {}) =>
  mount(RoomIncidentDetail, {
    props: {
      incident: incident(),
      vaultId: 'vault-1',
      dwellers: [],
      ...props,
    },
    global: {
      stubs: {
        UButton: {
          props: ['disabled', 'loading', 'variant', 'size'],
          template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
        },
      },
    },
  })

describe('RoomIncidentDetail', () => {
  beforeEach(() => {
    assignResponders.mockReset()
    assignResponders.mockResolvedValue(undefined)
  })

  it('names the threat with its family, objective and progress', () => {
    const text = mountDetail().text()
    expect(text).toContain('RAIDER ATTACK')
    expect(text).toContain('INTRUSION')
    expect(text).toContain('DEFEAT')
    expect(text).toContain('30 / 100')
  })

  it('composes the scene and the battle log', () => {
    const wrapper = mountDetail()
    expect(wrapper.find('section[aria-label="Incident live status"]').exists()).toBe(true)
    expect(wrapper.find('[aria-label="Battle log"]').exists()).toBe(true)
  })

  it('offers the strongest adults as the best team and sends them together', async () => {
    const wrapper = mountDetail({
      dwellers: [
        dweller({ id: 'd1', first_name: 'Alice', combat_power: 10 }),
        dweller({ id: 'd2', first_name: 'Bob', combat_power: 90 }),
        dweller({ id: 'd3', first_name: 'Cara', combat_power: 50 }),
        dweller({ id: 'd4', first_name: 'Dan', combat_power: 5 }),
      ],
    })

    expect(wrapper.text()).toContain('Send best 3')
    await wrapper.find('button').trigger('click')

    expect(assignResponders).toHaveBeenCalledWith(
      'vault-1',
      'incident-1',
      ['d2', 'd3', 'd1'],
      'test-token'
    )
  })

  it('keeps a dweller already in the incident room out of the send list', () => {
    const wrapper = mountDetail({
      dwellers: [
        dweller({ id: 'd1', first_name: 'Alice', room_id: 'room-1' }),
        dweller({ id: 'd2', first_name: 'Bob', room_id: 'room-2' }),
      ],
    })

    const text = wrapper.text()
    expect(text).toContain('Send defenders')
    expect(text).toContain('Send best 1')
    expect(text).toContain('Bob')
  })

  it('excludes dead, away and child dwellers from the send list', () => {
    const wrapper = mountDetail({
      dwellers: [
        dweller({ id: 'd1', first_name: 'Away', status: 'exploring' }),
        dweller({ id: 'd2', first_name: 'Gone', status: 'dead' }),
        dweller({ id: 'd3', first_name: 'Child', is_adult: false }),
        dweller({ id: 'd4', first_name: 'Hurt', health: 0 }),
      ],
    })

    expect(wrapper.text()).toContain('All available adults are already defending or away.')
  })

  it('sends a single dweller from the responder list', async () => {
    const wrapper = mountDetail({ dwellers: [dweller({ id: 'd1', first_name: 'Alice' })] })

    const buttons = wrapper.findAll('button')
    await buttons[buttons.length - 1].trigger('click')

    expect(assignResponders).toHaveBeenCalledWith('vault-1', 'incident-1', ['d1'], 'test-token')
  })

  it('states that room management is locked while the incident is live', () => {
    expect(mountDetail().text()).toContain('Room management is locked')
  })

  it('blocks a second assignment while one is in flight', async () => {
    let release: (() => void) | undefined
    assignResponders.mockImplementationOnce(
      () =>
        new Promise<void>((resolve) => {
          release = resolve
        })
    )

    const wrapper = mountDetail({
      dwellers: [
        dweller({ id: 'd1', first_name: 'Alice', combat_power: 90 }),
        dweller({ id: 'd2', first_name: 'Bob', combat_power: 50 }),
      ],
    })

    const buttons = wrapper.findAll('button')
    await buttons[0].trigger('click')
    await wrapper.vm.$nextTick()

    // Both controls must be inert until the first request settles.
    expect(wrapper.findAll('button').every((button) => button.attributes('disabled') !== undefined)).toBe(
      true
    )
    expect(assignResponders).toHaveBeenCalledTimes(1)

    release?.()
    await wrapper.vm.$nextTick()
  })
})
