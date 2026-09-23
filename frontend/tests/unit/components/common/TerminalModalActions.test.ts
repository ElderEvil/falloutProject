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

  it('disables the confirm action while confirmDisabled is set', () => {
    const enabled = mount(TerminalModalActions, {
      props: { cancelLabel: 'Review Later', confirmLabel: 'Confirm & Claim' },
    })
    expect(enabled.get('.confirm').attributes('disabled')).toBeUndefined()

    const disabled = mount(TerminalModalActions, {
      props: { cancelLabel: 'Review Later', confirmLabel: 'Confirm & Claim', confirmDisabled: true },
    })
    expect(disabled.get('.confirm').attributes('disabled')).toBeDefined()
  })
})
