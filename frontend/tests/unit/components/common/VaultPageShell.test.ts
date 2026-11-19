import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vite-plus/test'
import { ref } from 'vue'
import VaultPageShell from '@/core/components/common/VaultPageShell.vue'

const { sidePanelState } = vi.hoisted(() => ({
  sidePanelState: { isCollapsed: false },
}))

vi.mock('@/core/composables/useSidePanel', async () => {
  const { ref: makeRef } = await import('vue')
  return {
    useSidePanel: () => ({ isCollapsed: makeRef(sidePanelState.isCollapsed) }),
  }
})

const mountShell = (flicker: boolean, isFlickeringEnabled?: boolean, sidePanel = true) =>
  mount(VaultPageShell, {
    props: { flicker, sidePanel },
    global: {
      stubs: { SidePanel: { template: '<nav data-testid="side-panel" />' } },
      provide: isFlickeringEnabled === undefined ? {} : { isFlickering: ref(isFlickeringEnabled) },
    },
    slots: { default: '<div data-testid="page-content">Content</div>' },
  })

afterEach(() => {
  sidePanelState.isCollapsed = false
})

describe('VaultPageShell', () => {
  it('renders the navigation and page content slot', () => {
    const wrapper = mountShell(false, true)
    expect(wrapper.find('[data-testid="side-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="page-content"]').text()).toBe('Content')
    expect(wrapper.find('main').classes()).not.toContain('flicker')
    wrapper.unmount()
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

  it('keeps the expanded panel margin while the side panel is shown', () => {
    const wrapper = mountShell(false, true)
    const classes = wrapper.find('main').classes()
    expect(classes).toContain('ml-60')
    expect(classes).not.toContain('ml-16')
    expect(classes).not.toContain('ml-0')
    wrapper.unmount()
  })

  it('uses the collapsed panel margin while the side panel is collapsed', () => {
    sidePanelState.isCollapsed = true
    const wrapper = mountShell(false, true)
    const classes = wrapper.find('main').classes()
    expect(classes).toContain('ml-16')
    expect(classes).not.toContain('ml-60')
    wrapper.unmount()
  })

  it('drops the panel margin when no side panel is rendered', () => {
    const wrapper = mountShell(false, true, false)
    expect(wrapper.find('[data-testid="side-panel"]').exists()).toBe(false)
    const classes = wrapper.find('main').classes()
    expect(classes).toContain('ml-0')
    expect(classes).not.toContain('ml-60')
    expect(classes).not.toContain('ml-16')
    wrapper.unmount()
  })

  it('drops the panel margin regardless of collapse state when no side panel is rendered', () => {
    sidePanelState.isCollapsed = true
    const wrapper = mountShell(false, true, false)
    const classes = wrapper.find('main').classes()
    expect(classes).toContain('ml-0')
    expect(classes).not.toContain('ml-16')
    wrapper.unmount()
  })
})