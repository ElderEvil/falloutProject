import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import UToast from '@/core/components/ui/UToast.vue'

describe('UToast', () => {
  it.each([
    ['success', 'border-theme-primary', 'text-theme-primary'],
    ['warning', 'border-theme-accent', 'text-theme-accent'],
    ['info', 'border-theme-primary', 'text-theme-primary'],
  ] as const)('uses semantic theme utilities for %s toasts', (variant, borderClass, iconClass) => {
    const wrapper = mount(UToast, {
      props: { toast: { id: 'toast-1', message: 'Vault status updated', variant, count: 2 } },
    })

    expect(wrapper.classes()).toContain(borderClass)
    expect(wrapper.find('svg').classes()).toContain(iconClass)
    expect(wrapper.find('span').classes()).toContain('bg-theme-primary')
    expect(wrapper.html()).not.toContain('[--color-theme-')
  })
})
