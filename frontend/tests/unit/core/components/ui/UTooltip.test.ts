import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import UTooltip from '@/core/components/ui/UTooltip.vue'

describe('UTooltip', () => {
  it('renders trigger slot content', () => {
    const wrapper = mount(UTooltip, {
      props: { text: 'Test tooltip' },
      slots: {
        default: '<button>Hover me</button>'
      }
    })

    expect(wrapper.find('button').text()).toBe('Hover me')
  })

  it('has correct default props', () => {
    const wrapper = mount(UTooltip, {
      props: { text: 'Test tooltip' }
    })

    expect(wrapper.props('position')).toBe('top')
    expect(wrapper.props('delay')).toBe(200)
  })

  it('accepts custom position prop', () => {
    const wrapper = mount(UTooltip, {
      props: { text: 'Test tooltip', position: 'bottom' }
    })

    expect(wrapper.props('position')).toBe('bottom')
  })

  it('accepts custom delay prop', () => {
    const wrapper = mount(UTooltip, {
      props: { text: 'Test tooltip', delay: 500 }
    })

    expect(wrapper.props('delay')).toBe(500)
  })

  it('uses theme-aware CSS classes', () => {
    const wrapper = mount(UTooltip, {
      props: { text: 'Test tooltip' }
    })

    const html = wrapper.html()
    // Ensure no hardcoded green colors
    expect(html).not.toContain('rgba(0, 255, 0')
    expect(html).not.toContain('#00ff00')
  })
})
