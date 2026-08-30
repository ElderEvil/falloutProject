import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import StorageItemCard from '@/modules/storage/components/StorageItemCard.vue'

describe('StorageItemCard', () => {
  it('presents the item description and clearly labelled inventory actions', () => {
    const wrapper = mount(StorageItemCard, {
      props: {
        item: {
          name: 'Sawed-off Shotgun',
          description: 'Built for close-range combat.',
          rarity: 'common',
          value: 120,
          weapon_subtype: 'shotgun',
        },
        itemType: 'weapon',
      },
      global: { stubs: { Icon: true } },
    })

    expect(wrapper.text()).toContain('Built for close-range combat.')
    expect(wrapper.get('button[title="Scrap"]').text()).toContain('Scrap')
    expect(wrapper.get('button[title="Sell"]').text()).toContain('Sell')

    const actions = wrapper.findAll('button').map((button) => button.text())
    expect(actions.indexOf('Sell')).toBeLessThan(actions.indexOf('Scrap'))
  })

  it('includes the junk quantity in the sell-all title', () => {
    const wrapper = mount(StorageItemCard, {
      props: { item: { name: 'Desk Fan', value: 10 }, itemType: 'junk', count: 3 },
      global: { stubs: { Icon: true } },
    })

    expect(wrapper.find('button[title="Sell all (3)"]').exists()).toBe(true)
  })

  it('renders the unified weapon stats including accuracy', () => {
    const wrapper = mount(StorageItemCard, {
      props: {
        item: {
          name: '10mm Pistol',
          rarity: 'rare',
          value: 50,
          weapon_subtype: 'pistol',
          damage_min: 2,
          damage_max: 5,
          stat: 'agility',
          accuracy: 70,
          weapon_type: 'gun',
        },
        itemType: 'weapon',
      },
      global: { stubs: { Icon: true } },
    })

    const text = wrapper.text()
    expect(text).toContain('Damage:')
    expect(text).toContain('2-5')
    expect(text).toContain('Accuracy:')
    expect(text).toContain('70%')
    expect(text).toContain('Type:')
  })

  it('renders outfit SPECIAL bonuses alongside gender', () => {
    const wrapper = mount(StorageItemCard, {
      props: {
        item: {
          name: 'Lab Coat',
          rarity: 'rare',
          outfit_type: 'rare_outfit',
          intelligence_bonus: 2,
          gender: 'female',
        },
        itemType: 'outfit',
      },
      global: { stubs: { Icon: true } },
    })

    const text = wrapper.text()
    expect(text).toContain('I:')
    expect(text).toContain('+2')
    expect(text).toContain('Gender:')
    expect(text).toContain('female')
  })
})
