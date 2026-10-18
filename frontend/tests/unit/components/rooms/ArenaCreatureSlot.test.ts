import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ArenaCreatureSlot from '@/modules/rooms/components/ArenaCreatureSlot.vue'
import type { ArenaCreatureView } from '@/modules/rooms/models/arena'

vi.mock('@iconify/vue', () => ({
  Icon: { props: ['icon'], template: '<span :data-icon="icon" />' },
}))

const creature = (key: string, name = key): ArenaCreatureView => ({
  key,
  name,
  power: 35,
  health: 20,
  max_health: 35,
  id: `${key}#0`,
})

const render = (selected: ArenaCreatureView | null) =>
  mount(ArenaCreatureSlot, {
    props: {
      creature: selected,
      canChange: true,
      options: [],
      pickerOpen: false,
    },
  })

describe('ArenaCreatureSlot artwork', () => {
  it('provides a prominent clear button that removes the creature from its slot', async () => {
    const wrapper = render(creature('deathclaw', 'Deathclaw'))
    const button = wrapper.get('button[aria-label="Clear Deathclaw"]')
    await button.trigger('click')
    expect(wrapper.emitted('clear')).toEqual([['deathclaw']])
  })

  it.each([
    ['deathclaw', 'deathclaw'],
    ['radroach-swarm', 'radroach'],
    ['mole-rat-pack', 'mole-rat'],
    ['giant-radscorpion', 'radscorpion'],
    ['feral-ghoul', 'feral-ghoul'],
    ['training-eyebot', 'eyebot'],
    ['training-protectron', 'protectron'],
    ['training-mr-handy', 'mr-handy'],
    ['yao-guai', 'yao-guai'],
    ['mirelurk', 'mirelurk'],
    ['bloatfly', 'bloatfly'],
    ['radstag', 'radstag'],
    ['night-stalker', 'night-stalker'],
  ])('renders artwork for catalog key %s alongside live HP', (key, filename) => {
    const wrapper = render(creature(key, 'Opponent'))
    const image = wrapper.get('img')
    expect(image.attributes('src')).toContain(`/static/creature_images/assembled/${filename}.webp`)
    expect(image.attributes('alt')).toBe('Opponent')
    expect(wrapper.text()).toContain('20/35')
  })

  it('keeps creatures without artwork selectable with the paw fallback', async () => {
    const wrapper = render(null)
    const raider = { key: 'raider-gang', name: 'Raider gang', power: 60, max_hp: 60 }
    await wrapper.setProps({ pickerOpen: true, options: [raider] })
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.get('[data-icon="mdi:paw"]').exists()).toBe(true)
    await wrapper.get('.picker-option').trigger('click')
    expect(wrapper.emitted('select')).toEqual([[raider]])
    await wrapper.setProps({ creature: creature('raider-gang'), pickerOpen: false })
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toContain('20/35')
  })

  it('shows picker thumbnails and emits the selected catalog creature', async () => {
    const wrapper = render(null)
    const option = { key: 'radroach-swarm', name: 'Radroach swarm', power: 35, max_hp: 35 }
    await wrapper.setProps({ pickerOpen: true, options: [option] })
    expect(wrapper.get('img').attributes('src')).toContain('/assembled/radroach.webp')
    await wrapper.get('.picker-option').trigger('click')
    expect(wrapper.emitted('select')).toEqual([[option]])
  })

  it('falls back on image failure and renders artwork when the opponent changes', async () => {
    const wrapper = render(creature('deathclaw'))
    await wrapper.get('img').trigger('error')
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.get('[data-icon="mdi:paw"]').exists()).toBe(true)
    await wrapper.setProps({ creature: creature('radroach-swarm') })
    expect(wrapper.get('img').attributes('src')).toContain('/assembled/radroach.webp')
  })
})
