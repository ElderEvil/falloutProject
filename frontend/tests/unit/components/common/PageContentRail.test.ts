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

  it('narrows to the 1200px content column when width is content', async () => {
    const wrapper = mount(PageContentRail, {
      props: { width: 'content' },
      slots: { default: '<p>Detail content</p>' },
    })

    expect(wrapper.classes()).toContain('max-w-[1200px]')
    expect(wrapper.classes()).not.toContain('max-w-[1400px]')
    expect(wrapper.classes()).toEqual(expect.arrayContaining(['px-4', 'sm:px-6', 'lg:px-8']))

    await wrapper.setProps({ width: 'wide' })
    expect(wrapper.classes()).toContain('max-w-[1400px]')
    expect(wrapper.classes()).not.toContain('max-w-[1200px]')
  })

  it('narrows to the 900px column for chat when width is narrow', () => {
    const wrapper = mount(PageContentRail, {
      props: { width: 'narrow' },
      slots: { default: '<p>Chat</p>' },
    })

    expect(wrapper.classes()).toContain('max-w-[900px]')
    expect(wrapper.classes()).not.toContain('max-w-[1400px]')
    expect(wrapper.classes()).not.toContain('max-w-[1200px]')
    expect(wrapper.classes()).toEqual(expect.arrayContaining(['mx-auto', 'w-full', 'px-4']))
  })
})
