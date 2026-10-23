import { describe, expect, it, vi, beforeEach } from 'vite-plus/test'
import { mount, flushPromises } from '@vue/test-utils'
import { reactive } from 'vue'
import RoomIncidentDetail from '@/modules/rooms/components/RoomIncidentDetail.vue'
import DwellerListRow from '@/modules/dwellers/components/DwellerListRow.vue'
import type { Incident, IncidentTeamMember } from '@/modules/combat/models/incident'

const assignResponders = vi.fn()
const fetchIncidentTeam = vi.fn()
const getIncidentTeam = vi.fn<(incidentId: string) => IncidentTeamMember[]>(() => [])
const activeIncidents: Incident[] = []
const unloadedTeams = reactive(new Set<string>())
const hasLoadedIncidentTeam = (id: string) => !unloadedTeams.has(id)

vi.mock('@/modules/combat/stores/incident', () => ({
  useIncidentStore: () => ({
    assignResponders,
    fetchIncidentTeam,
    getIncidentTeam,
    activeIncidents,
    hasLoadedIncidentTeam,
  }),
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
  age_group: 'adult',
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
    activeIncidents.length = 0
    unloadedTeams.clear()
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

    expect(wrapper.text()).toContain('Send strongest 3')
    await wrapper.find('button').trigger('click')

    expect(assignResponders).toHaveBeenCalledWith(
      'vault-1',
      'incident-1',
      ['d2', 'd3', 'd1'],
      'test-token'
    )
  })

  it('ranks the entire list by unrounded power and then display name without changing the source list', async () => {
    const dwellers = [
      dweller({ id: 'd1', first_name: 'Alice', combat_power: 10.1 }),
      dweller({ id: 'd2', first_name: 'Zed', combat_power: 10.4 }),
      dweller({ id: 'd3', first_name: 'Bob', combat_power: 10.1 }),
      dweller({ id: 'd4', first_name: 'Aaron', last_name: null, combat_power: 10.1 }),
    ]
    const wrapper = await mountDetail({ dwellers })

    expect(wrapper.findAllComponents(DwellerListRow).map((row) => row.get('h3').text())).toEqual([
      'Zed Smith',
      'Aaron',
      'Alice Smith',
      'Bob Smith',
    ])
    expect(dwellers.map((candidate) => candidate.id)).toEqual(['d1', 'd2', 'd3', 'd4'])
    await wrapper.find('button').trigger('click')
    expect(assignResponders).toHaveBeenCalledWith(
      'vault-1',
      'incident-1',
      ['d2', 'd4', 'd1'],
      'test-token'
    )
  })

  it('backfills the best three after excluding an already rostered dweller with stale room data', async () => {
    getIncidentTeam.mockReturnValue([teamMember('d1')])
    const wrapper = await mountDetail({
      dwellers: [
        dweller({ id: 'd1', first_name: 'Assigned', combat_power: 100 }),
        dweller({ id: 'd2', first_name: 'Bob', combat_power: 90 }),
        dweller({ id: 'd3', first_name: 'Cara', combat_power: 50 }),
        dweller({ id: 'd4', first_name: 'Dan', combat_power: 10 }),
      ],
    })

    expect(wrapper.findAllComponents(DwellerListRow)).toHaveLength(3)
    await wrapper.find('button').trigger('click')
    expect(assignResponders).toHaveBeenCalledWith(
      'vault-1',
      'incident-1',
      ['d2', 'd3', 'd4'],
      'test-token'
    )
  })

  it('excludes responders committed to another live incident but allows completed members', async () => {
    activeIncidents.push(incident({ id: 'incident-2', vault_id: 'vault-1' }))
    getIncidentTeam.mockImplementation((id: string) =>
      id === 'incident-2'
        ? [
            teamMember('d1'),
            { ...teamMember('d2'), status: 'dispatched' },
            { ...teamMember('d3'), status: 'completed' },
          ]
        : []
    )
    const wrapper = await mountDetail({
      dwellers: [
        dweller({ id: 'd1', first_name: 'Assigned', combat_power: 100 }),
        dweller({ id: 'd2', first_name: 'Dispatched', combat_power: 90 }),
        dweller({ id: 'd3', first_name: 'Finished', combat_power: 50 }),
        dweller({ id: 'd4', first_name: 'Free', combat_power: 10 }),
      ],
    })

    expect(wrapper.findAllComponents(DwellerListRow).map((row) => row.get('h3').text())).toEqual([
      'Finished Smith',
      'Free Smith',
    ])
    await wrapper.find('button').trigger('click')
    expect(assignResponders).toHaveBeenCalledWith(
      'vault-1',
      'incident-1',
      ['d3', 'd4'],
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
    expect(text).toContain('Send strongest 1')
    expect(text).toContain('Bob')
  })

  it('excludes dead, away and child dwellers from the send list', async () => {
    const wrapper = await mountDetail({
      dwellers: [
        dweller({ id: 'd1', first_name: 'Away', status: 'exploring' }),
        dweller({ id: 'd2', first_name: 'Gone', status: 'dead' }),
        dweller({ id: 'd3', first_name: 'Child', age_group: 'child' }),
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
    expect(
      wrapper.findAll('button').every((button) => button.attributes('disabled') !== undefined)
    ).toBe(true)
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
      dwellers: [dweller({ room_id: 'room-1', id: 'd1', first_name: 'Alice', combat_power: 10 })],
    })

    expect(wrapper.text()).toContain('On scene')
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('POW 10')
  })

  it('badges dispatched responders in the on-scene roster', async () => {
    getIncidentTeam.mockReturnValue([{ ...teamMember('d1'), status: 'dispatched' }])
    const wrapper = await mountDetail({
      dwellers: [dweller({ room_id: 'room-1', id: 'd1', first_name: 'Alice', combat_power: 10 })],
    })

    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('DISPATCHED')
  })

  it('keeps a named placeholder for team members missing from the dweller list', async () => {
    getIncidentTeam.mockReturnValue([teamMember('dweller-unknown-1234')])
    const wrapper = await mountDetail({ dwellers: [] })

    expect(wrapper.text()).toContain('Responder 1')
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

    expect(assignResponders).toHaveBeenCalledWith(
      'vault-1',
      'incident-1',
      ['d2', 'd3'],
      'test-token'
    )
  })

  it('does not re-send a dweller already on the team', async () => {
    getIncidentTeam.mockReturnValue([teamMember('d2')])
    const wrapper = await mountDetail({
      dwellers: [dweller({ id: 'd2', first_name: 'Bob', room_id: 'room-2' })],
    })

    expect(wrapper.findAllComponents(DwellerListRow)).toHaveLength(0)
    expect(wrapper.text()).not.toContain('Send best')
    expect(assignResponders).not.toHaveBeenCalled()
  })

  it('offers only the best responders that fit in the remaining roster slots', async () => {
    getIncidentTeam.mockReturnValue(['d1', 'd2', 'd3', 'd4', 'd5'].map((id) => teamMember(id)))
    const wrapper = await mountDetail({
      dwellers: [
        dweller({ id: 'd6', first_name: 'Fay', room_id: 'room-2', combat_power: 90 }),
        dweller({ id: 'd7', first_name: 'Gus', room_id: 'room-2', combat_power: 80 }),
        dweller({ id: 'd8', first_name: 'Hal', room_id: 'room-2', combat_power: 70 }),
      ],
    })

    expect(wrapper.text()).toContain('Send strongest 1')
    await wrapper.find('button').trigger('click')

    expect(assignResponders).toHaveBeenCalledWith('vault-1', 'incident-1', ['d6'], 'test-token')
  })

  it('does not send when the roster is already full', async () => {
    getIncidentTeam.mockReturnValue(
      ['d1', 'd2', 'd3', 'd4', 'd5', 'd6'].map((id) => teamMember(id))
    )
    const wrapper = await mountDetail({
      dwellers: [dweller({ id: 'd7', first_name: 'Gus', room_id: 'room-2' })],
    })

    const buttons = wrapper.findAll('button')
    await buttons[buttons.length - 1].trigger('click')

    expect(wrapper.text()).not.toContain('Send best')
    expect(buttons.every((button) => button.attributes('disabled') !== undefined)).toBe(true)
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

    // Pending team load: availability is unknown, so there are no send controls.
    expect(wrapper.findAll('button')).toHaveLength(0)
    expect(wrapper.text()).toContain('Waiting for incident teams')
    expect(assignResponders).not.toHaveBeenCalled()

    resolveTeam?.()
    await flushPromises()

    // Load resolved: the controls are usable again.
    expect(
      wrapper.findAll('button').some((button) => button.attributes('disabled') === undefined)
    ).toBe(true)
  })

  it.each(['incident-1', 'incident-2'])(
    'waits for an unknown team (%s) and recovers after a successful poll',
    async (unknownTeamId) => {
      activeIncidents.push(incident({ id: 'incident-2', vault_id: 'vault-1' }))
      unloadedTeams.add(unknownTeamId)
      // The store resolves a failed fetch without inserting a team cache entry.
      const wrapper = await mountDetail({
        dwellers: [dweller()],
      })

      expect(wrapper.findAllComponents(DwellerListRow)).toHaveLength(0)
      expect(wrapper.findAll('button')).toHaveLength(0)
      expect(wrapper.text()).toContain('Waiting for incident teams')
      expect(wrapper.text()).not.toContain('All available adults')
      expect(assignResponders).not.toHaveBeenCalled()

      // A confirmed empty team is usable; the reactive store cache enables sending.
      unloadedTeams.delete(unknownTeamId)
      await flushPromises()

      expect(wrapper.findAllComponents(DwellerListRow)).toHaveLength(1)
      expect(wrapper.text()).not.toContain('Waiting for incident teams')
      await wrapper.get('button').trigger('click')
      expect(assignResponders).toHaveBeenCalledWith('vault-1', 'incident-1', ['d1'], 'test-token')
    }
  )

  it('does not wait for an unknown team in another vault', async () => {
    activeIncidents.push(incident({ id: 'incident-2', vault_id: 'vault-2' }))
    unloadedTeams.add('incident-2')
    const wrapper = await mountDetail({ dwellers: [dweller()] })

    await wrapper.get('button').trigger('click')
    expect(assignResponders).toHaveBeenCalledWith('vault-1', 'incident-1', ['d1'], 'test-token')
  })

  it('shows the level of on-scene team members', async () => {
    getIncidentTeam.mockReturnValue([teamMember('d1')])
    const wrapper = await mountDetail({
      dwellers: [dweller({ room_id: 'room-1', id: 'd1', first_name: 'Alice', level: 7 })],
    })

    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('· Lv 7')
  })

  it('shows the level of available responders', async () => {
    const wrapper = await mountDetail({
      dwellers: [dweller({ id: 'd1', first_name: 'Alice', level: 9 })],
    })

    expect(wrapper.text()).toContain('· Lv 9')
  })

  it('hints that the first round is pending while the team waits on scene', async () => {
    getIncidentTeam.mockReturnValue([teamMember('d1')])
    const wrapper = await mountDetail({
      dwellers: [dweller({ room_id: 'room-1', id: 'd1', first_name: 'Alice' })],
      incident: incident({ events: [] }),
    })

    expect(wrapper.text()).toContain('Awaiting next round…')
  })

  it('hides the pending-round hint once a round has been fought', async () => {
    getIncidentTeam.mockReturnValue([teamMember('d1')])
    const wrapper = await mountDetail({
      dwellers: [dweller({ room_id: 'room-1', id: 'd1', first_name: 'Alice' })],
      incident: incident({
        events: [{ id: 'e1', kind: 'round', message: 'Trade fire.', data: null }],
      }),
    })

    expect(wrapper.text()).not.toContain('Awaiting next round')
  })

  it('treats a containment event as a fought round', async () => {
    getIncidentTeam.mockReturnValue([teamMember('d1')])
    const wrapper = await mountDetail({
      dwellers: [dweller({ id: 'd1', first_name: 'Alice' })],
      incident: incident({
        events: [{ id: 'e1', kind: 'containment', message: 'Foam spreads.', data: null }],
      }),
    })

    expect(wrapper.text()).not.toContain('Awaiting next round')
  })

  it('hides the pending-round hint when no team is on scene', async () => {
    const wrapper = await mountDetail({ dwellers: [] })

    expect(wrapper.text()).not.toContain('Awaiting next round')
  })
  it('shows occupants alongside helpers even when the helper team is empty', async () => {
    const wrapper = await mountDetail({ dwellers: [dweller({ room_id: 'room-1' })] })
    expect(wrapper.text()).toContain('RESIDENT')
    expect(wrapper.get('[aria-label="Incident live status"]').text()).toContain('Alice')
    expect(wrapper.findAllComponents(DwellerListRow)).toHaveLength(0)
  })

  it('shows working/idle status and posting, then sends nearby inhabitants instead of distant high power', async () => {
    const rooms = [
      {
        id: 'room-1',
        name: 'Incident room',
        coordinate_x: 0,
        coordinate_y: 1,
        size: 3,
        size_min: 3,
      },
      { id: 'near', name: 'Diner', coordinate_x: 3, coordinate_y: 1, size: 3, size_min: 3 },
      {
        id: 'middle',
        name: 'Water Treatment',
        coordinate_x: 6,
        coordinate_y: 1,
        size: 3,
        size_min: 3,
      },
      {
        id: 'far',
        name: 'Power Generator',
        coordinate_x: 24,
        coordinate_y: 4,
        size: 3,
        size_min: 3,
      },
    ]
    const wrapper = await mountDetail({
      rooms,
      dwellers: [
        dweller({
          id: 'far',
          first_name: 'Strong',
          room_id: 'far',
          status: 'working',
          combat_power: 100,
        }),
        dweller({
          id: 'near-worker',
          first_name: 'Worker',
          room_id: 'near',
          status: 'working',
          combat_power: 50,
        }),
        dweller({
          id: 'near-idle',
          first_name: 'Idle',
          room_id: 'near',
          status: 'idle',
          combat_power: 10,
        }),
        dweller({
          id: 'middle',
          first_name: 'Middle',
          room_id: 'middle',
          status: 'working',
          combat_power: 30,
        }),
      ],
    })
    const rows = wrapper.findAllComponents(DwellerListRow)
    expect(rows.map((row) => row.get('h3').text())).toEqual([
      'Idle Smith',
      'Worker Smith',
      'Middle Smith',
      'Strong Smith',
    ])
    expect(rows[1].text()).toContain('Working')
    expect(rows[1].text()).toContain('Diner')
    expect(rows[1].text()).toContain('Same floor')
    expect(rows[1].text()).toContain('90/100')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'Send nearby 3')!
      .trigger('click')
    expect(assignResponders).toHaveBeenCalledWith(
      'vault-1',
      'incident-1',
      ['near-idle', 'near-worker', 'middle'],
      'test-token'
    )
  })

  it('keeps other-room residents and Arena fighters out of the helper list', async () => {
    activeIncidents.push(incident({ id: 'other', vault_id: 'vault-1', room_id: 'room-2' }))
    const wrapper = await mountDetail({
      dwellers: [
        dweller({ id: 'resident', room_id: 'room-2', status: 'working' }),
        dweller({ id: 'arena', room_id: 'arena', status: 'fighting' }),
        dweller({ id: 'free', first_name: 'Free', room_id: null, status: 'idle' }),
      ],
    })
    expect(wrapper.findAllComponents(DwellerListRow).map((row) => row.get('h3').text())).toEqual([
      'Free Smith',
    ])
    expect(wrapper.text()).toContain('Unassigned')
  })

  it('shows the saved return destination for a helper', async () => {
    getIncidentTeam.mockReturnValue([{ ...teamMember('d1'), origin_room_id: 'origin' }])
    const wrapper = await mountDetail({
      rooms: [{ id: 'origin', name: 'Original Diner' }],
      dwellers: [dweller({ room_id: 'room-1' })],
    })
    expect(wrapper.text()).toContain('Returns to Original Diner')
  })
})
