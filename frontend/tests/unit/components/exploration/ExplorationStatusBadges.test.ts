import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ExplorationStatusBadges from '@/modules/exploration/components/ExplorationStatusBadges.vue'
import type { Exploration } from '@/modules/exploration/stores/exploration'
import type { Dweller } from '@/modules/dwellers/models/dweller'

vi.mock('@iconify/vue', () => ({
  Icon: { name: 'Icon', template: '<span class="icon-mock" />' },
}))

const exploration = {
  id: 'exploration-1',
  vault_id: 'vault-1',
  dweller_id: 'dweller-1',
  status: 'active',
  duration: 8,
  start_time: '2026-01-01T00:00:00Z',
  end_time: null,
  events: [],
  loot_collected: [],
  total_distance: 0,
  total_caps_found: 0,
  enemies_encountered: 0,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  dweller_strength: 1,
  dweller_perception: 1,
  dweller_endurance: 1,
  dweller_charisma: 1,
  dweller_intelligence: 1,
  dweller_agility: 1,
  dweller_luck: 1,
  stimpaks: 0,
  radaways: 0,
} as Exploration

const dweller = {
  first_name: 'Lucy',
  last_name: 'MacLean',
  health: 100,
  max_health: 100,
  radiation: 0,
} as Dweller

describe('ExplorationStatusBadges', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows EXPLORING for an active run that is not ready yet', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-01-01T01:00:00Z'))
    const wrapper = mount(ExplorationStatusBadges, { props: { exploration, dweller } })

    expect(wrapper.text()).toContain('EXPLORING')
    expect(wrapper.text()).not.toContain('RETURNING')
    expect(wrapper.text()).not.toContain('READY')
    expect(wrapper.text()).not.toContain('AT RISK')

    wrapper.unmount()
  })

  it('shows RETURNING when the run is heading home', () => {
    const wrapper = mount(ExplorationStatusBadges, {
      props: {
        exploration: {
          ...exploration,
          status: 'returning',
          return_started_at: '2026-01-01T00:00:00Z',
          return_completes_at: '2026-01-01T02:00:00Z',
        },
        dweller,
      },
    })

    expect(wrapper.text()).toContain('RETURNING')
    expect(wrapper.text()).not.toContain('EXPLORING')
    expect(wrapper.text()).not.toContain('READY')

    wrapper.unmount()
  })

  it('shows READY when the run is ready to complete', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-01-01T09:00:00Z'))
    const wrapper = mount(ExplorationStatusBadges, { props: { exploration, dweller } })

    expect(wrapper.text()).toContain('READY')
    expect(wrapper.text()).not.toContain('EXPLORING')
    expect(wrapper.text()).not.toContain('RETURNING')

    wrapper.unmount()
  })

  it('shows AT RISK for a dweller with low health', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-01-01T01:00:00Z'))
    const wrapper = mount(ExplorationStatusBadges, {
      props: {
        exploration,
        dweller: { ...dweller, health: 20, max_health: 100, radiation: 10 },
      },
    })

    expect(wrapper.text()).toContain('AT RISK')
    expect(wrapper.find('[aria-label="Dweller at risk"]').exists()).toBe(true)

    wrapper.unmount()
  })
})
