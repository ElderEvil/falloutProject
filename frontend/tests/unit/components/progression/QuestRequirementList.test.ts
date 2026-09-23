import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Icon } from '@iconify/vue'
import QuestRequirementList from '@/modules/progression/components/QuestRequirementList.vue'

const requirements = [
  { id: 'req-1', requirement_type: 'level', requirement_data: { level: 5 }, is_mandatory: true },
  { id: 'req-2', requirement_type: 'dweller_count', requirement_data: { count: 10 }, is_mandatory: false },
]

describe('QuestRequirementList', () => {
  it('renders humanized requirement rows with met styling', () => {
    setActivePinia(createPinia())
    const wrapper = mount(QuestRequirementList, {
      props: { requirements, isMet: () => true },
    })

    expect(wrapper.text()).toContain('Requires Level 5+ dweller')
    expect(wrapper.text()).toContain('Reach 10 dwellers')
    expect(wrapper.text()).not.toContain('dweller_count')
    expect(wrapper.find('.prerequisite-item.met').exists()).toBe(true)
    expect(wrapper.findAllComponents(Icon).length).toBeGreaterThan(0)
  })

  it('marks unmet requirements with the locked styling', () => {
    setActivePinia(createPinia())
    const wrapper = mount(QuestRequirementList, {
      props: { requirements, isMet: (req) => req.requirement_type !== 'dweller_count' },
    })

    expect(wrapper.findAll('.prerequisite-item.unmet')).toHaveLength(1)
  })
})
