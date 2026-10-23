import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vite-plus/test'

import ComponentLoader from '@/core/components/common/ComponentLoader.vue'

describe('ComponentLoader', () => {
  it('announces a contextual loading label', () => {
    const wrapper = mount(ComponentLoader, { props: { label: 'Loading arena…' } })

    expect(wrapper.attributes('aria-label')).toBe('Loading arena…')
    expect(wrapper.text()).toContain('Loading arena…')
  })
})
