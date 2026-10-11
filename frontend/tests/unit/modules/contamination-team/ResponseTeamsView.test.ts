import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { reactive } from 'vue'
import { enableAutoUnmount, flushPromises } from '@vue/test-utils'
import { mountWithSetup } from '../../helpers/mountWithSetup'
import ResponseTeamsView from '@/modules/contamination-team/views/ResponseTeamsView.vue'
import { contaminationTeamApi } from '@/modules/contamination-team/api/roster'
import type { ContaminationTeamRead } from '@/modules/contamination-team/models/contaminationTeam'

const routeState = reactive({ params: { id: 'vault-1' }, path: '/vault/vault-1/response-teams' })
const mockPush = vi.fn()
enableAutoUnmount(afterEach)

vi.mock('@/modules/contamination-team/api/roster', () => ({
  contaminationTeamApi: { getRoster: vi.fn(), setPlace: vi.fn() },
}))

vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => ({ token: 'test-token' }),
}))

const mockToast = { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() }

vi.mock('@/core/composables/useToast', () => ({ useToast: () => mockToast }))

vi.mock('vue-router', async () => {
  const actual = await vi.importActual('vue-router')
  return {
    ...actual,
    useRoute: () => routeState,
    useRouter: () => ({ push: mockPush }),
  }
})

vi.mock('@/modules/contamination-team/components/ResponseTeamsPanel.vue', () => ({
  default: {
    name: 'ResponseTeamsPanel',
    props: ['roster', 'loading', 'error', 'busyDwellerIds'],
    emits: ['set-place'],
    template: `
      <div class="panel-stub">
        <button class="activate" @click="$emit('set-place', 'fire', 'd1', true)">Activate</button>
        <button class="bench" @click="$emit('set-place', 'fire', 'd1', false)">Bench</button>
      </div>
    `,
  },
}))

const roster = (overrides: Partial<ContaminationTeamRead> = {}): ContaminationTeamRead => ({
  vault_id: 'vault-1',
  teams: [
    {
      team: 'fire',
      active: [{ dweller_id: 'd1', status: 'fighting', name: 'John Doe', level: 12 }],
      reserve: [{ dweller_id: 'd2', status: 'idle', name: 'Jane', level: 8 }],
    },
    { team: 'radiation', active: [], reserve: [] },
  ],
  ...overrides,
})

const metricValues = (wrapper: ReturnType<typeof mountWithSetup>) =>
  wrapper.findAll('.page-header-metric-value').map((node) => node.text())

describe('ResponseTeamsView', () => {
  it('refreshes the roster on vault change and rejects a late previous-vault response', async () => {
    let finish!: (value: ContaminationTeamRead) => void
    vi.mocked(contaminationTeamApi.getRoster)
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finish = resolve
          })
      )
      .mockResolvedValueOnce(roster({ vault_id: 'vault-2', teams: [] }))
    const wrapper = mountWithSetup(ResponseTeamsView)
    routeState.params.id = 'vault-2'
    await flushPromises()
    expect(contaminationTeamApi.getRoster).toHaveBeenLastCalledWith('vault-2', 'test-token')
    finish(roster())
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ResponseTeamsPanel' }).props('roster').vault_id).toBe(
      'vault-2'
    )
  })

  it('serializes roster mutations to prevent stale full-roster responses', async () => {
    let finish!: (value: ContaminationTeamRead) => void
    vi.mocked(contaminationTeamApi.setPlace).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve
        })
    )
    const wrapper = mountWithSetup(ResponseTeamsView)
    await flushPromises()
    await wrapper.find('.activate').trigger('click')
    await wrapper.find('.bench').trigger('click')
    expect(contaminationTeamApi.setPlace).toHaveBeenCalledTimes(1)
    finish(roster())
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ResponseTeamsPanel' }).props('busyDwellerIds')).toEqual(
      []
    )
  })

  beforeEach(() => {
    vi.clearAllMocks()
    routeState.params.id = 'vault-1'
    vi.mocked(contaminationTeamApi.getRoster).mockResolvedValue(roster())
  })

  it('fetches the roster and renders Active/Reserve totals in the header', async () => {
    const wrapper = mountWithSetup(ResponseTeamsView)
    await flushPromises()

    expect(contaminationTeamApi.getRoster).toHaveBeenCalledWith('vault-1', 'test-token')
    expect(metricValues(wrapper)).toEqual(['1', '1'])
    expect(wrapper.text()).toContain('Active')
    expect(wrapper.text()).toContain('Reserve')
  })

  it('hides the metrics while the roster is loading', () => {
    const wrapper = mountWithSetup(ResponseTeamsView)

    expect(wrapper.findAll('.page-header-metric-value')).toHaveLength(0)
  })

  it('handles set-place by calling setPlace and re-rendering from the response', async () => {
    vi.mocked(contaminationTeamApi.setPlace).mockResolvedValue(
      roster({
        teams: [
          {
            team: 'fire',
            active: [
              { dweller_id: 'd1', status: 'fighting', name: 'John Doe', level: 12 },
              { dweller_id: 'd2', status: 'fighting', name: 'Jane', level: 8 },
            ],
            reserve: [],
          },
          { team: 'radiation', active: [], reserve: [] },
        ],
      })
    )
    const wrapper = mountWithSetup(ResponseTeamsView)
    await flushPromises()

    await wrapper.find('.activate').trigger('click')
    await flushPromises()

    expect(contaminationTeamApi.setPlace).toHaveBeenCalledWith(
      'vault-1',
      'fire',
      'd1',
      true,
      'test-token'
    )
    expect(metricValues(wrapper)).toEqual(['2', '0'])
  })
})
