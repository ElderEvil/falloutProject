import { describe, expect, it } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import LoadingInline from '@/core/components/common/LoadingInline.vue'

describe('LoadingInline', () => {
  it('announces standalone loading with a status role and label', () => {
    const wrapper = mount(LoadingInline, {
      props: { label: 'Loading notifications…' },
      global: { stubs: { Icon: true } },
    })

    expect(wrapper.attributes('role')).toBe('status')
    expect(wrapper.attributes('aria-live')).toBe('polite')
    expect(wrapper.text()).toContain('Loading notifications…')
  })

  it('stays silent when the surrounding button already announces busy state', () => {
    const wrapper = mount(LoadingInline, {
      props: { decorative: true },
      global: { stubs: { Icon: true } },
    })

    expect(wrapper.attributes('role')).toBeUndefined()
    expect(wrapper.attributes('aria-hidden')).toBe('true')
    expect(wrapper.text()).toBe('')
  })
})
