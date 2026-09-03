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
})
