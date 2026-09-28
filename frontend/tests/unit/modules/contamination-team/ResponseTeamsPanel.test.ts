import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mountWithSetup } from '../../helpers/mountWithSetup'
import ResponseTeamsPanel from '@/modules/contamination-team/components/ResponseTeamsPanel.vue'
import type { ContaminationTeamRead } from '@/modules/contamination-team/models/contaminationTeam'

const roster = (overrides: Partial<ContaminationTeamRead> = {}): ContaminationTeamRead => ({
  vault_id: 'vault-1',
  teams: [
    {
      team: 'fire',
      active: [{ dweller_id: 'd1', status: 'fighting', name: 'John Doe', level: 12 }],
      reserve: [{ dweller_id: 'd2', status: 'idle', name: 'Jane', level: 8 }],
    },
    {
      team: 'radiation',
      active: [{ dweller_id: 'missing', status: 'working', name: '', level: 1 }],
      reserve: [],
    },
  ],
  ...overrides,
})

function mountPanel(overrides: Partial<ContaminationTeamRead> = {}) {
  return mountWithSetup(ResponseTeamsPanel, {
    props: {
      roster: roster(overrides),
      loading: false,
      error: null,
    },
  })
}

const findButton = (wrapper: ReturnType<typeof mountWithSetup>, label: string) =>
  wrapper.findAll('button').find((b) => b.text().includes(label))!

describe('ResponseTeamsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders both team sections with member names', () => {
    const wrapper = mountPanel()

    expect(wrapper.text()).toContain('Fire Team')
    expect(wrapper.text()).toContain('Radiation Team')
    expect(wrapper.text()).toContain('John Doe')
    expect(wrapper.text()).toContain('Jane')
    expect(wrapper.text()).toContain('LVL 12')
  })

  it('shows a muted placeholder when a member has no name', () => {
    const wrapper = mountPanel()

    expect(wrapper.text()).toContain('Unknown dweller')
  })

  it('renders per-section empty states when a team has no members', () => {
    const wrapper = mountPanel()

    expect(wrapper.text()).toContain('No reserve members')
  })

  it('shows the empty state when the roster has no teams', () => {
    const wrapper = mountPanel({ teams: [] })

    expect(wrapper.text()).toContain('No response teams yet')
  })

  it('shows the loading state while loading', () => {
    const wrapper = mountWithSetup(ResponseTeamsPanel, {
      props: { roster: null, loading: true, error: null },
    })

    expect(wrapper.text()).toContain('Loading response teams...')
  })

  it('shows the error state when the fetch failed', () => {
    const wrapper = mountWithSetup(ResponseTeamsPanel, {
      props: { roster: null, loading: false, error: 'Signal lost' },
    })

    expect(wrapper.text()).toContain('Failed to load response teams')
    expect(wrapper.text()).toContain('Signal lost')
  })

  it('emits set-place with active=false when Bench is clicked', async () => {
    const wrapper = mountPanel()

    await findButton(wrapper, 'Bench').trigger('click')

    expect(wrapper.emitted('set-place')).toEqual([['fire', 'd1', false]])
  })

  it('emits set-place with active=true when Activate is clicked', async () => {
    const wrapper = mountPanel()

    await findButton(wrapper, 'Activate').trigger('click')

    expect(wrapper.emitted('set-place')).toEqual([['fire', 'd2', true]])
  })

  it('disables Activate when the active list is full', () => {
    const fullTeam = {
      team: 'fire' as const,
      active: [
        { dweller_id: 'a1', status: 'fighting', name: 'Alpha One', level: 5 },
        { dweller_id: 'a2', status: 'fighting', name: 'Alpha Two', level: 6 },
        { dweller_id: 'a3', status: 'fighting', name: 'Alpha Three', level: 7 },
      ],
      reserve: [{ dweller_id: 'd2', status: 'idle', name: 'Jane', level: 8 }],
    }
    const wrapper = mountPanel({
      teams: [
        fullTeam,
        { team: 'radiation', active: [], reserve: [] },
      ],
    })

    const activate = findButton(wrapper, 'Activate')
    expect((activate.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('disables buttons while the dweller is busy', () => {
    const wrapper = mountWithSetup(ResponseTeamsPanel, {
      props: {
        roster: roster(),
        loading: false,
        error: null,
        busyDwellerIds: ['d1'],
      },
    })

    const bench = findButton(wrapper, 'Bench')
    expect((bench.element as HTMLButtonElement).disabled).toBe(true)
  })
})