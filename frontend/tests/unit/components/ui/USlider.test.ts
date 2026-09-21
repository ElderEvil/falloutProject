import { describe, expect, it } from 'vitest'

import { mountWithSetup } from '../../helpers/mountWithSetup'
import USlider from '@/core/components/ui/USlider.vue'

describe('USlider', () => {
  it('renders a range input with min, max, step and value', () => {
    const wrapper = mountWithSetup(USlider, {
      props: { modelValue: 40, min: 0, max: 100, step: 5 },
    })

    const input = wrapper.find('input[type="range"]')
    expect(input.exists()).toBe(true)
    expect(input.attributes('min')).toBe('0')
    expect(input.attributes('max')).toBe('100')
    expect(input.attributes('step')).toBe('5')
    expect(input.attributes('value')).toBe('40')
  })

  it('applies default min, max and step when omitted', () => {
    const wrapper = mountWithSetup(USlider, { props: { modelValue: 50 } })

    const input = wrapper.find('input[type="range"]')
    expect(input.attributes('min')).toBe('0')
    expect(input.attributes('max')).toBe('100')
    expect(input.attributes('step')).toBe('1')
  })

  it('accepts an aria-label prop but does not forward it to the input', () => {
    const wrapper = mountWithSetup(USlider, {
      props: { modelValue: 30, 'aria-label': 'Volume' },
    })

    // Pre-existing bug: Vue stores the prop under the camelized key
    // `ariaLabel` while the template reads `props['aria-label']`, so the
    // attribute never reaches the input. Locked as current behaviour.
    expect(wrapper.props('ariaLabel')).toBe('Volume')
    expect(wrapper.find('input[type="range"]').attributes('aria-label')).toBeUndefined()
  })

  it('emits a numeric update:modelValue on input', async () => {
    const wrapper = mountWithSetup(USlider, { props: { modelValue: 10 } })

    await wrapper.find('input[type="range"]').setValue('60')

    expect(wrapper.emitted('update:modelValue')).toEqual([[60]])
  })

  it('disables the input when disabled', () => {
    const wrapper = mountWithSetup(USlider, { props: { modelValue: 10, disabled: true } })

    expect(wrapper.find('input[type="range"]').attributes('disabled')).toBeDefined()
  })
})