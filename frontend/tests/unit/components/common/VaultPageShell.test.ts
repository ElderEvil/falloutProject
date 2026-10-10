import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import VaultPageShell from '@/core/components/common/VaultPageShell.vue'

vi.mock('@/core/composables/useSidePanel', () => ({
  useSidePanel: () => ({ isCollapsed: { value: false } }),
}))

const mountShell = (flicker: boolean, isFlickeringEnabled?: boolean) =>
  mount(VaultPageShell, {
    props: { flicker },
    global: {
      stubs: { SidePanel: { template: '<nav data-testid="side-panel" />' } },
      provide: isFlickeringEnabled === undefined ? {} : { isFlickering: ref(isFlickeringEnabled) },
    },
    slots: { default: '<div data-testid="page-content">Content</div>' },
  })

describe('VaultPageShell', () => {
  it('renders the navigation and page content slot', () => {
    const wrapper = mountShell(false, true)

    expect(wrapper.find('[data-testid="side-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="page-content"]').text()).toBe('Content')
    expect(wrapper.find('main').classes()).not.toContain('flicker')
  })

  it('applies the shared flicker treatment when the provided gated flag is enabled', () => {
    const wrapper = mountShell(true, true)

    expect(wrapper.find('main').classes()).toContain('flicker')
    wrapper.unmount()
  })

  it('does not flicker when the provided gated flag is disabled', () => {
    const wrapper = mountShell(true, false)

    expect(wrapper.find('main').classes()).not.toContain('flicker')
    wrapper.unmount()
  })

  it('does not flicker when no provider is present', () => {
    const wrapper = mountShell(true)

    expect(wrapper.find('main').classes()).not.toContain('flicker')
    wrapper.unmount()
  })
})
