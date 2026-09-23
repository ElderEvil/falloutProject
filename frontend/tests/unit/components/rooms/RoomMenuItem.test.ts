import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import RoomMenuItem from '@/modules/rooms/components/RoomMenuItem.vue'
import { getRoomImageUrl } from '@/core/utils/image'
import { useVaultStore } from '@/modules/vault/stores/vault'

vi.mock('vue-router', () => ({ useRoute: () => ({ params: { id: 'vault-1' } }) }))
vi.mock('@iconify/vue', () => ({ Icon: { props: ['icon'], template: '<i :data-icon="icon" />' } }))

const room = {
  name: 'Power Generator',
  category: 'production',
  ability: 'strength',
  base_cost: 100,
  incremental_cost: 25,
  t2_upgrade_cost: 500,
  t3_upgrade_cost: 1500,
  population_required: null,
  size_min: 3,
  size_max: 9,
  tier: 1,
  image_url: '/static/room_images/FOS Power 1-1.png',
}

describe('RoomMenuItem', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('shows the template image and falls back to the preview category icon if it fails', async () => {
    const wrapper = mount(RoomMenuItem, { props: { room } })
    const preview = wrapper.find('.room-icon img')

    expect(preview.attributes('src')).toBe(getRoomImageUrl(room.image_url))
    await preview.trigger('error')
    expect(wrapper.find('.room-icon img').exists()).toBe(false)
    expect(wrapper.find('.room-icon [data-icon="mdi:lightning-bolt"]').exists()).toBe(true)
  })

  it('keeps population progress visible once a room is unlocked', () => {
    const vaultStore = useVaultStore()
    vaultStore.loadedVaults['vault-1'] = { bottle_caps: 1000, dweller_count: 10 } as never
    const wrapper = mount(RoomMenuItem, {
      props: { room: { ...room, population_required: 10 } },
    })

    const progress = wrapper.find('[data-slot="progress"]')
    expect(progress.exists()).toBe(true)
    expect(progress.attributes('aria-valuenow')).toBe('100')

    const rows = wrapper.findAll('.room-detail-row')
    expect(rows).toHaveLength(2)
    expect(rows[0].find('.room-category').exists()).toBe(true)
    expect(rows[0].find('.room-size').exists()).toBe(true)
    expect(rows[1].find('.room-cost').exists()).toBe(true)
    expect(rows[1].find('.room-population').exists()).toBe(true)

    const details = Array.from(wrapper.find('.room-details').element.children)
    expect(details.indexOf(rows[1].element)).toBeLessThan(details.indexOf(progress.element))
  })

  it('renders all four room detail rows', () => {
    const wrapper = mount(RoomMenuItem, {
      props: { room: { ...room, population_required: 10 } },
    })

    const details = wrapper.findAll('.room-category, .room-cost, .room-population, .room-size')
    expect(details).toHaveLength(4)
  })
})
