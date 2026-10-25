import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import CombatantMeters from '@/modules/rooms/components/CombatantMeters.vue'

const action = {
  name: 'Aimed Shot',
  icon: 'gun-rifle' as const,
  charge: 100,
  queued: false,
  pending: false,
  enabled: true,
}

describe('CombatantMeters', () => {
  it('renders the name, health, and charged action', () => {
    const wrapper = mount(CombatantMeters, {
      props: { name: 'Alpha', health: 80, maxHealth: 100, action },
    })

    expect(wrapper.text()).toContain('Alpha')
    expect(wrapper.get('button svg[data-skill-icon="gun-rifle"]').attributes('aria-hidden')).toBe(
      'true'
    )
    expect(
      wrapper.get('[role="progressbar"][aria-label="Alpha HP"]').attributes('aria-valuenow')
    ).toBe('80')
    expect(
      wrapper
        .get('[role="progressbar"][aria-label="Alpha skill charge"]')
        .attributes('aria-valuenow')
    ).toBe('100')
  })

  it('shows health only when the actor has no action', () => {
    const wrapper = mount(CombatantMeters, {
      props: { name: 'Radroach', health: 20, maxHealth: 35 },
    })

    expect(wrapper.get('[role="progressbar"][aria-label="Radroach HP"]').exists()).toBe(true)
    expect(wrapper.find('[aria-label="Radroach skill charge"]').exists()).toBe(false)
  })

  it('emits the skill when charged, enabled, and alive', async () => {
    const wrapper = mount(CombatantMeters, {
      props: { name: 'Alpha', health: 80, maxHealth: 100, action },
    })

    await wrapper.get('button[aria-label^="Use Aimed Shot for Alpha"]').trigger('click')

    expect(wrapper.emitted('skill')).toHaveLength(1)
  })

  it.each([
    ['uncharged', { ...action, charge: 99 }, 80],
    ['queued', { ...action, queued: true }, 80],
    ['pending', { ...action, pending: true }, 80],
    ['disabled', { ...action, enabled: false }, 80],
    ['knocked out', action, 0],
  ])('disables the action when %s', (_label, actionProp, health) => {
    const wrapper = mount(CombatantMeters, {
      props: { name: 'Alpha', health, maxHealth: 100, action: actionProp },
    })

    expect(
      wrapper.get('button[aria-label^="Use Aimed Shot for Alpha"]').attributes('disabled')
    ).toBeDefined()
  })
})
