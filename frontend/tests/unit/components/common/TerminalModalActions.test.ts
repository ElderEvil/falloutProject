import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import TerminalModalActions from '@/core/components/common/TerminalModalActions.vue'

describe('TerminalModalActions', () => {
  it('stacks long actions on narrow screens', () => {
    const wrapper = mount(TerminalModalActions, {
      props: { cancelLabel: 'Review Later', confirmLabel: 'Confirm & Claim' },
    })

    expect(wrapper.classes()).toContain('max-sm:flex-col')
    expect(wrapper.findAll('button').every((button) => button.classes().includes('max-sm:w-full'))).toBe(true)
  })
})
