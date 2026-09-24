import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import HealthRadiationBar from '@/core/components/common/HealthRadiationBar.vue'

describe('HealthRadiationBar', () => {
  it('exposes the aria-label as the accessible name of the meter', () => {
    const wrapper = mount(HealthRadiationBar, {
      props: { value: 80, radiation: 20, 'aria-label': 'Health' },
    })

    const meter = wrapper.find('[role="progressbar"]')
    expect(meter.attributes('aria-label')).toBe('Health')
    expect(meter.attributes('aria-valuenow')).toBe('80')
    expect(meter.attributes('aria-valuemin')).toBe('0')
    expect(meter.attributes('aria-valuemax')).toBe('100')
  })

  it('renders the healthy and radiation widths from the clamped value', () => {
    const wrapper = mount(HealthRadiationBar, {
      props: { value: 80, radiation: 20 },
    })

    expect(wrapper.find('.health-radiation-bar__fill').attributes('style')).toContain('width: 60%')
    expect(wrapper.find('.health-radiation-bar__radiation').attributes('style')).toContain(
      'width: 20%'
    )
  })

  it('omits the radiation segment at zero radiation and clamps out-of-range values', () => {
    const wrapper = mount(HealthRadiationBar, {
      props: { value: 150, radiation: 0 },
    })

    expect(wrapper.find('.health-radiation-bar__radiation').exists()).toBe(false)
    expect(wrapper.find('[role="progressbar"]').attributes('aria-valuenow')).toBe('100')
  })
})
