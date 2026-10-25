import { describe, expect, it } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import CombatEffect from '@/modules/combat/components/CombatEffect.vue'
import CombatantMotion from '@/modules/combat/components/CombatantMotion.vue'
import type { PlayingCombatAction } from '@/modules/combat/models/playback'

const action: PlayingCombatAction = {
  id: 'hit-1',
  message: 'Lucy fires',
  action: {
    actor_id: 'lucy',
    actor_body: 'ghoul',
    effect: 'shot',
    targets: [{ target_id: 'maximus', body: 'power-armor', damage: 5 }],
  },
}

describe('CombatantMotion', () => {
  it('braces for a shot and recoils at impact instead of lunging', async () => {
    const wrapper = mount(CombatantMotion, {
      props: { fighterId: 'lucy', action, phase: 'prepare' },
    })
    expect(wrapper.getComponent(CombatEffect).props()).toMatchObject({
      effect: 'shot',
      preparing: true,
    })
    await wrapper.setProps({ phase: 'impact' })
    expect(wrapper.getComponent(CombatEffect).props('preparing')).toBe(false)
  })
  it('winds up and follows through for melee', async () => {
    const wrapper = mount(CombatantMotion, {
      props: {
        fighterId: 'lucy',
        action: { ...action, action: { ...action.action, effect: 'thrust' } },
        phase: 'prepare',
      },
      slots: { default: '<span>portrait</span>' },
    })
    expect(wrapper.get('.combat-body--windup').text()).toBe('portrait')
    await wrapper.setProps({ phase: 'impact' })
    expect(wrapper.getComponent(CombatEffect).props()).toMatchObject({
      effect: 'thrust',
      preparing: false,
    })
  })
  it('only reacts on the resolved target at impact, with armor sparks', async () => {
    const wrapper = mount(CombatantMotion, {
      props: { fighterId: 'maximus', action, phase: 'prepare' },
    })
    expect(wrapper.find('.combat-effect').exists()).toBe(false)
    await wrapper.setProps({ phase: 'impact' })
    expect(wrapper.getComponent(CombatEffect).props('metal')).toBe(true)
    expect(wrapper.find('.armor-sparks').exists()).toBe(true)
    await wrapper.setProps({ fighterId: 'bystander' })
    expect(wrapper.find('.combat-effect').exists()).toBe(false)
  })
  it('keeps catch-up motion stationary and supports legacy actions', async () => {
    const wrapper = mount(CombatantMotion, {
      props: { fighterId: 'lucy', action: { ...action, accelerated: true }, phase: 'impact' },
    })
    expect(wrapper.getComponent(CombatEffect).props('effect')).toBe('shot')
    await wrapper.setProps({
      action: { id: 'old', message: '', action: { actor_id: 'lucy', targets: [] } },
    })
    expect(wrapper.find('.combat-body--human').exists()).toBe(true)
  })
})
