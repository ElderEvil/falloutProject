import { describe, expect, it } from 'vitest'

import { mountWithSetup } from '../../helpers/mountWithSetup'
import USelect from '@/core/components/ui/USelect.vue'

const options = [
  { value: 'vault', label: 'Vault 101' },
  { value: 'wasteland', label: 'Wasteland' },
]

describe('USelect', () => {
  it('renders a closed combobox trigger showing the placeholder', () => {
    const wrapper = mountWithSetup(USelect, {
      props: { options, placeholder: 'Choose a place' },
    })

    const trigger = wrapper.find('[role="combobox"]')
    expect(trigger.exists()).toBe(true)
    expect(trigger.attributes('aria-haspopup')).toBe('listbox')
    expect(trigger.attributes('aria-expanded')).toBe('false')
    expect(trigger.text()).toContain('Choose a place')
  })

  it('opens the listbox on click and lists the options', async () => {
    const wrapper = mountWithSetup(USelect, { props: { options } })

    const trigger = wrapper.find('[role="combobox"]')
    await trigger.trigger('click')

    expect(trigger.attributes('aria-expanded')).toBe('true')
    const listbox = wrapper.find('[role="listbox"]')
    expect(listbox.exists()).toBe(true)
    expect(wrapper.findAll('[role="option"]')).toHaveLength(2)
    expect(wrapper.text()).toContain('Vault 101')
    expect(listbox.attributes('id')).toBe(trigger.attributes('aria-controls'))
  })

  it('emits update:modelValue and closes the menu when an option is chosen', async () => {
    const wrapper = mountWithSetup(USelect, { props: { options } })

    const trigger = wrapper.find('[role="combobox"]')
    await trigger.trigger('click')
    await wrapper.findAll('[role="option"]')[1]!.trigger('click')

    expect(wrapper.emitted('update:modelValue')).toEqual([['wasteland']])
    expect(wrapper.find('[role="listbox"]').exists()).toBe(false)
    expect(trigger.attributes('aria-expanded')).toBe('false')
  })

  it('shows the selected option label instead of the placeholder', () => {
    const wrapper = mountWithSetup(USelect, {
      props: { options, modelValue: 'vault', placeholder: 'Choose a place' },
    })

    const trigger = wrapper.find('[role="combobox"]')
    expect(trigger.text()).toContain('Vault 101')
    expect(trigger.text()).not.toContain('Choose a place')
  })

  it('toggles with Enter and Space and closes with Escape', async () => {
    const wrapper = mountWithSetup(USelect, { props: { options } })
    const trigger = wrapper.find('[role="combobox"]')

    await trigger.trigger('keydown', { key: 'Enter' })
    expect(trigger.attributes('aria-expanded')).toBe('true')

    await trigger.trigger('keydown', { key: 'Escape' })
    expect(trigger.attributes('aria-expanded')).toBe('false')

    await trigger.trigger('keydown', { key: ' ' })
    expect(trigger.attributes('aria-expanded')).toBe('true')
  })

  it('associates the visible label via aria-labelledby', () => {
    const wrapper = mountWithSetup(USelect, {
      props: { options, label: 'Destination' },
    })

    const trigger = wrapper.find('[role="combobox"]')
    const labelId = trigger.attributes('aria-labelledby')
    expect(labelId).toBeTruthy()
    const label = wrapper.findAll('span').find((el) => el.text().includes('Destination'))
    expect(label?.attributes('id')).toBe(labelId)
  })

  it('uses aria-label when no visible label is given', () => {
    const wrapper = mountWithSetup(USelect, {
      props: { options, ariaLabel: 'Pick a place' },
    })

    expect(wrapper.find('[role="combobox"]').attributes('aria-label')).toBe('Pick a place')
  })

  it('does not open when disabled', async () => {
    const wrapper = mountWithSetup(USelect, { props: { options, disabled: true } })
    const trigger = wrapper.find('[role="combobox"]')

    expect(trigger.attributes('disabled')).toBeDefined()
    await trigger.trigger('click')
    expect(trigger.attributes('aria-expanded')).toBe('false')
    expect(wrapper.find('[role="listbox"]').exists()).toBe(false)
  })

  it('shows help text, and error text replaces it', () => {
    const withHelp = mountWithSetup(USelect, {
      props: { options, helpText: 'Pick one' },
    })
    expect(withHelp.text()).toContain('Pick one')

    const withError = mountWithSetup(USelect, {
      props: { options, error: 'Required', helpText: 'Pick one' },
    })
    expect(withError.text()).toContain('Required')
    expect(withError.text()).not.toContain('Pick one')
  })
})