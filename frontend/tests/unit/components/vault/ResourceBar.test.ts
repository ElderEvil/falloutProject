import { describe, expect, it } from 'vitest'
import { mountWithSetup } from '../../helpers/mountWithSetup'
import ResourceBar from '@/modules/vault/components/shell/ResourceBar.vue'

function mountBar(props: Record<string, unknown> = {}) {
  return mountWithSetup(ResourceBar, {
    props: { current: 60, max: 100, icon: 'mdi:lightning-bolt', ...props },
  })
}

describe('ResourceBar', () => {
  it('renders the meter with correct aria values and current/max text', () => {
    const wrapper = mountBar()

    const meter = wrapper.get('[role="meter"]')
    expect(meter.attributes('aria-valuenow')).toBe('60')
    expect(meter.attributes('aria-valuemax')).toBe('100')
    expect(meter.attributes('aria-valuemin')).toBe('0')
    expect(meter.attributes('aria-label')).toContain('60')
    expect(wrapper.text()).toContain('60/100')
  })

  it('displays the label when provided', () => {
    const wrapper = mountBar({ label: 'Power' })

    expect(wrapper.text()).toContain('Power')
  })

  it('exposes the tooltip trigger on the meter for keyboard users', () => {
    const wrapper = mountBar()

    const meter = wrapper.get('[role="meter"]')
    expect(meter.attributes('tabindex')).toBe('0')
  })
})
