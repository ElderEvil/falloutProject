import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import UProgressBar from '@/core/components/ui/UProgressBar.vue'

describe('UProgressBar', () => {
  it('uses the semantic sunken surface for its track', () => {
    const wrapper = mount(UProgressBar, { props: { modelValue: 50 } })

    expect(wrapper.classes()).toContain('u-progress-bar--sunken')
  })

  it('renders no radiation segment by default', () => {
    const wrapper = mount(UProgressBar, { props: { modelValue: 50 } })

    expect(wrapper.find('.u-progress-bar__radiation').exists()).toBe(false)
  })

  it('renders the radiation segment stacked after the fill', () => {
    const wrapper = mount(UProgressBar, { props: { modelValue: 60, radiation: 25 } })
    const segment = wrapper.find('.u-progress-bar__radiation')

    expect(segment.exists()).toBe(true)
    expect(segment.attributes('style')).toContain('width: 25%')
  })

  it('clamps combined health and radiation to the track', () => {
    const wrapper = mount(UProgressBar, { props: { modelValue: 90, radiation: 50 } })
    const fills = wrapper.findAll('.u-progress-bar__fill, .u-progress-bar__radiation')

    expect(wrapper.find('.u-progress-bar__fill').attributes('style')).toContain('width: 40%')
    expect(wrapper.find('.u-progress-bar__radiation').attributes('style')).toContain('width: 50%')
    expect(fills).toHaveLength(2)
  })

  it('does not let radiation extend beyond the health value', () => {
    const wrapper = mount(UProgressBar, { props: { modelValue: 40, radiation: 75 } })

    expect(wrapper.find('.u-progress-bar__fill').attributes('style')).toContain('width: 0%')
    expect(wrapper.find('.u-progress-bar__radiation').attributes('style')).toContain('width: 40%')
  })
})
