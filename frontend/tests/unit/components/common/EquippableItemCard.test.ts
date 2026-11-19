import { describe, expect, it } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import EquippableItemCard from '@/core/components/common/EquippableItemCard.vue'

const weapon = {
  id: 'weapon-1',
  name: '10mm Pistol',
  rarity: 'common',
  weapon_subtype: 'pistol',
  description: 'A reliable sidearm.',
  value: 25,
}

const neutralEffect = {
  strength: 0,
  perception: 0,
  endurance: 0,
  charisma: 0,
  intelligence: 0,
  agility: 0,
  luck: 0,
  max_health: 0,
  damage_pct: 0,
  incident_response_pct: 0,
  radiation_resist_pct: 0,
  happiness: 0,
  caps_pct: 0,
  xp_pct: 0,
  training_speed_pct: 0,
}

const makePet = (overrides: Record<string, unknown> = {}) => ({
  id: 'pet-1',
  name: 'Dogmeat',
  rarity: 'rare',
  value: 100,
  image_url: null,
  dweller_id: null,
  storage_id: 'storage-1',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  effect: neutralEffect,
  ...overrides,
})

const mountCard = (props: Record<string, unknown>) =>
  mount(EquippableItemCard, { props, global: { stubs: { Icon: true } } })

describe('EquippableItemCard', () => {
  it('emits equip/unequip for equipment actions', async () => {
    const available = mountCard({ item: weapon, itemType: 'weapon', showActions: true })
    await available.get('button').trigger('click')
    expect(available.emitted('equip')).toHaveLength(1)

    const equipped = mountCard({
      item: weapon,
      itemType: 'weapon',
      showActions: true,
      equipped: true,
    })
    await equipped.get('button').trigger('click')
    expect(equipped.emitted('unequip')).toHaveLength(1)
  })

  it('emits pet equip/unequip through the same actions', async () => {
    const available = mountCard({ item: makePet(), itemType: 'pet', showActions: true })
    await available.get('button').trigger('click')
    expect(available.emitted('equip')).toHaveLength(1)

    const equipped = mountCard({
      item: makePet(),
      itemType: 'pet',
      showActions: true,
      equipped: true,
    })
    await equipped.get('button').trigger('click')
    expect(equipped.emitted('unequip')).toHaveLength(1)
  })

  it('disables actions without emitting while a pet action is pending', async () => {
    const wrapper = mountCard({
      item: makePet(),
      itemType: 'pet',
      showActions: true,
      disabled: true,
    })

    const button = wrapper.get('button')
    expect(button.attributes('disabled')).toBeDefined()
    await button.trigger('click')
    expect(wrapper.emitted('equip')).toBeUndefined()
  })

  it('renders pet effect rows once and no stat rows for a neutral pet', () => {
    const effectful = mountCard({
      item: makePet({
        effect: { ...neutralEffect, strength: 2, max_health: 50, damage_pct: 0.25, xp_pct: 0.5 },
      }),
      itemType: 'pet',
    })

    const text = effectful.text()
    expect(text).toContain('Dogmeat')
    expect(text).toContain('Pet')
    expect(text).toContain('rare')
    expect(text).toContain('Strength')
    expect(text).toContain('+2')
    expect(text).toContain('+25%')
    expect(text.match(/Max HP/g) ?? []).toHaveLength(1)
    expect(text.match(/\+50%/g) ?? []).toHaveLength(1)
    expect(effectful.findAll('[data-slot="badge"]')).toHaveLength(0)

    const neutral = mountCard({ item: makePet(), itemType: 'pet' })
    expect(neutral.text()).not.toContain('Strength')
  })

  it('shows value as a stat for equipment but not for pets', () => {
    expect(mountCard({ item: weapon, itemType: 'weapon' }).text()).toContain('Value')
    expect(mountCard({ item: makePet(), itemType: 'pet' }).text()).not.toContain('Value')
  })

  it('constrains long outfit names so they truncate instead of overflowing the card', () => {
    const longNames = [
      'Firefighter suit, rad helmet',
      "Confessor Cromwell's rags",
      'X-01 Mk IV power armor',
    ]

    for (const name of longNames) {
      const wrapper = mountCard({
        item: { id: 'outfit-1', name, rarity: 'rare', outfit_type: 'rare_outfit' },
        itemType: 'outfit',
      })

      const nameContainer = wrapper.find('h4').element.parentElement!
      expect(nameContainer.classList).toContain('min-w-0')
      expect(wrapper.find('h4').classes()).toContain('truncate')
      expect(wrapper.find('p').classes()).toContain('truncate')
      expect(wrapper.text()).toContain(name)
    }
  })
})
