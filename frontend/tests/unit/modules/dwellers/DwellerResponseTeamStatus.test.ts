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

const member = (overrides: Record<string, unknown> = {}) => ({
  dweller_id: 'd1',
  status: 'fighting',
  name: 'John Doe',
  level: 12,
  ...overrides,
})

const team = (name: 'fire' | 'radiation', overrides: Record<string, unknown> = {}) => ({
  team: name,
  active: [],
  reserve: [],
  ...overrides,
})

const roster = (fire = team('fire'), radiation = team('radiation')): ContaminationTeamRead =>
  ({ vault_id: 'vault-1', teams: [fire, radiation] }) as ContaminationTeamRead

function mountChip(data: ContaminationTeamRead, dwellerId = 'd1') {
  vi.mocked(fetchResponseRoster).mockResolvedValue(data)
  return mountWithSetup(DwellerResponseTeamStatus, {
    props: { dwellerId, vaultId: 'vault-1' },
  })
}

describe('DwellerResponseTeamStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it.each([
    [
      'an active fire team member',
      roster(team('fire', { active: [member()] })),
      ['Fire Team'],
      ['Radiation Team'],
    ],
    [
      'a radiation bench member',
      roster(team('fire'), team('radiation', { reserve: [member({ status: 'idle' })] })),
      ['Radiation Team · Reserve'],
      ['Fire Team'],
    ],
  ] as const)('renders a chip for %s', async (_name, data, present, absent) => {
    const wrapper = mountChip(data)
    await flushPromises()

    expect(fetchResponseRoster).toHaveBeenCalledExactlyOnceWith('vault-1')
    for (const text of present) expect(wrapper.text()).toContain(text)
    for (const text of absent) expect(wrapper.text()).not.toContain(text)
  })

  it('renders both chips in order when the dweller is on both teams', async () => {
    const wrapper = mountChip(
      roster(
        team('fire', { active: [member()] }),
        team('radiation', { reserve: [member({ status: 'idle' })] })
      )
    )
    await flushPromises()

    const chips = wrapper.findAll('.state-chip')
    expect(chips[0].text()).toContain('Fire Team')
    expect(chips[1].text()).toContain('Radiation Team · Reserve')
  })

  it('renders nothing for a non-member', async () => {
    const wrapper = mountChip(roster())
    await flushPromises()

    expect(wrapper.findAll('.state-chip')).toHaveLength(0)
  })

  it('updates the chips when a placement changes through the shared store', async () => {
    const wrapper = mountChip(roster())
    await flushPromises()
    expect(wrapper.findAll('.state-chip')).toHaveLength(0)

    vi.mocked(updateResponseTeamPlace).mockResolvedValueOnce(
      roster(team('fire', { active: [member({ status: 'active', name: 'Ash', level: 9 })] }))
    )
    await useResponseStationStore().setPlace('vault-1', 'fire', 'd1', true)
    await flushPromises()
    expect(wrapper.text()).toContain('Fire Team')

    await wrapper.setProps({ vaultId: 'vault-2' })
    await flushPromises()
    expect(wrapper.findAll('.state-chip')).toHaveLength(0)
  })
})
