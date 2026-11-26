import { describe, expect, it } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import { Progress } from '@/core/components/ui/progress'
import CollectibleSetsPanel from '@/modules/map/components/CollectibleSetsPanel.vue'

const sets = [
  { set: 'magazines', name: 'Magazines', held: 2, required: 3, active: false },
  { set: 'comics', name: 'Comics', held: 4, required: 4, active: true },
]

describe('CollectibleSetsPanel', () => {
  it('shows each set progress and marks a completed set as active', () => {
    const wrapper = mount(CollectibleSetsPanel, { props: { sets } })

    expect(wrapper.text()).toContain('Magazines')
    expect(wrapper.text()).toContain('2 / 3')
    expect(wrapper.text()).toContain('Comics')
    expect(wrapper.text()).toContain('4 / 4')
    expect(wrapper.findAllComponents(Progress).map((bar) => bar.props('modelValue'))).toEqual([
      67, 100,
    ])
  })

  it('only marks a set whose bonus is being paid', () => {
    const wrapper = mount(CollectibleSetsPanel, { props: { sets } })

    expect(wrapper.findAll('.set-active')).toHaveLength(1)
    expect(wrapper.find('.set-active').text()).toBe('Bonus active')
  })
})
