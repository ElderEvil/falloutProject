import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ExplorerNavbar from '@/modules/exploration/components/ExplorerNavbar.vue'

describe('ExplorerNavbar', () => {
  it('groups explorer position and navigation controls in one compact frame', () => {
    const wrapper = mount(ExplorerNavbar, {
      props: {
        currentIndex: 1,
        total: 3,
        hasPrevious: true,
        hasNext: true,
      },
      global: {
        stubs: { Icon: true },
      },
    })

    expect(wrapper.find('.explorer-navigation').classes()).not.toContain('border-b-[3px]')
    expect(wrapper.find('.explorer-navigation-box').text()).toContain('2 / 3')
    expect(wrapper.find('.explorer-navigation-box').findAll('button')).toHaveLength(2)
  })
})
