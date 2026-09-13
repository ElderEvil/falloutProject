import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { UModal } from '@/core/components/ui'
import LunchboxOpenModal from '@/modules/storage/components/LunchboxOpenModal.vue'
import type { components } from '@/core/types/api.generated'

type LunchboxOpened = components['schemas']['LunchboxOpened']

vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon"></span>',
    props: ['icon'],
  },
}))

const result: LunchboxOpened = {
  reward_type: 'lunchbox',
  items: [
    { name: 'Laser Pistol', type: 'weapon', rarity: 'rare' },
    { name: 'Vault Suit', type: 'outfit', rarity: 'common' },
    { name: 'Combat Armor', type: 'outfit', rarity: 'legendary' },
  ],
  dweller: { reward_type: 'dweller', dweller_id: 'dweller-1', name: 'Jane Doe' },
}

describe('LunchboxOpenModal', () => {
  it('renders sealed placeholders before revealing', () => {
    const wrapper = mount(LunchboxOpenModal, {
      props: { show: true, result },
      global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
    })

    expect(wrapper.findComponent(UModal).props('modelValue')).toBe(true)
    expect(wrapper.text()).toContain('Reveal Contents')
    expect(wrapper.text()).not.toContain('Laser Pistol')
    expect(wrapper.text()).not.toContain('Jane Doe')
  })

  it('reveals rolled items and the dweller on demand', async () => {
    const wrapper = mount(LunchboxOpenModal, {
      props: { show: true, result },
      global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
    })

    const reveal = wrapper.findAll('button').find(button => button.text().includes('Reveal Contents'))
    expect(reveal?.exists()).toBe(true)
    await reveal!.trigger('click')

    expect(wrapper.text()).toContain('Laser Pistol')
    expect(wrapper.text()).toContain('rare')
    expect(wrapper.text()).toContain('Vault Suit')
    expect(wrapper.text()).toContain('Jane Doe')
  })

  it('emits close from the Done action', async () => {
    const wrapper = mount(LunchboxOpenModal, {
      props: { show: true, result },
      global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
    })

    const done = wrapper.findAll('button').find(button => button.text() === 'Done')
    expect(done?.exists()).toBe(true)
    await done!.trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})
