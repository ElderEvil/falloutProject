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
  it('makes companions lunge with their owner without weapon effects or damage reactions', async () => {
    const wrapper = mount(CombatantMotion, {
      props: { fighterId: 'lucy', companion: true, action, phase: 'prepare' },
    })
    expect(wrapper.find('.combat-body--windup').exists()).toBe(true)
    expect(wrapper.findComponent(CombatEffect).exists()).toBe(false)
    await wrapper.setProps({ phase: 'impact' })
    expect(wrapper.find('.combat-body--attack').exists()).toBe(true)
    expect(wrapper.find('.combat-body--recoil').exists()).toBe(false)
    await wrapper.setProps({ fighterId: 'maximus' })
    expect(wrapper.find('.combat-body--hit').exists()).toBe(false)
    expect(wrapper.find('.combat-body--attack').exists()).toBe(false)
    expect(wrapper.findComponent(CombatEffect).exists()).toBe(false)
  })
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
  it('highlights only targets that take damage', async () => {
    const wrapper = mount(CombatantMotion, {
      props: { fighterId: 'maximus', action, phase: 'impact' },
    })
    expect(wrapper.find('.combat-body--damaged').exists()).toBe(true)
    await wrapper.setProps({
      action: {
        ...action,
        action: { ...action.action, targets: [{ target_id: 'maximus', body: 'human', damage: 0 }] },
      },
    })
    expect(wrapper.find('.combat-body--damaged').exists()).toBe(false)
  })
  it('shows the skill impact artwork only on affected fighters during impact', async () => {
    const skill = { ...action, action: { ...action.action, skill: 'Aimed Shot' } }
    const wrapper = mount(CombatantMotion, {
      props: { fighterId: 'maximus', action: skill, phase: 'prepare' },
    })
    expect(wrapper.find('.skill-hit').exists()).toBe(false)
    await wrapper.setProps({ phase: 'impact' })
    expect(wrapper.find('.skill-hit').exists()).toBe(true)
    await wrapper.setProps({ fighterId: 'lucy' })
    expect(wrapper.find('.skill-hit').exists()).toBe(false)
    await wrapper.setProps({ fighterId: 'maximus', action: { ...skill, accelerated: true } })
    expect(wrapper.get('.skill-hit').classes()).toContain('skill-hit--stationary')
    await wrapper.setProps({ action })
    expect(wrapper.find('.skill-hit').exists()).toBe(false)
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
