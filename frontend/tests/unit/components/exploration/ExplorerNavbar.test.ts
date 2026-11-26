import { describe, expect, it } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ExplorerNavbar from '@/modules/exploration/components/ExplorerNavbar.vue'

describe('ExplorerNavbar', () => {
  it('groups explorer position and recall controls in one compact frame', async () => {
    setActivePinia(createPinia())
    const wrapper = mount(ExplorerNavbar, {
      props: { currentIndex: 1, total: 3, hasPrevious: true, hasNext: true, canRecall: true },
      global: { stubs: { Icon: true } },
    })

    expect(wrapper.find('.explorer-navigation-box').text()).toContain('2 / 3')
    expect(wrapper.find('.explorer-navigation-box').findAll('button')).toHaveLength(2)
    expect(wrapper.find('[aria-label="Recall dweller"]').exists()).toBe(true)

    await wrapper.find('[aria-label="Recall dweller"]').trigger('click')
    expect(wrapper.emitted('recall')).toHaveLength(1)
  })
})
