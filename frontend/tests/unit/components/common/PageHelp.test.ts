import { afterEach, describe, expect, it } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import PageHeader from '@/core/components/common/PageHeader.vue'

enableAutoUnmount(afterEach)

describe('Page help', () => {
  it('opens named help on demand and closes it while keeping actionable content visible', async () => {
    const wrapper = mount(PageHeader, {
      attachTo: document.body,
      props: { title: 'Response Teams' },
      slots: {
        help: '<p>Membership is earned through incident participation.</p>',
        actions: '<span>2 open places</span>',
      },
      global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
    })
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Membership is earned')
    expect(wrapper.text()).toContain('2 open places')
    await wrapper.find('button[aria-label="About Response Teams"]').trigger('click')
    await flushPromises()
    const dialog = wrapper.find('[role="dialog"]')
    expect(dialog.exists()).toBe(true)
    expect(dialog.attributes('aria-labelledby')).toBeTruthy()
    expect(dialog.text()).toContain('Membership is earned')
    await dialog.trigger('keydown', { key: 'Escape' })
    await flushPromises()
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    await wrapper.find('button[aria-label="About Response Teams"]').trigger('click')
    await flushPromises()
    await wrapper.find('[role="dialog"]').find('button').trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('2 open places')
  })

  it('does not add an About control to pages without help', () => {
    const wrapper = mount(PageHeader, { props: { title: 'Storage' } })
    expect(wrapper.find('button').exists()).toBe(false)
  })
})
