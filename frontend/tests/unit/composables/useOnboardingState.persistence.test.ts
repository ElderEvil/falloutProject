import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { useOnboardingState } from '@/core/composables/useOnboardingState'

describe('useOnboardingState persistence', () => {
  it('keeps persisting after the first consumer unmounts', async () => {
    localStorage.clear()
    const consumer = defineComponent({
      setup() {
        useOnboardingState()
        return () => h('div')
      },
    })

    const wrapper = mount(consumer)
    wrapper.unmount()

    useOnboardingState().acknowledgeLesson('v1', 'orientation.resources')
    await vi.waitFor(() =>
      expect(localStorage.getItem('onboarding:v1')).toContain('orientation.resources')
    )
  })
})
