import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { flushPromises } from '@vue/test-utils'
import { mountWithSetup } from '../../helpers/mountWithSetup'
import DwellerResponseTeamStatus from '@/modules/dwellers/components/DwellerResponseTeamStatus.vue'
import {
  fetchResponseRoster,
  updateResponseTeamPlace,
} from '@/modules/rooms/services/responseStationService'
import { useResponseStationStore } from '@/modules/rooms/stores/responseStation'
import type { ContaminationTeamRead } from '@/modules/contamination-team'

vi.mock('@/modules/rooms/services/responseStationService', () => ({
  fetchResponseRoster: vi.fn(),
  updateResponseTeamPlace: vi.fn(),
}))

vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => ({ token: 'test-token', sessionGeneration: 0 }),
}))

const mockToast = { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() }

vi.mock('@/core/composables/useToast', () => ({ useToast: () => mockToast }))

const roster = (overrides: Partial<ContaminationTeamRead> = {}): ContaminationTeamRead => ({
  vault_id: 'vault-1',
  teams: [
    { team: 'fire', active: [], reserve: [] },
    { team: 'radiation', active: [], reserve: [] },
  ],
  ...overrides,
})

function mountChip(dwellerId: string, data: ContaminationTeamRead) {
  vi.mocked(fetchResponseRoster).mockResolvedValue(data)
  return mountWithSetup(DwellerResponseTeamStatus, {
    props: { dwellerId, vaultId: 'vault-1' },
  })
}

describe('DwellerResponseTeamStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders an Active chip for a fire team member', async () => {
    const wrapper = mountChip(
      'd1',
      roster({
        teams: [
          {
            team: 'fire',
            active: [{ dweller_id: 'd1', status: 'fighting', name: 'John Doe', level: 12 }],
            reserve: [],
          },
          { team: 'radiation', active: [], reserve: [] },
        ],
      })
    )
    await flushPromises()

    expect(fetchResponseRoster).toHaveBeenCalledTimes(1)
    expect(fetchResponseRoster).toHaveBeenCalledWith('vault-1')
    expect(wrapper.text()).toContain('Fire Team')
    expect(wrapper.text()).not.toContain('Radiation Team')
  })

  it('renders a Reserve chip for a radiation bench member', async () => {
    const wrapper = mountChip(
      'd1',
      roster({
        teams: [
          { team: 'fire', active: [], reserve: [] },
          {
            team: 'radiation',
            active: [],
            reserve: [{ dweller_id: 'd1', status: 'idle', name: 'John Doe', level: 12 }],
          },
        ],
      })
    )
    await flushPromises()

    expect(wrapper.text()).toContain('Radiation Team · Reserve')
    expect(wrapper.text()).not.toContain('Fire Team')
  })

  it('renders both chips in order when the dweller is on both teams', async () => {
    const wrapper = mountChip(
      'd1',
      roster({
        teams: [
          {
            team: 'fire',
            active: [{ dweller_id: 'd1', status: 'fighting', name: 'John Doe', level: 12 }],
            reserve: [],
          },
          {
            team: 'radiation',
            active: [],
            reserve: [{ dweller_id: 'd1', status: 'idle', name: 'John Doe', level: 12 }],
          },
        ],
      })
    )
    await flushPromises()

    const chips = wrapper.findAll('.state-chip')
    expect(chips[0].text()).toContain('Fire Team')
    expect(chips[1].text()).toContain('Radiation Team · Reserve')
  })

  it('renders nothing for a non-member', async () => {
    const wrapper = mountChip('d1', roster())
    await flushPromises()

    expect(wrapper.findAll('.state-chip')).toHaveLength(0)
  })

  it('updates the chips when a placement changes through the shared store', async () => {
    const wrapper = mountChip('d1', roster())
    await flushPromises()
    expect(wrapper.findAll('.state-chip')).toHaveLength(0)
    vi.mocked(updateResponseTeamPlace).mockResolvedValueOnce(
      roster({
        teams: [
          {
            team: 'fire',
            active: [{ dweller_id: 'd1', status: 'active', name: 'Ash', level: 9 }],
            reserve: [],
          },
        ],
      })
    )
    await useResponseStationStore().setPlace('vault-1', 'fire', 'd1', true)
    await flushPromises()
    expect(wrapper.text()).toContain('Fire Team')
    await wrapper.setProps({ vaultId: 'vault-2' })
    await flushPromises()
    expect(wrapper.findAll('.state-chip')).toHaveLength(0)
  })
})
