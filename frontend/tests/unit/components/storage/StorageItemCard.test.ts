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
})
