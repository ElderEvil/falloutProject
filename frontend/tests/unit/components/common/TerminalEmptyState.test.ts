import { describe, expect, it } from 'vitest'
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
})
