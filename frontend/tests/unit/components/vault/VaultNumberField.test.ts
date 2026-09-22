import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import VaultNumberField from '@/modules/vault/components/VaultNumberField.vue'

describe('VaultNumberField', () => {
  it('renders a labelled number input', () => {
    const wrapper = mount(VaultNumberField, { props: { modelValue: '' } })

    expect(wrapper.find('label').text()).toContain('Vault Number')
    expect(wrapper.find('input').attributes('type')).toBe('number')
    expect(wrapper.find('input').attributes('placeholder')).toBe('Vault Number (1-999)')
  })

  it('shows a validation error for out-of-range numbers', async () => {
    const wrapper = mount(VaultNumberField, { props: { modelValue: '' } })

    await wrapper.find('input').setValue('1000')

    expect(wrapper.text()).toContain('Invalid vault number')
  })

  it('exposes isValid() reflecting the schema', async () => {
    const wrapper = mount(VaultNumberField, { props: { modelValue: '' } })
    const vm = wrapper.vm as unknown as { isValid: () => boolean }

    expect(vm.isValid()).toBe(false)

    await wrapper.find('input').setValue('42')
    expect(vm.isValid()).toBe(true)
  })
})