import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import UToast from '@/core/components/ui/UToast.vue'

describe('UToast', () => {
  it.each([
    ['success', 'border-l-success', 'text-success'],
    ['warning', 'border-l-warning', 'text-warning'],
    ['info', 'border-l-info', 'text-info'],
  ] as const)('uses semantic theme utilities for %s toasts', (variant, borderClass, iconClass) => {
    const wrapper = mount(UToast, {
      props: { toast: { id: 'toast-1', message: 'Vault status updated', variant, count: 2 } },
    })

    expect(wrapper.classes()).toContain(borderClass)
    expect(wrapper.find('svg').classes()).toContain(iconClass)
    expect(wrapper.find('span').classes()).toContain('bg-surface-hover')
    expect(wrapper.html()).not.toContain('[--color-theme-')
  })

  it('uses a polite status announcement and a restrained raised surface for errors', () => {
    const wrapper = mount(UToast, {
      props: { toast: { id: 'toast-1', message: 'Signal lost', variant: 'error' } },
    })

    expect(wrapper.attributes('role')).toBe('status')
    expect(wrapper.attributes('aria-live')).toBe('polite')
    expect(wrapper.classes()).toContain('bg-surface-raised/95')
    expect(wrapper.classes()).not.toContain('bg-red-900/90')
    expect(wrapper.find('button').classes()).toContain('focus-visible:ring-2')
  })
})
