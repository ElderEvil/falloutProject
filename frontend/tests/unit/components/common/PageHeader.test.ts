import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PageHeader from '@/core/components/common/PageHeader.vue'

describe('PageHeader', () => {
  it('keeps the icon aligned to the title when a description is present', () => {
    const wrapper = mount(PageHeader, {
      props: {
        title: 'Dwellers',
        icon: 'mdi:account-group',
        subtitle: 'Assign, train & equip your vault population.',
      },
    })

    expect(wrapper.find('h1').text()).toBe('Dwellers')
    expect(wrapper.find('.page-header > div').classes()).toContain('items-start')
    expect(wrapper.find('p').classes()).toContain('text-theme-primary/60')
  })
})
