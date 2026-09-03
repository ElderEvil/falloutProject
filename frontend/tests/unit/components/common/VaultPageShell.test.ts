import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import VaultPageShell from '@/core/components/common/VaultPageShell.vue'

vi.mock('@/core/composables/useSidePanel', () => ({
  useSidePanel: () => ({ isCollapsed: { value: false } }),
}))

describe('VaultPageShell', () => {
  it('renders the navigation and page content slot', () => {
    const wrapper = mount(VaultPageShell, {
      global: {
        stubs: { SidePanel: { template: '<nav data-testid="side-panel" />' } },
      },
      slots: { default: '<div data-testid="page-content">Content</div>' },
    })

    expect(wrapper.find('[data-testid="side-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="page-content"]').text()).toBe('Content')
    expect(wrapper.find('main').classes()).not.toContain('flicker')
  })

  it('can apply the shared flicker treatment to a page', () => {
    const wrapper = mount(VaultPageShell, {
      props: { flicker: true },
      global: {
        stubs: { SidePanel: true },
      },
    })

    expect(wrapper.find('main').classes()).toContain('flicker')
  })
})
