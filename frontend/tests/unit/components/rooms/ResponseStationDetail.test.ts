import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { mountWithSetup } from '../../helpers/mountWithSetup'
import ResponseStationDetail from '@/modules/rooms/components/ResponseStationDetail.vue'
import { useRoomStore } from '@/modules/rooms/stores/room'
import {
  fetchResponseRoster,
  updateResponseTeamPlace,
} from '@/modules/rooms/services/responseStationService'
import type { Room } from '@/modules/rooms/models/room'
import type { ContaminationTeamRead } from '@/modules/contamination-team/models/contaminationTeam'

vi.mock('@/modules/rooms/services/responseStationService', () => ({
  fetchResponseRoster: vi.fn(),
  updateResponseTeamPlace: vi.fn(),
  expandResponseStation: vi.fn(),
}))

vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => ({ token: 'test-token' }),
}))

const mockToast = {
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
  info: vi.fn(),
  show: vi.fn(),
  remove: vi.fn(),
  toasts: { value: [] },
}

vi.mock('@/core/composables/useToast', () => ({ useToast: () => mockToast }))

const station = (overrides: Partial<Room> = {}): Room =>
  ({
    id: 'station-1',
    name: 'Response Station',
    category: 'response',
    ability: 'endurance',
    tier: 1,
    capacity: null,
    size: 3,
    size_min: 3,
    size_max: 9,
    base_cost: 600,
    coordinate_x: 0,
    coordinate_y: 0,
    image_url: null,
    ...overrides,
  }) as Room

const roster = (): ContaminationTeamRead => ({
  vault_id: 'vault-1',
  teams: [
    {
      team: 'fire',
      active: [
        {
          dweller_id: 'd1',
          status: 'active',
          name: 'Ash',
          level: 9,
          service_count: 3,
          outfit_name: 'Firefighter suit',
          has_matching_gear: true,
          hazard_resist: 0.7,
        },
      ],
      reserve: [
        {
          dweller_id: 'd2',
          status: 'reserve',
          name: 'Ember',
          level: 4,
          service_count: 0,
          outfit_name: 'Vault suit',
          has_matching_gear: false,
          hazard_resist: 0.15,
        },
      ],
    },
    { team: 'radiation', active: [], reserve: [] },
  ],
})

const mountStation = (overrides: Partial<Room> = {}) =>
  mountWithSetup(ResponseStationDetail, {
    props: {
      room: station(overrides),
      vaultId: 'vault-1',
      assignedDwellers: [
        { id: 'd1', first_name: 'Ash', last_name: 'Fall', apprentice_stat: null },
      ] as never,
      dwellerCapacity: 2,
    },
  })

const findButton = (wrapper: ReturnType<typeof mountWithSetup>, label: string) =>
  wrapper.findAll('button').find((button) => button.text().includes(label))!

describe('ResponseStationDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(fetchResponseRoster).mockResolvedValue(roster())
  })

  it('renders stationed capacity, footprint, crew totals and expansion terms', async () => {
    const wrapper = mountStation()
    await flushPromises()

    expect(fetchResponseRoster).toHaveBeenCalledWith('vault-1', 'test-token')
    expect(wrapper.text()).toContain('1 / 2 stationed')
    expect(wrapper.text()).toContain('3 / 9 cells')
    expect(wrapper.text()).toContain('1 / 6')
    expect(wrapper.text()).toContain('600 caps adds one segment')
    expect(wrapper.text()).toContain('earn a place by fighting three matching incidents')
    expect(findButton(wrapper, 'Expand Station').attributes('disabled')).toBeUndefined()
  })

  it('renders both rosters with service counts and matching-suit protection', async () => {
    const wrapper = mountStation()
    await flushPromises()

    expect(wrapper.text()).toContain('Fire Team')
    expect(wrapper.text()).toContain('Radiation Team')
    expect(wrapper.text()).toContain('1 / 3 active places')
    expect(wrapper.text()).toContain('Reserve · 1')
    expect(wrapper.text()).toContain('3 incidents served')
    expect(wrapper.text()).toContain('Matching suit · protection 70%')
    expect(wrapper.text()).toContain('0 incidents served')
    expect(wrapper.text()).toContain('No matching suit · protection 15%')
    expect(wrapper.text()).toContain(
      'No matching Firefighter suit equipped. Worn gear removes 15 percent of fire hazard damage.'
    )
  })

  it('sends roster moves through the service with the active token', async () => {
    vi.mocked(updateResponseTeamPlace).mockResolvedValue(roster())
    const wrapper = mountStation()
    await flushPromises()

    await findButton(wrapper, 'Activate').trigger('click')
    await flushPromises()

    expect(updateResponseTeamPlace).toHaveBeenCalledWith(
      'vault-1',
      'fire',
      'd2',
      true,
      'test-token'
    )
  })

  it('offers a retry that refetches the roster after a load failure', async () => {
    vi.mocked(fetchResponseRoster).mockRejectedValueOnce(new Error('Signal lost'))
    const wrapper = mountStation()
    await flushPromises()
    expect(wrapper.text()).toContain('Failed to load response teams')

    await findButton(wrapper, 'Retry').trigger('click')
    await flushPromises()

    expect(fetchResponseRoster).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('Fire Team')
  })

  it('expands the station through the room store and notifies the parent', async () => {
    const wrapper = mountStation()
    await flushPromises()
    const roomStore = useRoomStore()
    const expandSpy = vi
      .spyOn(roomStore, 'expandRoom')
      .mockResolvedValue(station({ size: 6 }) as Room)

    await findButton(wrapper, 'Expand Station').trigger('click')
    await flushPromises()

    expect(expandSpy).toHaveBeenCalledWith('station-1', 'test-token', 'vault-1')
    expect(wrapper.emitted('roomUpdated')).toHaveLength(1)
    expect(mockToast.success).toHaveBeenCalledWith(
      expect.stringContaining('Response Station expanded to 6 cells')
    )
  })

  it('disables expansion and explains the ceiling at maximum footprint', async () => {
    const wrapper = mountStation({ size: 9, size_max: 9 })
    await flushPromises()

    expect(findButton(wrapper, 'Expand Station').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Maximum footprint reached')
  })
})
