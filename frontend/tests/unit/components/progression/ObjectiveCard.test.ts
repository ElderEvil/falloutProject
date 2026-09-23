import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { Progress } from '@/core/components/ui/progress'
import ObjectiveCard from '@/modules/progression/components/ObjectiveCard.vue'

describe('ObjectiveCard', () => {
  it('uses the shared progress bar with the objective percentage', () => {
    const progressBar = mount(ObjectiveCard, { props: { objective: { id: '1', vault_id: 'v1', challenge: 'Collect caps', progress: 40, total: 100, reward: '50 Caps', is_completed: false, category: 'daily', created_at: '' } } }).findComponent(Progress)
    expect(progressBar.exists()).toBe(true)
    expect(progressBar.props()).toMatchObject({ modelValue: 40 })
    expect(progressBar.find('[aria-label="Objective progress"]').exists()).toBe(true)
  })

  it('marks a completed objective with the completed card and stamp instead of the claim button', () => {
    const card = mount(ObjectiveCard, { props: { objective: { id: '2', vault_id: 'v1', challenge: 'Collect caps', progress: 100, total: 100, reward: '50 Caps', is_completed: true, category: 'daily', created_at: '' } } })
    expect(card.find('.completed-card').exists()).toBe(true)
    expect(card.find('.completed-stamp').exists()).toBe(true)
    expect(card.find('.claim-btn').exists()).toBe(false)
  })
})
