import { describe, expect, it, beforeEach, vi } from 'vite-plus/test'
import { createRouterMock } from '../../helpers/mocks'
import { createExploration } from '../../helpers/explorationFixtures'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ExplorerSummaryCard from '@/modules/exploration/components/ExplorerSummaryCard.vue'
import type { Exploration } from '@/modules/exploration/stores/exploration'

vi.mock('vue-router', () => createRouterMock({ params: { id: 'vault-1' } }))

const exploration = createExploration()

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
    global: { stubs: { DwellerPortrait: true, Icon: true } },
  })
}

describe('ExplorerSummaryCard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders the irradiated health display with effective and base maximums', () => {
    expect(mountCard({ radiation: 20 }).text()).toContain('102 / 105 (125)')
  })

  it('renders health / maxHealth without a parenthesised base value when not irradiated', () => {
    const wrapper = mountCard({ radiation: 0 })

    expect(wrapper.text()).toContain('102 / 125')
    expect(wrapper.text()).not.toContain('(125)')
  })

  it('keeps the Health radiation meter ARIA values', () => {
    const meter = mountCard({ radiation: 20 }).find('[role="progressbar"]')

    expect(meter.attributes('aria-valuenow')).toBe('81.6')
    expect(meter.attributes('aria-valuemin')).toBe('0')
    expect(meter.attributes('aria-valuemax')).toBe('100')
  })

  it('links the portrait and the name to the dweller page', () => {
    const wrapper = mountCard()

    expect(wrapper.findComponent('.dweller-portrait-frame').props('to')).toBe(
      '/vault/vault-1/dwellers/dweller-1'
    )
    expect(wrapper.findComponent('.dweller-name-link').props('to')).toBe(
      '/vault/vault-1/dwellers/dweller-1'
    )
  })
})
