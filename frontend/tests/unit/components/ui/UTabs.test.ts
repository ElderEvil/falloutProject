import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import UTabs from '@/core/components/ui/UTabs.vue'

vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="tab-icon" :data-icon="icon" />',
    props: ['icon'],
  },
}))

describe('UTabs', () => {
  it('renders optional tab icons and changes the active tab', async () => {
    const wrapper = mount(UTabs, {
      props: {
        modelValue: 'daily',
        tabs: [
          { key: 'daily', label: 'Daily', icon: 'mdi:calendar-today' },
          { key: 'completed', label: 'Completed', icon: 'mdi:check-circle' },
        ],
      },
    })

    expect(wrapper.findAll('.utabs-button')).toHaveLength(2)
    expect(wrapper.findAll('.tab-icon')[0].attributes('data-icon')).toBe('mdi:calendar-today')
    expect(wrapper.find('.utabs-button.active').text()).toContain('Daily')

    await wrapper.findAll('.utabs-button')[1]!.trigger('click')

    expect(wrapper.emitted('update:modelValue')).toEqual([['completed']])
  })
})
