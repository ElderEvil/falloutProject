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
          Button: true,
          Badge: true,
          Progress: true,
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

  it('lets players set an active training goal before enabling repeat', async () => {
    const wrapper = mount(TrainingProgressCard, {
      props: {
        dwellerName: 'Alice',
        training: {
          id: 't1',
          dweller_id: 'd1',
          room_id: 'r1',
          stat_being_trained: 'strength',
          current_stat_value: 5,
          target_stat_value: 6,
          goal_stat_value: 8,
          status: 'active',
          progress: 0,
          started_at: new Date().toISOString(),
          estimated_completion_at: new Date(Date.now() + 42 * 60_000).toISOString(),
        },
      },
      global: { stubs: { Icon: true, DwellerPortrait: true } },
    })
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('Strength 5 → 6')
    expect(wrapper.text()).toContain('42m left')
    expect(wrapper.text()).toContain('Goal:')
    const goal = wrapper.get('[role=group][aria-label="Training goal for Alice"]')
    expect(goal.text()).toContain('8')
    const decrease = goal.get('button[aria-label="Decrease goal for Alice"]')
    const increase = goal.get('button[aria-label="Increase goal for Alice"]')
    await decrease.trigger('click')
    await increase.trigger('click')
    expect(wrapper.emitted('goal')).toEqual([
      ['t1', 7],
      ['t1', 9],
    ])
    await wrapper.setProps({ isSavingGoal: true })
    expect(decrease.attributes('aria-disabled')).toBe('true')
    expect(increase.attributes('aria-disabled')).toBe('true')
    expect(decrease.attributes()).not.toHaveProperty('disabled')
    await decrease.trigger('click')
    expect(wrapper.emitted('goal')).toHaveLength(2)
    await wrapper.setProps({
      isSavingGoal: false,
      training: { ...wrapper.props('training'), goal_stat_value: 6 },
    })
    expect(decrease.attributes()).toHaveProperty('disabled')
    expect(increase.attributes()).not.toHaveProperty('disabled')
    await wrapper.setProps({ training: { ...wrapper.props('training'), goal_stat_value: 10 } })
    expect(increase.attributes()).toHaveProperty('disabled')
    expect(decrease.attributes()).not.toHaveProperty('disabled')
    expect(wrapper.text()).toContain('Goal:')
    expect(wrapper.get('[role=progressbar]').attributes('aria-label')).toBe(
      'Strength training progress for Alice'
    )
    expect(wrapper.find('[title]').exists()).toBe(false)
    await wrapper.setProps({
      training: {
        ...wrapper.props('training'),
        estimated_completion_at: new Date(
          Date.parse(wrapper.props('training').started_at) + 120 * 60_000
        ).toISOString(),
      },
    })
    expect(wrapper.find('.completion-time').text()).toBe('2h 0m left')
    wrapper.unmount()
  })
})
