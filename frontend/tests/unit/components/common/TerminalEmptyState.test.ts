import { describe, expect, it } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import TerminalEmptyState from '@/core/components/common/TerminalEmptyState.vue'

describe('TerminalEmptyState', () => {
  it('renders its shared warm surface and optional action', () => {
    const wrapper = mount(TerminalEmptyState, {
      props: {
        icon: 'mdi:package-variant-closed',
        title: 'Storage Empty',
        description: 'Send explorers to find supplies.',
      },
      slots: { actions: '<button>Open expedition</button>' },
    })

    expect(wrapper.classes()).toContain('bg-surface')
    expect(wrapper.text()).toContain('Storage Empty')
    expect(wrapper.text()).toContain('Open expedition')
  })

  it('can blend into a parent surface when requested', () => {
    const wrapper = mount(TerminalEmptyState, {
      props: { icon: 'mdi:package-variant-closed', title: 'Storage Empty', transparent: true },
    })

    expect(wrapper.classes()).toContain('bg-transparent')
    expect(wrapper.classes()).not.toContain('bg-surface')
  })

  it('uses only compact spacing and icon dimensions in compact mode', () => {
    const wrapper = mount(TerminalEmptyState, {
      props: { icon: 'mdi:package-variant-closed', title: 'Storage Empty', compact: true },
    })

    expect(wrapper.classes()).toContain('py-8')
    expect(wrapper.classes()).not.toContain('py-12')
    expect(wrapper.find('svg').classes()).toContain('h-12')
    expect(wrapper.find('svg').classes()).not.toContain('h-16')
  })
})
