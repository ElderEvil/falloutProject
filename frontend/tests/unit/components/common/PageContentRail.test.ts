import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PageContentRail from '@/core/components/common/PageContentRail.vue'

describe('PageContentRail', () => {
  it('provides the shared responsive content rail and forwards extra classes', () => {
    const wrapper = mount(PageContentRail, {
      attrs: { class: 'flex flex-col gap-6' },
      slots: { default: '<p>Vault content</p>' },
    })

    expect(wrapper.text()).toContain('Vault content')
    expect(wrapper.classes()).toEqual(
      expect.arrayContaining(['max-w-[1400px]', 'px-4', 'sm:px-6', 'lg:px-8', 'flex', 'gap-6'])
    )
  })
})
