import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import UButton from '@/core/components/ui/UButton.vue'

describe('UButton', () => {
  it('forwards an undeclared listener only once', async () => {
    const onDblclick = vi.fn()
    const wrapper = mount(UButton, {
      attrs: { onDblclick },
    })

    await wrapper.trigger('dblclick')

    expect(onDblclick).toHaveBeenCalledTimes(1)
  })
})
