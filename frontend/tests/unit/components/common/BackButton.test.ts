import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import BackButton from '@/core/components/common/BackButton.vue'

describe('BackButton', () => {
  it('renders its destination label and emits click', async () => {
    const wrapper = mount(BackButton, { props: { label: 'Back to Vault' } })

    expect(wrapper.get('button').text()).toContain('Back to Vault')
    expect(wrapper.get('button').attributes('aria-label')).toBe('Back to Vault')

    await wrapper.get('button').trigger('click')

    expect(wrapper.emitted('click')).toHaveLength(1)
  })
})
