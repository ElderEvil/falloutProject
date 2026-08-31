import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import TrainingProgressCard from '@/modules/progression/components/training/TrainingProgressCard.vue'

describe('TrainingProgressCard', () => {
  it('uses a calm ready state instead of bouncing and pulsing the completion card', () => {
    const wrapper = mount(TrainingProgressCard, {
      props: {
        training: {
          id: 'training-1',
          dweller_id: 'dweller-1',
          room_id: 'room-1',
          stat_being_trained: 'strength',
          current_stat_value: 4,
          target_stat_value: 5,
          status: 'active',
          progress: 1,
          started_at: new Date(Date.now() - 60_000).toISOString(),
          estimated_completion_at: new Date(Date.now() - 1_000).toISOString(),
        },
      },
      global: {
        stubs: {
          Icon: true,
          UButton: true,
          UBadge: true,
          UProgressBar: true,
          DwellerPortrait: true,
        },
      },
    })

    const card = wrapper.find('.training-progress-card')
    expect(card.classes()).toContain('completion-ready')
    expect(card.classes().join(' ')).not.toContain('animate-[')
    expect(wrapper.find('.completion-stat-icon').classes().join(' ')).not.toContain('animate-[')
    expect(wrapper.find('.completion-time').classes().join(' ')).not.toContain('animate-[')

    wrapper.unmount()
  })
})
