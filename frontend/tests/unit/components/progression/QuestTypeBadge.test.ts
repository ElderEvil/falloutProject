import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { Badge } from '@/core/components/ui/badge'
import QuestTypeBadge from '@/modules/progression/components/QuestTypeBadge.vue'

describe('QuestTypeBadge', () => {
  it('renders side quests with the bordered outline styling', () => {
    const wrapper = mount(QuestTypeBadge, { props: { questType: 'side' } })

    expect(wrapper.text()).toContain('Side')
    expect(wrapper.findComponent(Badge).props('variant')).toBe('outline')
    expect(wrapper.find('.type-badge').attributes('style')).toBeUndefined()
  })

  it('renders other types with their signature colors', () => {
    const wrapper = mount(QuestTypeBadge, { props: { questType: 'main' } })

    expect(wrapper.text()).toContain('Main')
    expect(wrapper.findComponent(Badge).props('variant')).toBe('default')
    expect(wrapper.find('.type-badge').attributes('style')).toContain('background-color')
  })
})
