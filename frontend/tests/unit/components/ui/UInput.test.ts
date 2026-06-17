import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import UInput from '@/core/components/ui/UInput.vue'

describe('UInput (Accessibility)', () => {
  it('should associate label with input via for/id attributes', () => {
    const wrapper = mount(UInput, {
      props: { label: 'Username', modelValue: '' },
    })
    const label = wrapper.find('label')
    const input = wrapper.find('input')
    const forAttr = label.attributes('for')
    const idAttr = input.attributes('id')
    expect(forAttr).toBeTruthy()
    expect(idAttr).toBeTruthy()
    expect(forAttr).toBe(idAttr)
  })

  it('should have required indicator when prop is set', () => {
    const wrapper = mount(UInput, {
      props: { label: 'Username', modelValue: '', required: true },
    })
    expect(wrapper.text()).toContain('*')
  })

  it('should display error message when error prop is set', () => {
    const wrapper = mount(UInput, {
      props: { label: 'Username', modelValue: '', error: 'This field is required' },
    })
    expect(wrapper.text()).toContain('This field is required')
  })

  it('should have unique id per instance', () => {
    const wrapper1 = mount(UInput, {
      props: { label: 'Field 1', modelValue: '' },
    })
    const wrapper2 = mount(UInput, {
      props: { label: 'Field 2', modelValue: '' },
    })
    const id1 = wrapper1.find('input').attributes('id')
    const id2 = wrapper2.find('input').attributes('id')
    expect(id1).not.toBe(id2)
  })
})
