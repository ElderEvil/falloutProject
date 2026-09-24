import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ExplorerSummaryCard from '@/modules/exploration/components/ExplorerSummaryCard.vue'

const baseProps = {
  dwellerName: 'Lucy MacLean',
  dwellerLevel: 12,
  health: 102,
  maxHealth: 125,
  progressPercentage: 40,
  timeRemaining: '4h 48m',
  explorationDuration: 8,
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
