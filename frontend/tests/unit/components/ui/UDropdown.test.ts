import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import UDropdown from '@/core/components/ui/UDropdown.vue'

describe('UDropdown (Accessibility)', () => {
  const createWrapper = () =>
    mount(UDropdown, {
      slots: {
        trigger: '<span>Open</span>',
        default: '<div class="dropdown-content">Content</div>',
      },
    })

  it('should have role="button" on the trigger element', () => {
    const wrapper = createWrapper()
    const trigger = wrapper.find('[data-testid="dropdown-trigger"]')
    expect(trigger.attributes('role')).toBe('button')
  })

  it('should have tabindex="0" on the trigger element', () => {
    const wrapper = createWrapper()
    const trigger = wrapper.find('[data-testid="dropdown-trigger"]')
    expect(trigger.attributes('tabindex')).toBe('0')
  })

  it('should open dropdown when Enter key is pressed on trigger', async () => {
    const wrapper = createWrapper()
    const trigger = wrapper.find('[data-testid="dropdown-trigger"]')
    await trigger.trigger('keydown.enter')
    expect(wrapper.find('.dropdown-content').exists()).toBe(true)
  })

  it('should open dropdown when Space key is pressed on trigger', async () => {
    const wrapper = createWrapper()
    const trigger = wrapper.find('[data-testid="dropdown-trigger"]')
    await trigger.trigger('keydown.space')
    expect(wrapper.find('.dropdown-content').exists()).toBe(true)
  })
})
