import { describe, expect, it, vi } from 'vite-plus/test'
import { createIconifyMock } from '../../helpers/mocks'
import { mount } from '@vue/test-utils'
import RewardItemCard from '@/core/components/common/RewardItemCard.vue'

vi.mock('@iconify/vue', () => createIconifyMock())

describe('RewardItemCard', () => {
  it('renders a currency tile with the supplied icon and label above value, without rarity or quantity', () => {
    const wrapper = mount(RewardItemCard, {
      props: {
        kind: 'currency',
        icon: 'mdi:coins',
        label: 'Bottle Caps',
        name: '100 · 50% chance',
        quantity: 5,
        rarity: 'legendary',
      },
    })

    expect(wrapper.find('[data-icon="mdi:coins"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Bottle Caps')
    expect(wrapper.text()).toContain('100 · 50% chance')
    expect(wrapper.find('[data-slot="badge"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('legendary')
    expect(wrapper.text()).not.toContain('×5')
  })

  it('falls back to a gift icon when no currency icon is supplied', () => {
    const wrapper = mount(RewardItemCard, {
      props: { kind: 'currency', label: 'Reward', name: '50 caps' },
    })

    expect(wrapper.find('[data-icon="mdi:gift"]').exists()).toBe(true)
  })
})
