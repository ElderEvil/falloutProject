import { describe, it, expect } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import DwellerStatusBadge from '@/modules/dwellers/components/stats/DwellerStatusBadge.vue'

type BadgeProps = InstanceType<typeof DwellerStatusBadge>['$props']

const mountBadge = (props: Partial<BadgeProps>) => mount(DwellerStatusBadge, { props })

describe('DwellerStatusBadge', () => {
  it.each([
    ['idle', 'Idle'],
    ['working', 'Working'],
    ['exploring', 'Exploring'],
    ['questing', 'Questing'],
    ['training', 'Training'],
    ['fighting', 'Fighting'],
    ['dead', 'Dead'],
  ] as const)('renders the %s status as %s', (status, label) => {
    const wrapper = mountBadge({ status, showLabel: true })

    expect(wrapper.get('.status-badge').text()).toBe(label)
  })

  it.each([true, false])('shows the label only when showLabel is %s', (showLabel) => {
    const wrapper = mountBadge({ status: 'working', showLabel })

    expect(wrapper.text().includes('Working')).toBe(showLabel)
  })

  it.each([
    ['small', 'h-5'],
    ['medium', 'h-6'],
    ['large', 'h-7'],
  ] as const)('applies the %s size', (size, height) => {
    const wrapper = mountBadge({ status: 'working', size })

    expect(wrapper.get('.status-badge').classes()).toContain(height)
  })

  it('defaults to a small, label-less badge', () => {
    const wrapper = mountBadge({ status: 'working' })

    expect(wrapper.text()).not.toContain('Working')
    const badge = wrapper.get('.status-badge')
    expect(badge.classes()).toContain('h-5')
  })

  it.each([
    ['exploring', 'exploring'],
    ['working', 'working'],
    ['dead', 'dead'],
    ['idle', 'idle'],
  ])('sets the glow color for %s through a CSS custom property', (status, token) => {
    const wrapper = mountBadge({ status: status as BadgeProps['status'] })

    const badge = wrapper.get('.status-badge')
    expect(badge.attributes('style')).toContain('--glow-color')
    expect(badge.attributes('style')).toContain(
      `rgb(from var(--color-status-${token}) r g b / 0.3)`
    )
    // The glow rides the custom property, never a dynamic hover class.
    expect(badge.classes().some((c) => c.startsWith('hover:'))).toBe(false)
  })
})
