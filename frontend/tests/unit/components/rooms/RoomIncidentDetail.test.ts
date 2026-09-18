import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import RoomIncidentDetail from '@/modules/rooms/components/RoomIncidentDetail.vue'
import type { Incident, IncidentTeamMember } from '@/modules/combat/models/incident'

const assignResponders = vi.fn()
const fetchIncidentTeam = vi.fn()
const getIncidentTeam = vi.fn(() => [])
const warning = vi.fn()

vi.mock('@/modules/combat/stores/incident', () => ({
  useIncidentStore: () => ({ assignResponders, fetchIncidentTeam, getIncidentTeam }),
}))

vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => ({ token: 'test-token' }),
}))

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), warning, info: vi.fn() }),
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

const mountDetail = async (props: Record<string, unknown> = {}, flush = true) => {
  const wrapper = mount(RoomIncidentDetail, {
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
  // The team load resolves on mount; send controls stay disabled until then.
  if (flush) await flushPromises()
  return wrapper
}

describe('RoomIncidentDetail', () => {
  beforeEach(() => {
    assignResponders.mockReset()
    assignResponders.mockResolvedValue(undefined)
    fetchIncidentTeam.mockReset()
    fetchIncidentTeam.mockResolvedValue(undefined)
    getIncidentTeam.mockReset()
    getIncidentTeam.mockReturnValue([])
    warning.mockReset()
  })

  const teamMember = (dwellerId: string): IncidentTeamMember => ({
    id: `tm-${dwellerId}`,
    team_id: 'team-1',
    dweller_id: dwellerId,
    slot_number: 1,
    status: 'assigned',
    created_at: null,
    updated_at: null,
  })

  it('names the threat with its family, objective and progress', async () => {
    const text = (await mountDetail()).text()
    expect(text).toContain('RAIDER ATTACK')
    expect(text).toContain('INTRUSION')
    expect(text).toContain('DEFEAT')
    expect(text).toContain('30 / 100')
  })

  it('composes the scene and the battle log', async () => {
    const wrapper = await mountDetail()
    expect(wrapper.find('section[aria-label="Incident live status"]').exists()).toBe(true)
    expect(wrapper.find('[aria-label="Battle log"]').exists()).toBe(true)
  })

  it('offers the strongest adults as the best team and sends them together', async () => {
    const wrapper = await mountDetail({
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

  it('keeps a dweller already in the incident room out of the send list', async () => {
    const wrapper = await mountDetail({
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

  it('excludes dead, away and child dwellers from the send list', async () => {
    const wrapper = await mountDetail({
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
    const wrapper = await mountDetail({ dwellers: [dweller({ id: 'd1', first_name: 'Alice' })] })

    const buttons = wrapper.findAll('button')
    await buttons[buttons.length - 1].trigger('click')

    expect(assignResponders).toHaveBeenCalledWith('vault-1', 'incident-1', ['d1'], 'test-token')
  })

  it('states that room management is locked while the incident is live', async () => {
    expect((await mountDetail()).text()).toContain('Room management is locked')
  })

  it('blocks a second assignment while one is in flight', async () => {
    let release: (() => void) | undefined
    assignResponders.mockImplementationOnce(
      () =>
        new Promise<void>((resolve) => {
          release = resolve
        })
    )

    const wrapper = await mountDetail({
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

  it('fetches the designated team on mount', async () => {
    await mountDetail()

    expect(fetchIncidentTeam).toHaveBeenCalledWith('vault-1', 'incident-1', 'test-token')
  })

  it('renders the designated team roster with combat power', async () => {
    getIncidentTeam.mockReturnValue([teamMember('d1')])
    const wrapper = await mountDetail({
      dwellers: [dweller({ id: 'd1', first_name: 'Alice', combat_power: 10 })],
    })

    expect(wrapper.text()).toContain('On scene')
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('POW 10')
  })

  it('falls back to a short id for team members missing from the dweller list', async () => {
    getIncidentTeam.mockReturnValue([teamMember('dweller-unknown-1234')])
    const wrapper = await mountDetail({ dwellers: [] })

    expect(wrapper.text()).toContain('dweller-')
  })

  it('sends only the newly chosen dweller, not the current team', async () => {
    getIncidentTeam.mockReturnValue([teamMember('d1')])
    const wrapper = await mountDetail({
      dwellers: [
        dweller({ id: 'd1', first_name: 'Alice', room_id: 'room-1' }),
        dweller({ id: 'd2', first_name: 'Bob', room_id: 'room-2' }),
      ],
    })

    const buttons = wrapper.findAll('button')
    await buttons[buttons.length - 1].trigger('click')

    expect(assignResponders).toHaveBeenCalledWith('vault-1', 'incident-1', ['d2'], 'test-token')
  })

  it('sends only the best defenders, not the current team', async () => {
    getIncidentTeam.mockReturnValue([teamMember('d1')])
    const wrapper = await mountDetail({
      dwellers: [
        dweller({ id: 'd1', first_name: 'Alice', room_id: 'room-1', combat_power: 10 }),
        dweller({ id: 'd2', first_name: 'Bob', room_id: 'room-2', combat_power: 90 }),
        dweller({ id: 'd3', first_name: 'Cara', room_id: 'room-2', combat_power: 50 }),
      ],
    })

    await wrapper.find('button').trigger('click')

    expect(assignResponders).toHaveBeenCalledWith('vault-1', 'incident-1', ['d2', 'd3'], 'test-token')
  })

  it('does not re-send a dweller already on the team', async () => {
    getIncidentTeam.mockReturnValue([teamMember('d2')])
    const wrapper = await mountDetail({
      dwellers: [dweller({ id: 'd2', first_name: 'Bob', room_id: 'room-2' })],
    })

    const buttons = wrapper.findAll('button')
    await buttons[buttons.length - 1].trigger('click')

    expect(assignResponders).not.toHaveBeenCalled()
  })

  it('warns and sends only what fits when the roster would exceed 6', async () => {
    getIncidentTeam.mockReturnValue(['d1', 'd2', 'd3', 'd4', 'd5'].map((id) => teamMember(id)))
    const wrapper = await mountDetail({
      dwellers: [
        dweller({ id: 'd6', first_name: 'Fay', room_id: 'room-2', combat_power: 90 }),
        dweller({ id: 'd7', first_name: 'Gus', room_id: 'room-2', combat_power: 80 }),
        dweller({ id: 'd8', first_name: 'Hal', room_id: 'room-2', combat_power: 70 }),
      ],
    })

    await wrapper.find('button').trigger('click')

    expect(warning).toHaveBeenCalled()
    expect(assignResponders).toHaveBeenCalledWith('vault-1', 'incident-1', ['d6'], 'test-token')
  })

  it('does not send when the roster is already full', async () => {
    getIncidentTeam.mockReturnValue(['d1', 'd2', 'd3', 'd4', 'd5', 'd6'].map((id) => teamMember(id)))
    const wrapper = await mountDetail({
      dwellers: [dweller({ id: 'd7', first_name: 'Gus', room_id: 'room-2' })],
    })

    const buttons = wrapper.findAll('button')
    await buttons[buttons.length - 1].trigger('click')

    expect(warning).toHaveBeenCalled()
    expect(assignResponders).not.toHaveBeenCalled()
  })

  it('disables the send controls until the team has loaded', async () => {
    let resolveTeam: (() => void) | undefined
    fetchIncidentTeam.mockImplementationOnce(
      () =>
        new Promise<void>((resolve) => {
          resolveTeam = resolve
        })
    )

    const wrapper = await mountDetail(
      {
        dwellers: [
          dweller({ id: 'd1', first_name: 'Alice', combat_power: 90 }),
          dweller({ id: 'd2', first_name: 'Bob', combat_power: 50 }),
        ],
      },
      false
    )

    // Pending team load: every send control is inert and a stray click submits nothing.
    expect(wrapper.findAll('button').every((button) => button.attributes('disabled') !== undefined)).toBe(
      true
    )
    await wrapper.findAll('button')[0].trigger('click')
    expect(assignResponders).not.toHaveBeenCalled()

    resolveTeam?.()
    await flushPromises()

    // Load resolved: the controls are usable again.
    expect(wrapper.findAll('button').some((button) => button.attributes('disabled') === undefined)).toBe(
      true
    )
  })
})
