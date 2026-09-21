import { describe, expect, it } from 'vitest'

import { mountWithSetup } from '../../helpers/mountWithSetup'
import UAlert from '@/core/components/ui/UAlert.vue'

describe('UAlert', () => {
  it('renders an alert with the title and slot content', () => {
    const wrapper = mountWithSetup(UAlert, {
      props: { title: 'Warning' },
      slots: { default: 'Radiation detected' },
    })

    const alert = wrapper.find('[role="alert"]')
    expect(alert.exists()).toBe(true)
    expect(alert.text()).toContain('Warning')
    expect(alert.text()).toContain('Radiation detected')
  })

  it('renders a dismiss button only when dismissible', () => {
    const plain = mountWithSetup(UAlert, { slots: { default: 'Info' } })
    expect(plain.find('button').exists()).toBe(false)

    const dismissible = mountWithSetup(UAlert, {
      props: { dismissible: true },
      slots: { default: 'Info' },
    })
    expect(dismissible.find('button[aria-label="Dismiss alert"]').exists()).toBe(true)
  })

  it('emits close and removes the alert when dismissed', async () => {
    const wrapper = mountWithSetup(UAlert, {
      props: { dismissible: true },
      slots: { default: 'Info' },
    })

    await wrapper.find('button[aria-label="Dismiss alert"]').trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)

    // Let the leave transition finish before asserting the alert is gone.
    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('renders without a title', () => {
    const wrapper = mountWithSetup(UAlert, { slots: { default: 'Just a message' } })

    expect(wrapper.find('[role="alert"]').text()).toContain('Just a message')
  })
})