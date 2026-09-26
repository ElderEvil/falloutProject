import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ExplorerSummaryCard from '@/modules/exploration/components/ExplorerSummaryCard.vue'
import type { Exploration } from '@/modules/exploration/stores/exploration'

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

const baseProps = {
  dwellerName: 'Lucy MacLean',
  dwellerLevel: 12,
  health: 102,
  maxHealth: 125,
  progressPercentage: 40,
  timeRemaining: '4h 48m',
  explorationDuration: 8,
  exploration,
}

function mountCard(props: Record<string, unknown> = {}) {
  return mount(ExplorerSummaryCard, {
    props: { ...baseProps, ...props },
    global: {
      stubs: {
        DwellerPortrait: true,
        Icon: true,
      },
    },
  })
}

describe('ExplorerSummaryCard', () => {
  it('renders the irradiated health display with effective and base maximums', () => {
    const wrapper = mountCard({ health: 102, maxHealth: 125, radiation: 20 })

    expect(wrapper.text()).toContain('102 / 105 (125)')

    wrapper.unmount()
  })

  it('renders health / maxHealth without a parenthesised base value when not irradiated', () => {
    const wrapper = mountCard({ health: 102, maxHealth: 125, radiation: 0 })

    expect(wrapper.text()).toContain('102 / 125')
    expect(wrapper.text()).not.toContain('(125)')

    wrapper.unmount()
  })

  it('keeps the Health radiation meter ARIA values', () => {
    const wrapper = mountCard({ health: 102, maxHealth: 125, radiation: 20 })

    const meter = wrapper.find('[role="progressbar"]')
    expect(meter.attributes('aria-valuenow')).toBe('81.6')
    expect(meter.attributes('aria-valuemin')).toBe('0')
    expect(meter.attributes('aria-valuemax')).toBe('100')

    wrapper.unmount()
  })
})
