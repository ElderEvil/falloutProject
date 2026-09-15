import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { h, nextTick } from 'vue'
import UTooltip from '@/core/components/ui/UTooltip.vue'

describe('UTooltip', () => {
  afterEach(() => {
    vi.useRealTimers()
    document.querySelectorAll('[role="tooltip"]').forEach((element) => element.remove())
  })

  it('renders trigger slot content', () => {
    const wrapper = mount(UTooltip, {
      props: { text: 'Test tooltip' },
      slots: {
        default: '<button>Hover me</button>',
      },
    })

    expect(wrapper.find('button').text()).toBe('Hover me')
  })

  it('has correct default props', () => {
    const wrapper = mount(UTooltip, {
      props: { text: 'Test tooltip' },
    })

    expect(wrapper.props('position')).toBe('top')
    expect(wrapper.props('delay')).toBe(200)
  })

  it('accepts custom position prop', () => {
    const wrapper = mount(UTooltip, {
      props: { text: 'Test tooltip', position: 'bottom' },
    })

    expect(wrapper.props('position')).toBe('bottom')
  })

  it('accepts custom delay prop', () => {
    const wrapper = mount(UTooltip, {
      props: { text: 'Test tooltip', delay: 500 },
    })

    expect(wrapper.props('delay')).toBe(500)
  })

  it('uses theme-aware CSS classes', () => {
    const wrapper = mount(UTooltip, {
      props: { text: 'Test tooltip' },
    })

    const html = wrapper.html()
    // Ensure no hardcoded green colors
    expect(html).not.toContain('rgba(0, 255, 0')
    expect(html).not.toContain('#00ff00')
  })

  it('measures the root element when the trigger is a component', async () => {
    vi.useFakeTimers()
    const TriggerStub = {
      name: 'TriggerStub',
      template: '<button class="inner">Go</button>',
    }
    const wrapper = mount(UTooltip, {
      attachTo: document.body,
      props: { text: 'Component trigger' },
      slots: { default: () => h(TriggerStub) },
    })

    await wrapper.get('button').trigger('focusin')
    vi.advanceTimersByTime(200)
    await nextTick()

    const tooltip = document.querySelector<HTMLElement>('[role="tooltip"]')
    expect(tooltip).not.toBeNull()
    expect(tooltip?.textContent).toContain('Component trigger')

    wrapper.unmount()
  })

  it('shows for keyboard focus and links the focused control to its description', async () => {
    vi.useFakeTimers()
    const wrapper = mount(UTooltip, {
      attachTo: document.body,
      props: { text: 'Build a new room' },
      slots: {
        default: ({ tooltipId }: { tooltipId: string }) =>
          h('button', { 'aria-describedby': tooltipId }, 'Build'),
      },
    })

    await wrapper.get('button').trigger('focusin')
    vi.advanceTimersByTime(200)
    await nextTick()

    const tooltip = document.querySelector<HTMLElement>('[role="tooltip"]')
    expect(tooltip).not.toBeNull()
    expect(wrapper.get('button').attributes('aria-describedby')).toBe(tooltip?.id)

    wrapper.unmount()
  })
})
