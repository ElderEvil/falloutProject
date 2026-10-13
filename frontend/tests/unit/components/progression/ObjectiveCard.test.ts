import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { Progress } from '@/core/components/ui/progress'
import ObjectiveCard from '@/modules/progression/components/ObjectiveCard.vue'

describe('ObjectiveCard', () => {
  it('uses the shared progress bar with the objective percentage', () => {
    const progressBar = mount(ObjectiveCard, {
      props: {
        objective: {
          id: '1',
          vault_id: 'v1',
          challenge: 'Collect caps',
          progress: 40,
          total: 100,
          reward: '50 Caps',
          is_completed: false,
          category: 'daily',
          created_at: '',
        },
      },
    }).findComponent(Progress)
    expect(progressBar.exists()).toBe(true)
    expect(progressBar.props()).toMatchObject({ modelValue: 40 })
    expect(progressBar.find('[aria-label="Objective progress"]').exists()).toBe(true)
  })

  it('marks a completed objective with the completed card and stamp instead of the claim button', () => {
    const card = mount(ObjectiveCard, {
      props: {
        objective: {
          id: '2',
          vault_id: 'v1',
          challenge: 'Collect caps',
          progress: 100,
          total: 100,
          reward: '50 Caps',
          is_completed: true,
          category: 'daily',
          created_at: '',
        },
      },
    })
    expect(card.find('.completed-card').exists()).toBe(true)
    expect(card.find('.completed-stamp').exists()).toBe(true)
    expect(card.find('.claim-btn').exists()).toBe(false)
  })

  it.each([
    ['production_only', 'Production counts even when storage is full.'],
    ['distinct_dwellers', 'Each dweller counts once for this objective.'],
  ])('explains the %s counting rule', (rule, message) => {
    const objective = {
      id: '3',
      vault_id: 'v1',
      challenge: 'Produce power',
      progress: 10,
      total: 150,
      reward: '15 caps',
      is_completed: false,
      category: 'daily' as const,
      created_at: '',
      target_entity: { [rule]: true },
    }
    const card = mount(ObjectiveCard, { props: { objective } })
    expect(card.text()).toContain(message)
    const ordinary = mount(ObjectiveCard, {
      props: { objective: { ...objective, target_entity: {} } },
    })
    expect(ordinary.text()).not.toContain(message)
  })
})
