import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { UProgressBar } from '@/core/components/ui'
import ObjectiveCard from '@/modules/progression/components/ObjectiveCard.vue'

describe('ObjectiveCard', () => {
  it('uses the shared progress bar with the objective percentage', () => {
    const progressBar = mount(ObjectiveCard, { props: { objective: { id: '1', vault_id: 'v1', challenge: 'Collect caps', progress: 40, total: 100, reward: '50 Caps', is_completed: false, category: 'daily', created_at: '' } } }).findComponent(UProgressBar)
    expect(progressBar.exists()).toBe(true)
    expect(progressBar.props()).toMatchObject({ modelValue: 40, height: 8, glow: false, ariaLabel: 'Objective progress' })
  })

  it('marks a completed objective with the completed card and stamp instead of the claim button', () => {
    const card = mount(ObjectiveCard, { props: { objective: { id: '2', vault_id: 'v1', challenge: 'Collect caps', progress: 100, total: 100, reward: '50 Caps', is_completed: true, category: 'daily', created_at: '' } } })
    expect(card.find('.completed-card').exists()).toBe(true)
    expect(card.find('.completed-stamp').exists()).toBe(true)
    expect(card.find('.claim-btn').exists()).toBe(false)
  })
})
