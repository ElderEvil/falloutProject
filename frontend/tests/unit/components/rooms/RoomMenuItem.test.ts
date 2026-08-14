import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import RoomMenuItem from '@/modules/rooms/components/RoomMenuItem.vue'
import { getRoomImageUrl } from '@/core/utils/image'

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
})
