import { describe, expect, it } from 'vitest'
import { mountWithSetup } from '../../helpers/mountWithSetup'
import PageHeaderMetric from '@/core/components/common/PageHeaderMetric.vue'

// Reka renders TooltipContent only when open and teleported; stub it inline so
// the tooltip text (the behavioral contract) is assertable without hover timers.
const contentStub = { template: '<div><slot /></div>' }

const card = '[data-slot="card"]'
const trigger = '[data-slot="tooltip-trigger"]'
const value = '.page-header-metric-value'

describe('PageHeaderMetric', () => {
  it('renders the value and label without a focus stop when no tooltip is passed', () => {
    const wrapper = mountWithSetup(PageHeaderMetric, {
      props: { label: 'Dwellers', value: 12, icon: 'mdi:account-group' },
    })

    expect(wrapper.find(trigger).exists()).toBe(false)
    expect(wrapper.find(card).attributes('tabindex')).toBeUndefined()
    expect(wrapper.text()).toContain('12')
    expect(wrapper.text()).toContain('Dwellers')
  })

  it('makes the metric keyboard reachable and surfaces the tooltip text', () => {
    const wrapper = mountWithSetup(PageHeaderMetric, {
      props: {
        label: 'Dwellers',
        value: 12,
        icon: 'mdi:account-group',
        tooltip: 'Total dwellers in vault: 12/20\nCapacity: 20 dwellers',
      },
      global: { stubs: { TooltipContent: contentStub } },
    })

    // tabindex is the accessibility contract; cursor-help is only its styling.
    expect(wrapper.find(trigger).attributes('tabindex')).toBe('0')
    expect(wrapper.text()).toContain('Total dwellers in vault: 12/20')
    expect(wrapper.text()).toContain('Capacity: 20 dwellers')
  })

  // Deliberately asserts the *passthrough*, not a design token: the token below is
  // supplied by the caller, so renaming a class the component itself owns cannot
  // break this test. That is the distinction the class-assertion ratchet wants.
  it('forwards a caller-supplied valueClass to the value element', () => {
    const wrapper = mountWithSetup(PageHeaderMetric, {
      props: {
        label: 'Happiness',
        value: 20,
        icon: 'mdi:emoticon-happy',
        valueClass: 'text-caller-supplied-warning',
      },
    })

    expect(wrapper.find(value).attributes('class')).toContain('text-caller-supplied-warning')
  })

  it('keeps the default value styling when no valueClass is supplied', () => {
    const wrapper = mountWithSetup(PageHeaderMetric, {
      props: { label: 'Happiness', value: 80, icon: 'mdi:emoticon-happy' },
    })

    expect(wrapper.find(value).attributes('class')).not.toContain('text-caller-supplied-warning')
  })
})
