import { describe, expect, it } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import ItemCard from '@/core/components/common/ItemCard.vue'
import type { Weapon } from '@/modules/combat/models/equipment'

const weapon = {
  id: 'weapon-1',
  name: '10mm Pistol',
  rarity: 'common',
  weapon_subtype: 'pistol',
  description: 'A reliable sidearm.',
  damage_min: 2,
  damage_max: 5,
  stat: 'agility',
  accuracy: 70,
  weapon_type: 'gun',
}

const outfit = {
  id: 'outfit-1',
  name: 'Lab Coat',
  rarity: 'rare',
  outfit_type: 'rare_outfit',
  description: 'Protects against spills.',
  intelligence: 2,
  gender: 'female',
}

// A stat row is the leaf div whose text is exactly "Label:value" (the icon is
// stubbed away); parent containers concatenate several labels and never match.
const statRows = (wrapper: VueWrapper) =>
  wrapper
    .findAll('div')
    .filter((node) => /^[A-Za-z ]+:[^:]+$/.test(node.text()) && node.findAll('div').length === 0)

describe('ItemCard', () => {
  it('renders the list variant as one row per attribute with label and value', () => {
    const wrapper = mount(ItemCard, {
      props: { item: weapon, itemType: 'weapon', variant: 'list' },
      global: { stubs: { Icon: true } },
    })

    const text = wrapper.text()
    expect(text).toContain('10mm Pistol')
    expect(text).toContain('Pistol • common')
    expect(text).toContain('A reliable sidearm.')
    expect(text).toContain('Damage:')
    expect(text).toContain('2-5')
    expect(text).toContain('Accuracy:')
    expect(text).toContain('70%')
    expect(text).toContain('Type:')
    expect(text).toContain('Gun')
    expect(statRows(wrapper)).toHaveLength(5)
  })

  it('renders the grid variant with the same facts', () => {
    const wrapper = mount(ItemCard, {
      props: { item: outfit, itemType: 'outfit', variant: 'grid' },
      global: { stubs: { Icon: true } },
    })

    const text = wrapper.text()
    expect(text).toContain('Lab Coat')
    expect(text).toContain('Rare Outfit • rare')
    expect(text).toContain('Protects against spills.')
    expect(text).toContain('Intelligence:')
    expect(text).toContain('+2')
    expect(text).toContain('Gender:')
    expect(text).toContain('female')
    expect(statRows(wrapper)).toHaveLength(2)
  })

  it('shows the count badge only when count is greater than one', () => {
    const single = mount(ItemCard, {
      props: { item: weapon, itemType: 'weapon', count: 1 },
      global: { stubs: { Icon: true } },
    })
    expect(single.text()).not.toContain('×')

    const stacked = mount(ItemCard, {
      props: { item: weapon, itemType: 'weapon', count: 3 },
      global: { stubs: { Icon: true } },
    })
    expect(stacked.text()).toContain('×3')
  })

  it('renders no stat block for items without stats', () => {
    const wrapper = mount(ItemCard, {
      props: {
        item: { id: 'junk-1', name: 'Desk Fan', rarity: 'common' } as Weapon,
        itemType: 'junk',
      },
      global: { stubs: { Icon: true } },
    })

    expect(wrapper.text()).toContain('Desk Fan')
    expect(wrapper.text()).toContain('common')
    expect(statRows(wrapper)).toHaveLength(0)
  })

  it('appends a Value row when showValueAsStat is set', () => {
    const wrapper = mount(ItemCard, {
      props: { item: { ...weapon, value: 50 }, itemType: 'weapon', showValueAsStat: true },
      global: { stubs: { Icon: true } },
    })

    const text = wrapper.text()
    expect(text).toContain('Value:')
    expect(text).toContain('50')
    expect(statRows(wrapper)).toHaveLength(6)
  })
})