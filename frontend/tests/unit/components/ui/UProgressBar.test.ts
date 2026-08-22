import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import UProgressBar from '@/core/components/ui/UProgressBar.vue'

describe('UProgressBar', () => {
  it('uses the semantic sunken surface for its track', () => {
    const wrapper = mount(UProgressBar, { props: { modelValue: 50 } })

    expect(wrapper.classes()).toContain('u-progress-bar--sunken')
  })
})
