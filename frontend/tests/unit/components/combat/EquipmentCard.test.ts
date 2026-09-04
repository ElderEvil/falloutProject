import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import EquipmentCard from '@/modules/combat/components/equipment/EquipmentCard.vue'

const weapon = {
  id: 'weapon-1',
  name: '10mm Pistol',
  rarity: 'common',
  weapon_subtype: 'pistol',
  description: 'A reliable sidearm.',
}

describe('EquipmentCard', () => {
  it('emits the matching shared-button action for available and equipped items', async () => {
    const available = mount(EquipmentCard, {
      props: { item: weapon, type: 'weapon', showActions: true },
      global: { stubs: { Icon: true } },
    })

    await available.get('button').trigger('click')
    expect(available.emitted('equip')).toHaveLength(1)

    const equipped = mount(EquipmentCard, {
      props: { item: weapon, type: 'weapon', showActions: true, equipped: true },
      global: { stubs: { Icon: true } },
    })

    await equipped.get('button').trigger('click')
    expect(equipped.emitted('unequip')).toHaveLength(1)
  })
})
