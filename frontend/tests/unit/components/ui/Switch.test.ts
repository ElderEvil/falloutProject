import { describe, expect, it } from 'vitest'

import { mountWithSetup } from '../../helpers/mountWithSetup'
import Switch from '@/core/components/ui/switch/Switch.vue'

function root(wrapper: ReturnType<typeof mountWithSetup>) {
  return wrapper.find('[data-slot="switch"]')
}

describe('Switch', () => {
  it('renders unchecked by default with switch semantics', () => {
    const wrapper = mountWithSetup(Switch)

    expect(root(wrapper).attributes('role')).toBe('switch')
    expect(root(wrapper).attributes('aria-checked')).toBe('false')
    expect(root(wrapper).attributes('data-state')).toBe('unchecked')
  })

  it('renders the checked state from the checked prop', () => {
    const wrapper = mountWithSetup(Switch, { props: { checked: true } })

    expect(root(wrapper).attributes('aria-checked')).toBe('true')
    expect(root(wrapper).attributes('data-state')).toBe('checked')
  })

  it('emits the toggled value on click', async () => {
    const wrapper = mountWithSetup(Switch, { props: { checked: false } })

    await root(wrapper).trigger('click')

    expect(wrapper.emitted('update:checked')).toEqual([[true]])
  })

  it('emits false when clicking a checked switch', async () => {
    const wrapper = mountWithSetup(Switch, { props: { checked: true } })

    await root(wrapper).trigger('click')

    expect(wrapper.emitted('update:checked')).toEqual([[false]])
  })

  it('toggles on Enter keydown', async () => {
    const wrapper = mountWithSetup(Switch, { props: { checked: false } })

    await root(wrapper).trigger('keydown.enter')

    expect(wrapper.emitted('update:checked')).toEqual([[true]])
  })

  it('renders a native button so Space activates it like a switch', () => {
    const wrapper = mountWithSetup(Switch)

    expect(root(wrapper).element.tagName).toBe('BUTTON')
  })

  it('does not emit when disabled', async () => {
    const wrapper = mountWithSetup(Switch, { props: { checked: false, disabled: true } })

    expect(root(wrapper).attributes('data-disabled')).toBeDefined()
    await root(wrapper).trigger('click')
    await root(wrapper).trigger('keydown.enter')

    expect(wrapper.emitted('update:checked')).toBeUndefined()
  })

  it('forwards the aria-label to the switch', () => {
    const wrapper = mountWithSetup(Switch, { props: { 'aria-label': 'Enable notifications' } })

    expect(root(wrapper).attributes('aria-label')).toBe('Enable notifications')
  })

  it('supports v-model:checked', async () => {
    const wrapper = mountWithSetup({
      components: { Switch },
      template: '<Switch v-model:checked="value" />',
      data: () => ({ value: false }),
    })

    await wrapper.find('[data-slot="switch"]').trigger('click')

    expect(wrapper.vm.value).toBe(true)
  })

  it('merges caller classes onto the root', () => {
    const wrapper = mountWithSetup(Switch, { props: { class: 'mt-4' } })

    // Caller-provided class passthrough (not an implementation-class
    // assertion: 'mt-4' is test input, so this survives component rewrites).
    expect(root(wrapper).attributes('class')).toContain('mt-4')
  })
})