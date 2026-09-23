import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { Icon } from '@iconify/vue'
import QuestRewardList from '@/modules/progression/components/QuestRewardList.vue'

const rewards = [
  { id: 'reward-1', reward_type: 'caps', reward_data: { amount: 50 }, reward_chance: 1 },
  {
    id: 'reward-2',
    reward_type: 'item',
    reward_data: { item_name: 'Stimpak', rarity: 'common' },
    reward_chance: 0.5,
  },
]

describe('QuestRewardList', () => {
  it('renders formatted labels with category icons and chance suffixes', () => {
    const wrapper = mount(QuestRewardList, { props: { rewards } })

    expect(wrapper.text()).toContain('50 Caps')
    expect(wrapper.text()).toContain('Stimpak')
    expect(wrapper.text()).not.toContain('(common)')
    expect(wrapper.text()).toContain('(50%)')
    const icons = wrapper.findAllComponents(Icon).map((icon) => icon.props('icon'))
    expect(icons).toContain('mdi:currency-usd')
    expect(icons).toContain('mdi:medical-bag')
  })

  it('renders the fallback text when no rewards are set', () => {
    const wrapper = mount(QuestRewardList, { props: { rewards: [], fallbackText: '100 Caps' } })

    expect(wrapper.text()).toContain('100 Caps')
  })
})
