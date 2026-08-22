import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import TerminalMetric from '@/core/components/common/TerminalMetric.vue'

vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    props: ['icon'],
    template: '<span class="icon-mock" :data-icon="icon" />',
  },
}))

describe('TerminalMetric', () => {
  it('renders a labelled metric with the warm sunken surface', () => {
    const wrapper = mount(TerminalMetric, {
      props: { icon: 'mdi:compass', label: 'Expeditions', value: 3 },
    })

    expect(wrapper.classes()).toContain('terminal-metric')
    expect(wrapper.classes()).toContain('bg-surface-sunken')
    expect(wrapper.text()).toContain('Expeditions')
    expect(wrapper.text()).toContain('3')
    expect(wrapper.find('.icon-mock').attributes('data-icon')).toBe('mdi:compass')
  })

  it('uses compact spacing for dense summaries', () => {
    const wrapper = mount(TerminalMetric, {
      props: { label: 'Morale', value: '82%', compact: true },
    })

    expect(wrapper.classes()).toContain('px-2.5')
    expect(wrapper.find('.icon-mock').exists()).toBe(false)
  })
})
