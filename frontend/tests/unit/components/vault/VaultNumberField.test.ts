import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import VaultNumberField from '@/modules/vault/components/VaultNumberField.vue'

afterEach(() => vi.restoreAllMocks())

describe('VaultNumberField', () => {
  it('renders a labelled number input', () => {
    const wrapper = mount(VaultNumberField, { props: { modelValue: '' } })

    expect(wrapper.find('label').text()).toContain('Vault Number')
    expect(wrapper.find('input').attributes('type')).toBe('number')
    expect(wrapper.find('input').attributes('placeholder')).toBe('1–999')
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

  it('generates valid vault numbers across the random range and clears validation errors', async () => {
    vi.spyOn(Math, 'random').mockReturnValueOnce(0).mockReturnValueOnce(0.99999)
    const wrapper = mount(VaultNumberField, { props: { modelValue: '' } })
    await wrapper.get('input').setValue('1000')
    expect(wrapper.text()).toContain('Invalid vault number')
    const random = wrapper.get('button[aria-label="Random vault number"]')
    await random.trigger('click')
    expect((wrapper.get('input').element as HTMLInputElement).value).toBe('1')
    expect(wrapper.text()).not.toContain('Invalid vault number')
    await random.trigger('click')
    expect((wrapper.get('input').element as HTMLInputElement).value).toBe('999')
  })
})
