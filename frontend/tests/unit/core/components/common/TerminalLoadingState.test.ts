import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import TerminalLoadingState from '@/core/components/common/TerminalLoadingState.vue'

describe('TerminalLoadingState', () => {
  it('announces its message as a polite loading status', () => {
    const wrapper = mount(TerminalLoadingState, {
      props: { message: 'Loading vault data...' },
    })

    const status = wrapper.get('[role="status"]')

    expect(status.attributes('aria-live')).toBe('polite')
    expect(status.text()).toContain('Loading vault data...')
  })

  it('uses a full-height layout when requested', () => {
    const wrapper = mount(TerminalLoadingState, {
      props: { message: 'Loading vault data...', fullHeight: true },
    })

    expect(wrapper.classes()).toContain('min-h-[60vh]')
  })
})
