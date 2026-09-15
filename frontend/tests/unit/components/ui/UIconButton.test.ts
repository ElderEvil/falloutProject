import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import UIconButton from '@/core/components/ui/UIconButton.vue'
import UTooltip from '@/core/components/ui/UTooltip.vue'

describe('UIconButton', () => {
  it('requires a label in the rendered control and emits clicks', async () => {
    const wrapper = mount(UIconButton, {
      props: { icon: 'mdi:close', label: 'Clear fighter' },
    })

    await wrapper.get('button').trigger('click')

    expect(wrapper.get('button').attributes('aria-label')).toBe('Clear fighter')
    expect(wrapper.get('button').attributes('aria-describedby')).toBeTruthy()
    expect(wrapper.get('button').attributes('title')).toBeUndefined()
    expect(wrapper.findComponent(UTooltip).props('text')).toBe('Clear fighter')
    expect(wrapper.emitted('click')).toHaveLength(1)
  })
})
