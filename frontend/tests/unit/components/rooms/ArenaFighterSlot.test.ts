import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ArenaFighterSlot from '@/modules/rooms/components/ArenaFighterSlot.vue'

const fighter = {
  id: 'fighter-1',
  name: 'Lucy',
  level: 5,
  health: 80,
  max_health: 100,
  power: null,
  image_url: '/static/portraits/lucy.png',
  thumbnail_url: '/static/portraits/lucy-thumb.png',
  is_creature: false,
}

describe('ArenaFighterSlot portraits', () => {
  it('provides a prominent clear button that removes the fighter from its slot', async () => {
    const wrapper = mount(ArenaFighterSlot, {
      props: {
        side: 'a',
        fighter,
        canChange: true,
        damageNumbers: [],
        options: [],
        pickerOpen: false,
      },
    })
    const button = wrapper.get('button[aria-label="Clear fighter"]')
    await button.trigger('click')
    expect(wrapper.emitted('clear')).toEqual([['a']])
  })

  it('uses the shared portrait component for selected fighters and picker entries', () => {
    const wrapper = mount(ArenaFighterSlot, {
      props: {
        side: 'a',
        fighter,
        canChange: false,
        damageNumbers: [],
        options: [fighter],
        pickerOpen: false,
      },
    })
    expect(wrapper.get('img').attributes('src')).toContain('/static/portraits/lucy-thumb.png')
    expect(wrapper.get('img').attributes('alt')).toBe('Lucy')
    expect(wrapper.text()).toContain('80/100')
  })

  it('disables roster selection when no candidate is available', async () => {
    const wrapper = mount(ArenaFighterSlot, {
      props: {
        side: 'a',
        fighter: null,
        canChange: true,
        damageNumbers: [],
        options: [],
        pickerOpen: false,
      },
    })
    const choose = wrapper.get('.fighter-slot-empty')
    expect(choose.text()).toContain('Choose from roster')
    expect(choose.attributes('disabled')).toBeDefined()
    await choose.trigger('click')
    expect(wrapper.emitted('togglePicker')).toBeUndefined()
  })

  it('shows picker portraits without altering the selected roster entry', async () => {
    const wrapper = mount(ArenaFighterSlot, {
      props: {
        side: 'a',
        fighter: null,
        canChange: true,
        damageNumbers: [],
        options: [fighter],
        pickerOpen: true,
      },
    })
    expect(wrapper.get('img').attributes('src')).toContain('/static/portraits/lucy-thumb.png')
    await wrapper.get('.picker-option').trigger('click')
    expect(wrapper.emitted('select')).toEqual([['a', fighter]])
  })
})
