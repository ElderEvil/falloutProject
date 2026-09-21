import { describe, expect, it } from 'vitest'

import { mountWithSetup } from '../../helpers/mountWithSetup'
import UBadge from '@/core/components/ui/UBadge.vue'

describe('UBadge', () => {
  it('renders the slot content inside a span', () => {
    const wrapper = mountWithSetup(UBadge, { slots: { default: 'Active' } })

    expect(wrapper.element.tagName).toBe('SPAN')
    expect(wrapper.text()).toBe('Active')
  })

  it('renders a dot indicator only when dot is set', () => {
    const withDot = mountWithSetup(UBadge, { props: { dot: true }, slots: { default: 'Pending' } })
    expect(withDot.find('span span').exists()).toBe(true)

    const withoutDot = mountWithSetup(UBadge, { slots: { default: 'Pending' } })
    expect(withoutDot.find('span span').exists()).toBe(false)
  })

  it('renders the icon component when provided', () => {
    const icon = { template: '<span>★</span>' }
    const wrapper = mountWithSetup(UBadge, { props: { icon }, slots: { default: 'Starred' } })

    expect(wrapper.text()).toContain('★')
    expect(wrapper.text()).toContain('Starred')
  })

  it.each([
    'success',
    'warning',
    'danger',
    'info',
    'default',
    'primary',
    'secondary',
    'outline',
  ] as const)('renders content for the %s variant', (variant) => {
    const wrapper = mountWithSetup(UBadge, { props: { variant }, slots: { default: 'Tag' } })

    expect(wrapper.text()).toBe('Tag')
  })
})